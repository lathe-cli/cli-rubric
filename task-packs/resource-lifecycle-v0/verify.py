#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = PACK_DIR / "task-pack.json"
REFERENCE_CLI = PACK_DIR / "reference_cli.py"


def load_json(path):
    return json.loads(path.read_text())


def write_state(path, state):
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def resource(state, resource_id):
    return next(
        (item for item in state["resources"] if item["id"] == resource_id),
        None,
    )


def contains_values(output, values):
    return all(str(value) in output for value in values)


def grade(task_id, initial_state, final_state, output):
    if task_id == "list-resources":
        expected = [
            value
            for item in initial_state["resources"]
            for value in (item["id"], item["name"], item["status"])
        ]
        return contains_values(output, expected)
    if task_id == "inspect-alpha":
        alpha = resource(initial_state, "alpha")
        expected = [
            alpha["id"],
            alpha["name"],
            alpha["status"],
            *alpha["labels"].keys(),
            *alpha["labels"].values(),
        ]
        return contains_values(output, expected)
    if task_id == "create-gamma":
        return resource(final_state, "gamma") == {
            "id": "gamma",
            "name": "Gamma",
            "status": "active",
            "labels": {"team": "core"},
        }
    if task_id == "update-beta":
        return resource(final_state, "beta") == {
            "id": "beta",
            "name": "Beta",
            "status": "active",
            "labels": {"owner": "ops", "team": "edge"},
        }
    if task_id == "recover-invalid-create":
        return resource(final_state, "delta") == {
            "id": "delta",
            "name": "Delta",
            "status": "active",
            "labels": {"team": "core"},
        }
    if task_id == "delete-beta-safely":
        return resource(final_state, "beta") is None
    raise ValueError(f"unknown grader task: {task_id}")


def json_document(value):
    if not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def step_by_role(steps, role):
    return next((step for step in steps if step["role"] == role), None)


def relevant_output(steps):
    main = step_by_role(steps, "main")
    recovery = step_by_role(steps, "recovery")
    commit = step_by_role(steps, "commit")
    return (main or recovery or commit or steps[-1])["stdout"]


def structured_output(steps):
    for step in steps:
        if step["role"] == "discover":
            continue
        stream = step["stderr"] if step["role"] == "invalid" else step["stdout"]
        if json_document(stream) is None:
            return False
    return True


def actionable_error(steps):
    invalid = step_by_role(steps, "invalid")
    if invalid is None:
        return False
    document = json_document(invalid["stderr"])
    if not isinstance(document, dict):
        return "hint:" in invalid["stderr"].lower()
    error = document.get("error")
    return (
        isinstance(error, dict)
        and bool(error.get("code"))
        and bool(error.get("message"))
        and bool(error.get("hint"))
    )


def criterion_result(criterion, task, initial_state, final_state, steps):
    task_id = task["id"]
    outcome = grade(task_id, initial_state, final_state, relevant_output(steps))
    main = step_by_role(steps, "main")
    invalid = step_by_role(steps, "invalid")
    recovery = step_by_role(steps, "recovery")
    preview = step_by_role(steps, "preview")
    commit = step_by_role(steps, "commit")

    if criterion == "outcome_correct":
        return outcome
    if criterion == "zero_exit":
        terminal = main or recovery or commit or steps[-1]
        return terminal["exit_code"] == 0
    if criterion == "structured_output":
        return structured_output(steps)
    if criterion == "discoverable_help":
        discover = step_by_role(steps, "discover")
        return (
            discover is not None
            and discover["exit_code"] == 0
            and "resource list" in discover["stdout"]
            and "resource create" in discover["stdout"]
            and "resource delete" in discover["stdout"]
        )
    if criterion == "read_only_preserves_state":
        return all(step["before"] == step["after"] for step in steps)
    if criterion == "confirmed_change":
        changed = main or commit
        return (
            changed is not None
            and changed["exit_code"] == 0
            and changed["before"] != changed["after"]
            and outcome
        )
    if criterion == "invalid_nonzero":
        return invalid is not None and invalid["exit_code"] != 0
    if criterion == "actionable_error":
        return actionable_error(steps)
    if criterion == "invalid_preserves_state":
        return invalid is not None and invalid["before"] == invalid["after"]
    if criterion == "recovery_success":
        return recovery is not None and recovery["exit_code"] == 0 and outcome
    if criterion == "preview_supported":
        if preview is None or preview["exit_code"] != 0:
            return False
        document = json_document(preview["stdout"])
        return isinstance(document, dict) and document.get("dry_run") is True
    if criterion == "preview_no_mutation":
        return preview is not None and preview["before"] == preview["after"]
    raise ValueError(f"unknown criterion: {criterion}")


