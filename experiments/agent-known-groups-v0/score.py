#!/usr/bin/env python3

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
PROTOCOL_PATH = EXPERIMENT_DIR / "protocol.json"
TASK_PACK_PATH = REPO_ROOT / "task-packs/resource-lifecycle-v0/task-pack.json"


class ValidationError(ValueError):
    pass


def load_json(path):
    return json.loads(Path(path).read_text())


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mean(values):
    return sum(values) / len(values)


def normalize_cost(value, target, limit):
    if target >= limit:
        raise ValidationError("cost normalization target must be below limit")
    if value <= target:
        return 1.0
    if value >= limit:
        return 0.0
    return (limit - value) / (limit - target)


def measure_registry(protocol):
    registry = {}
    for dimension_id, dimension in protocol["dimensions"].items():
        for measure_id, measure in dimension["measures"].items():
            if measure_id in registry:
                raise ValidationError(f"duplicate measure id: {measure_id}")
            registry[measure_id] = {
                **measure,
                "construct_id": dimension_id,
                "dimension_weight": dimension["weight"],
            }
    return registry


def applicable_tasks(measure, task_ids):
    return task_ids if measure["tasks"] == "all" else measure["tasks"]


def expected_measure_keys(registry, task_id, task_ids):
    return {
        (definition["construct_id"], measure_id)
        for measure_id, definition in registry.items()
        if task_id in applicable_tasks(definition, task_ids)
    }


def validate_protocol(protocol, task_pack):
    if protocol["official_score"] is not False:
        raise ValidationError("qualification protocol must forbid official scores")
    if protocol["phases"]["qualification"]["score_status"] != "unscored":
        raise ValidationError("qualification phase must remain unscored")
    dimensions = protocol["dimensions"]
    if set(dimensions) != {"A1", "A2", "A3", "A4", "A5"}:
        raise ValidationError("Agent dimensions must be A1 through A5")
    if not math.isclose(
        sum(item["weight"] for item in dimensions.values()),
        1.0,
        abs_tol=1e-9,
    ):
        raise ValidationError("dimension weights must sum to one")
    task_ids = [task["id"] for task in task_pack["tasks"]]
    for dimension_id, dimension in dimensions.items():
        if not math.isclose(
            sum(item["weight"] for item in dimension["measures"].values()),
            1.0,
            abs_tol=1e-9,
        ):
            raise ValidationError(f"{dimension_id} measure weights must sum to one")
        for measure in dimension["measures"].values():
            unknown = set(applicable_tasks(measure, task_ids)) - set(task_ids)
            if unknown:
                raise ValidationError(
                    f"{dimension_id} references unknown tasks: {sorted(unknown)}"
                )
    expected_variants = protocol["subjects"]["variants"]
    actual_variants = [item["id"] for item in task_pack["reference_variants"]]
    if expected_variants != actual_variants:
        raise ValidationError("protocol variants do not match the task pack")


def resolve_uri(uri, bundle_path, repo_root):
    relative = Path(uri)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValidationError(f"unsafe artifact uri: {uri}")
    candidates = [
        (repo_root / relative).resolve(),
        (bundle_path.parent / relative).resolve(),
    ]
    roots = [repo_root.resolve(), bundle_path.parent.resolve()]
    for candidate, root in zip(candidates, roots):
        if candidate.is_relative_to(root) and candidate.is_file():
            return candidate
    raise ValidationError(f"artifact does not exist: {uri}")


def validate_reference(reference, bundle_path, repo_root):
    path = resolve_uri(reference["uri"], bundle_path, repo_root)
    if sha256_file(path) != reference["sha256"]:
        raise ValidationError(f"artifact digest mismatch: {reference['uri']}")
    return path