def run_task(manifest, task, variant, adapter):
    initial_state = deepcopy(manifest["fixture"]["initial_state"])
    with tempfile.TemporaryDirectory(prefix="cli-rubric-task-") as directory:
        state_file = Path(directory) / "state.json"
        write_state(state_file, initial_state)
        environment = os.environ.copy()
        environment[manifest["fixture"]["state_environment_variable"]] = str(state_file)
        steps = []

        for adapter_step in adapter:
            before = load_json(state_file)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REFERENCE_CLI),
                    "--variant",
                    variant,
                    *adapter_step["argv"],
                ],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
                timeout=task["budget"]["wall_time_seconds"],
            )
            after = load_json(state_file)
            steps.append(
                {
                    "role": adapter_step["role"],
                    "argv": adapter_step["argv"],
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "before": before,
                    "after": after,
                }
            )

        final_state = load_json(state_file)
        criteria = {
            criterion: criterion_result(
                criterion,
                task,
                initial_state,
                final_state,
                steps,
            )
            for criterion in task["criteria"]
        }
        return {
            "task_id": task["id"],
            "passed": sum(criteria.values()),
            "total": len(criteria),
            "criteria": criteria,
        }


def verify_manifest(manifest):
    tasks = manifest["tasks"]
    variants = manifest["reference_variants"]
    task_ids = [task["id"] for task in tasks]
    variant_ids = [variant["id"] for variant in variants]

    if len(tasks) != 6 or len(set(task_ids)) != 6:
        raise AssertionError("the controlled pack must contain six unique tasks")
    if set(manifest["tracks"]) != {"human", "agent"}:
        raise AssertionError("the controlled pack must cover both tracks")
    if len(variants) != 3 or len(set(variant_ids)) != 3:
        raise AssertionError("the controlled pack must contain three variants")
    if manifest["verification"]["expected_order"] != variant_ids:
        raise AssertionError("reference variants must follow expected_order")
    if manifest["fixture"]["reset_per_task"] is not True:
        raise AssertionError("fixture reset_per_task must remain true")

    for task in tasks:
        if not task["core"]:
            raise AssertionError(f"{task['id']} must remain a core task")
        if task["budget"]["max_commands"] < 1:
            raise AssertionError(f"{task['id']} has no command budget")
        if grade(
            task["id"],
            manifest["fixture"]["initial_state"],
            manifest["fixture"]["initial_state"],
            "",
        ):
            raise AssertionError(f"{task['id']} grader accepts empty evidence")

    for variant in variants:
        adapters = variant["task_adapters"]
        if set(adapters) != set(task_ids):
            raise AssertionError(f"{variant['id']} does not cover every task")
        for task in tasks:
            if len(adapters[task["id"]]) > task["budget"]["max_commands"]:
                raise AssertionError(
                    f"{variant['id']} exceeds {task['id']} command budget"
                )


def verify():
    manifest = load_json(MANIFEST_PATH)
    verify_manifest(manifest)
    tasks = {task["id"]: task for task in manifest["tasks"]}
    results = []

    for variant in manifest["reference_variants"]:
        task_results = [
            run_task(
                manifest,
                tasks[task_id],
                variant["id"],
                adapter,
            )
            for task_id, adapter in variant["task_adapters"].items()
        ]
        results.append(
            {
                "id": variant["id"],
                "passed_criteria": sum(item["passed"] for item in task_results),
                "total_criteria": sum(item["total"] for item in task_results),
                "tasks": task_results,
            }
        )

    counts = [item["passed_criteria"] for item in results]
    if counts != sorted(counts) or len(set(counts)) != len(counts):
        raise AssertionError(f"reference ordering failed: {counts}")
    if results[-1]["passed_criteria"] != results[-1]["total_criteria"]:
        raise AssertionError("improved reference must pass every criterion")

    return {
        "status": "pass",
        "result_kind": "calibration_only",
        "official_score": False,
        "task_pack": manifest["id"],
        "ordering": [item["id"] for item in results],
        "criteria_counts": {
            item["id"]: {
                "passed": item["passed_criteria"],
                "total": item["total_criteria"],
            }
            for item in results
        },
        "variants": results,
    }


def main():
    try:
        result = verify()
    except (
        AssertionError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ) as error:
        print(json.dumps({"status": "fail", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