def validate_bundle(bundle, bundle_path, repo_root, protocol, task_pack):
    if bundle["schema_version"] != "0.1.0" or bundle["track"] != "agent":
        raise ValidationError("qualification bundle must use Agent schema v0.1.0")
    if bundle["maturity"] != "experimental":
        raise ValidationError("qualification bundle must remain experimental")
    if bundle["score"]["status"] != "unscored":
        raise ValidationError("qualification bundle must remain unscored")
    if bundle["subject"]["name"] not in protocol["subjects"]["variants"]:
        raise ValidationError("bundle subject is not a controlled variant")
    if bundle["integrity"]["all_artifacts_verified"] is not True:
        raise ValidationError("bundle does not claim verified artifacts")

    actor_ids = [actor["id"] for actor in bundle["actors"]]
    artifact_ids = [artifact["id"] for artifact in bundle["artifacts"]]
    trial_ids = [trial["id"] for trial in bundle["trials"]]
    if len(actor_ids) != len(set(actor_ids)):
        raise ValidationError("actor ids must be unique")
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValidationError("artifact ids must be unique")
    if len(trial_ids) != len(set(trial_ids)):
        raise ValidationError("trial ids must be unique")

    for artifact in bundle["artifacts"]:
        path = resolve_uri(artifact["uri"], bundle_path, repo_root)
        if path.stat().st_size != artifact["byte_length"]:
            raise ValidationError(f"artifact length mismatch: {artifact['id']}")
        if sha256_file(path) != artifact["sha256"]:
            raise ValidationError(f"artifact digest mismatch: {artifact['id']}")

    method = bundle["method"]
    for key in ("rubric", "profile", "task_pack", "runner"):
        validate_reference(method[key], bundle_path, repo_root)
    for grader in method["graders"]:
        validate_reference(grader, bundle_path, repo_root)

    task_ids = {task["id"] for task in task_pack["tasks"]}
    registry = measure_registry(protocol)
    artifacts = set(artifact_ids)
    actors = set(actor_ids)
    for trial in bundle["trials"]:
        if trial["task_id"] not in task_ids:
            raise ValidationError(f"unknown task: {trial['task_id']}")
        if trial["actor_id"] not in actors:
            raise ValidationError(f"unknown actor: {trial['actor_id']}")
        sequences = [command["sequence"] for command in trial["commands"]]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValidationError(f"non-contiguous command sequence: {trial['id']}")
        for command in trial["commands"]:
            for key in ("stdin_ref", "stdout_ref", "stderr_ref"):
                reference = command.get(key)
                if reference is not None and reference not in artifacts:
                    raise ValidationError(f"unknown command evidence ref: {reference}")
        seen = set()
        for measurement in trial["measurements"]:
            measure_id = measurement["measure_id"]
            if measure_id not in registry:
                raise ValidationError(f"unknown measure: {measure_id}")
            definition = registry[measure_id]
            if measurement["construct_id"] != definition["construct_id"]:
                raise ValidationError(f"construct mismatch: {measure_id}")
            if trial["task_id"] not in applicable_tasks(
                definition,
                list(task_ids),
            ):
                raise ValidationError(
                    f"{measure_id} is not applicable to {trial['task_id']}"
                )
            key = (measurement["construct_id"], measure_id)
            if key in seen:
                raise ValidationError(
                    f"duplicate trial measurement: {trial['id']}:{measure_id}"
                )
            seen.add(key)
            if not set(measurement["evidence_refs"]).issubset(artifacts):
                raise ValidationError(f"unknown measurement evidence: {measure_id}")
        expected = expected_measure_keys(
            registry,
            trial["task_id"],
            list(task_ids),
        )
        if seen != expected:
            missing = sorted(expected - seen)
            extra = sorted(seen - expected)
            raise ValidationError(
                f"measurement coverage mismatch: {trial['id']}: "
                f"missing={missing}, extra={extra}"
            )


def project_subject(bundles, protocol, task_pack):
    task_ids = [task["id"] for task in task_pack["tasks"]]
    values = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    completion_values = defaultdict(list)
    critical_events = []
    major_deviations = []

    for bundle in bundles:
        major_deviations.extend(
            item
            for item in bundle["method"]["protocol_deviations"]
            if item["severity"] == "major"
        )
        for trial in bundle["trials"]:
            critical_events.extend(trial["critical_events"])
            if not trial["valid"]:
                continue
            actor_id = trial["actor_id"]
            for measurement in trial["measurements"]:
                key = (
                    measurement["construct_id"],
                    measurement["measure_id"],
                )
                values[key][trial["task_id"]][actor_id].append(
                    measurement["normalized_value"]
                )
                if measurement["measure_id"] == "task_completion":
                    completion_values[trial["task_id"]].append(
                        measurement["normalized_value"]
                    )

    dimensions = []
    weighted_value = 0.0
    weighted_coverage = 0.0
    for dimension_id, dimension in protocol["dimensions"].items():
        numerator = 0.0
        coverage = 0.0
        measures = []
        for measure_id, definition in dimension["measures"].items():
            expected_tasks = applicable_tasks(definition, task_ids)
            per_task = {}
            for task_id, actors in values[(dimension_id, measure_id)].items():
                per_task[task_id] = mean(
                    [mean(repetitions) for repetitions in actors.values()]
                )
            task_coverage = (
                len(set(per_task) & set(expected_tasks)) / len(expected_tasks)
                if expected_tasks
                else 0.0
            )
            value = mean(list(per_task.values())) if per_task else None
            effective_weight = definition["weight"] * task_coverage
            if value is not None:
                numerator += value * effective_weight
                coverage += effective_weight
            measures.append(
                {
                    "id": measure_id,
                    "value": value,
                    "task_coverage": task_coverage,
                    "weight": definition["weight"],
                }
            )
        dimension_value = numerator / coverage if coverage else None
        dimensions.append(
            {
                "id": dimension_id,
                "weight": dimension["weight"],
                "value": dimension_value,
                "score": (
                    round(100 * dimension_value, 6)
                    if dimension_value is not None
                    else None
                ),
                "coverage": round(coverage, 6),
                "measures": measures,
            }
        )
        if dimension_value is not None:
            weighted_value += dimension["weight"] * coverage * dimension_value
            weighted_coverage += dimension["weight"] * coverage

    diagnostic_score = (
        round(100 * weighted_value / weighted_coverage, 6)
        if weighted_coverage
        else None
    )
    core_completion = (
        mean([value for values_ in completion_values.values() for value in values_])
        if completion_values
        else 0.0
    )
    zero_success = any(
        len(values_) >= 3 and not any(values_) for values_ in completion_values.values()
    )
    confirmed_cli_events = [
        event
        for event in critical_events
        if event["confirmed"] and event["attributable_to"] == "cli"
    ]
    return {
        "diagnostic_score": diagnostic_score,
        "coverage": round(weighted_coverage, 6),
        "dimensions": dimensions,
        "gates": {
            "evidence": bool(major_deviations) or weighted_coverage < 1.0,
            "core_task": core_completion < 0.6 or zero_success,
            "critical_failure": bool(confirmed_cli_events),
            "preference": diagnostic_score is not None and diagnostic_score >= 90,
        },
        "valid_trial_count": sum(
            trial["valid"] for bundle in bundles for trial in bundle["trials"]
        ),
    }


def project_bundles(bundles, protocol, task_pack):
    grouped = defaultdict(list)
    for bundle in bundles:
        grouped[bundle["subject"]["name"]].append(bundle)
    projections = {
        subject: project_subject(subject_bundles, protocol, task_pack)
        for subject, subject_bundles in grouped.items()
    }
    ranked = sorted(
        (
            (subject, projection["diagnostic_score"])
            for subject, projection in projections.items()
            if projection["diagnostic_score"] is not None
        ),
        key=lambda item: item[1],
    )
    observed_order = [subject for subject, _ in ranked]
    expected_order = protocol["subjects"]["variants"]
    return {
        "reconstruction_status": "pass",
        "result_kind": "qualification_projection",
        "official_score": False,
        "score_status": "unscored",
        "subjects": projections,
        "known_groups": {
            "expected_order": expected_order,
            "observed_order": observed_order,
            "complete": set(observed_order) == set(expected_order),
            "matches": observed_order == expected_order,
            "interpretation": "Diagnostic only; qualification results are discarded.",
        },
    }


def self_check(protocol, task_pack):
    validate_protocol(protocol, task_pack)
    if (
        normalize_cost(0, 0, 3) != 1
        or normalize_cost(3, 0, 3) != 0
        or not math.isclose(normalize_cost(1, 0, 3), 2 / 3)
    ):
        raise ValidationError("cost normalization self-check failed")
    return {
        "status": "pass",
        "mode": "self-check",
        "official_score": False,
        "protocol": protocol["id"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bundles", nargs="*", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    try:
        protocol = load_json(PROTOCOL_PATH)
        task_pack = load_json(TASK_PACK_PATH)
        if args.self_check:
            result = self_check(protocol, task_pack)
        else:
            if not args.bundles:
                parser.error("at least one evidence bundle is required")
            bundles = []
            for path in args.bundles:
                bundle = load_json(path)
                validate_bundle(
                    bundle,
                    path.resolve(),
                    REPO_ROOT,
                    protocol,
                    task_pack,
                )
                bundles.append(bundle)
            result = project_bundles(bundles, protocol, task_pack)
    except (
        AssertionError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        ValidationError,
    ) as error:
        print(json.dumps({"status": "fail", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
