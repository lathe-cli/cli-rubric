#!/usr/bin/env python3

import argparse
import json
import runpy
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import score as scorer

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
PROTOCOL_PATH = EXPERIMENT_DIR / "protocol.json"
PROFILE_PATH = EXPERIMENT_DIR / "qualification-profile.json"
TASK_PACK_PATH = REPO_ROOT / "task-packs/resource-lifecycle-v0/task-pack.json"
REFERENCE_CLI = REPO_ROOT / "task-packs/resource-lifecycle-v0/reference_cli.py"
TASK_PACK_VERIFY = REPO_ROOT / "task-packs/resource-lifecycle-v0/verify.py"
RUBRIC_PATH = REPO_ROOT / "docs/RUBRIC-v0.md"
EVIDENCE_SCHEMA = REPO_ROOT / "schemas/v0/evidence.schema.json"
RESULTS_ROOT = REPO_ROOT / ".local/agent-known-groups-v0"
ACTOR_ID = "openai-codex-cli-qualification"

GRADER = runpy.run_path(
    str(TASK_PACK_VERIFY),
    run_name="cli_rubric_resource_lifecycle_grader",
)

RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "completed",
        "state_verified",
        "error_recovered",
        "observed",
        "summary",
    ],
    "properties": {
        "completed": {"type": "boolean"},
        "state_verified": {"type": "boolean"},
        "error_recovered": {"type": "boolean"},
        "observed": {"type": "string"},
        "summary": {"type": "string"},
    },
    "additionalProperties": False,
}

WRAPPER_SOURCE = """\
#!{python}
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / ".subject.json").read_text())
STATE = Path(CONFIG["state"])
LOG = Path(CONFIG["log"])


def load_state():
    return json.loads(STATE.read_text())


started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
started = time.monotonic()
before = load_state()
arguments = sys.argv[1:]
if any(
    argument == "--variant" or argument.startswith("--variant=")
    for argument in arguments
):
    exit_code = 2
    stdout = ""
    stderr = "error: unknown option\\n"
else:
    environment = {{
        "CLI_RUBRIC_STATE": str(STATE),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }}
    completed = subprocess.run(
        [
            CONFIG["python"],
            CONFIG["reference_cli"],
            "--variant",
            CONFIG["variant"],
            *arguments,
        ],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )
    exit_code = completed.returncode
    stdout = completed.stdout
    stderr = completed.stderr
after = load_state()
record = {{
    "argv": arguments,
    "started_at": started_at,
    "duration_ms": round((time.monotonic() - started) * 1000),
    "exit_code": exit_code,
    "stdout": stdout,
    "stderr": stderr,
    "before": before,
    "after": after,
}}
with LOG.open("a") as stream:
    stream.write(json.dumps(record, sort_keys=True) + "\\n")
sys.stdout.write(stdout)
sys.stderr.write(stderr)
raise SystemExit(exit_code)
"""


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def relative_uri(path):
    return str(Path(path).resolve().relative_to(REPO_ROOT))


def artifact_reference(path, media_type, version=None):
    reference = {
        "uri": relative_uri(path),
        "sha256": scorer.sha256_file(path),
        "media_type": media_type,
    }
    if version is not None:
        reference["version"] = version
    return reference


def artifact_record(artifact_id, role, path, media_type, redacted=False):
    path = Path(path)
    return {
        "id": artifact_id,
        "role": role,
        "uri": relative_uri(path),
        "media_type": media_type,
        "byte_length": path.stat().st_size,
        "sha256": scorer.sha256_file(path),
        "redacted": redacted,
    }


def task_by_id(task_pack, task_id):
    return next(task for task in task_pack["tasks"] if task["id"] == task_id)


def variant_by_id(task_pack, variant_id):
    return next(
        variant
        for variant in task_pack["reference_variants"]
        if variant["id"] == variant_id
    )


def verify_frozen_inputs(protocol, profile, task_pack):
    scorer.validate_protocol(protocol, task_pack)
    references = [
        (protocol["references"]["rubric"], RUBRIC_PATH),
        (protocol["references"]["task_pack"], TASK_PACK_PATH),
        (profile["rubric"], RUBRIC_PATH),
        (profile["task_pack"], TASK_PACK_PATH),
        (profile["agent"]["prompt"], PROTOCOL_PATH),
        (profile["documentation"]["artifacts"][0], PROTOCOL_PATH),
    ]
    for reference, path in references:
        if scorer.sha256_file(path) != reference["sha256"]:
            raise scorer.ValidationError(f"frozen digest mismatch: {path}")
    if profile["track"] != "agent":
        raise scorer.ValidationError("qualification profile must remain Agent-only")
    if profile["protocol"]["repetitions_per_task"] != 1:
        raise scorer.ValidationError("qualification repetitions must remain one")
    if profile["agent"]["history_policy"] != "clean_per_trial":
        raise scorer.ValidationError("qualification trials require clean history")
    if profile["safety"]["production_credentials"] is not False:
        raise scorer.ValidationError("subject credentials must remain forbidden")


def write_wrapper(trial_dir, variant, initial_state):
    state_path = trial_dir / "state.json"
    log_path = trial_dir / "subject-log.jsonl"
    config_path = trial_dir / ".subject.json"
    subject_path = trial_dir / "subject"
    write_json(state_path, initial_state)
    write_json(
        config_path,
        {
            "python": sys.executable,
            "reference_cli": str(REFERENCE_CLI),
            "variant": variant,
            "state": str(state_path),
            "log": str(log_path),
        },
    )
    subject_path.write_text(WRAPPER_SOURCE.format(python=sys.executable))
    state_path.chmod(0o600)
    config_path.chmod(0o600)
    subject_path.chmod(0o700)
    return state_path, log_path, subject_path


def expected_observation(task_id, initial_state, final_state):
    if task_id == "list-resources":
        return {
            "resources": sorted(
                initial_state["resources"],
                key=lambda item: item["id"],
            )
        }
    if task_id == "recover-invalid-create":
        return {"resource": GRADER["resource"](final_state, "delta")}
    if task_id == "delete-beta-safely":
        return {"deleted_id": "beta"}
    raise ValueError(f"qualification prompt is missing for task: {task_id}")


def observation_instruction(task_id):
    if task_id == "list-resources":
        return (
            'Set observed to {"resources": [...]} with each resource id, name, '
            "status, and labels."
        )
    if task_id == "recover-invalid-create":
        return (
            'Set observed to {"resource": {...}} with delta id, name, status, '
            "and labels."
        )
    if task_id == "delete-beta-safely":
        return 'Set observed to {"deleted_id": "beta"} after verifying absence.'
    raise ValueError(f"qualification prompt is missing for task: {task_id}")


def build_prompt(task):
    return "\n".join(
        [
            "You are participating in a blind CLI evaluation.",
            "The only subject CLI is ./subject in the current directory.",
            f"Task: {task['intent']}",
            "",
            "Rules:",
            "- Use only ./subject for CLI work; bundled --help is allowed.",
            "- Do not inspect files, source, environment variables, or processes.",
            "- Do not use the network or any external documentation.",
            f"- Use at most {task['budget']['max_commands']} subject invocations.",
            "- Work non-interactively and verify the final state through the CLI.",
            "- The final response must match the supplied JSON schema.",
            (
                "- Set observed to a JSON-encoded string. "
                + observation_instruction(task["id"])
            ),
            (
                "- Set error_recovered=true only when the task intentionally "
                "required an invalid attempt and you recovered from it."
            ),
        ]
    )


def parse_events(output):
    events = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def command_items(events):
    return [
        event["item"]
        for event in events
        if event.get("type") == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") == "command_execution"
    ]


def token_usage(events):
    for event in reversed(events):
        if event.get("type") != "turn.completed":
            continue
        usage = event.get("usage")
        return usage if isinstance(usage, dict) else None
    return None


def read_wrapper_log(path):
    if not path.is_file():
        return []
    records = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_response(path):
    if not path.is_file():
        return None
    try:
        response = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(response, dict) or set(response) != set(
        RESPONSE_SCHEMA["required"]
    ):
        return None
    if not all(
        isinstance(response[key], bool)
        for key in ("completed", "state_verified", "error_recovered")
    ):
        return None
    if not isinstance(response["observed"], str):
        return None
    try:
        response["observed"] = json.loads(response["observed"])
    except json.JSONDecodeError:
        return None
    if not isinstance(response["observed"], dict):
        return None
    if not isinstance(response["summary"], str):
        return None
    return response


def prohibited_actor_commands(items):
    prohibited = []
    for item in items:
        command = item.get("command", "")
        if not isinstance(command, str):
            prohibited.append(command)
            continue
        try:
            tokens = shlex.split(command)
        except ValueError:
            prohibited.append(command)
            continue
        payload = (
            tokens[2]
            if len(tokens) == 3 and tokens[0].endswith("/zsh") and tokens[1] == "-lc"
            else command.strip()
        )
        lowered = payload.lower()
        if not (payload == "./subject" or payload.startswith("./subject ")):
            prohibited.append(command)
            continue
        if any(
            operator in payload
            for operator in (";", "&&", "||", "|", "`", "$(", "\n", ">", "<")
        ):
            prohibited.append(command)
            continue
        if any(
            marker in lowered
            for marker in (
                ".subject.json",
                "reference_cli",
                "printenv",
                "protocol.json",
                "task-pack.json",
                "--variant",
            )
        ):
            prohibited.append(command)
    return prohibited


def is_help(record):
    return "--help" in record["argv"] or record["argv"][:1] == ["help"]


def is_top_level_discovery(record):
    return record["argv"] in ([], ["--help"], ["help"])


def command_path(argv):
    if argv[:1] == ["resource"] and len(argv) > 1:
        return tuple(argv[:2])
    return tuple(argv[:1])


def expected_paths(task_pack, variant_id, task_id):
    variant = variant_by_id(task_pack, variant_id)
    return {
        command_path(step["argv"])
        for step in variant["task_adapters"][task_id]
        if step["role"] != "discover"
    }


def unsupported_guess_count(records, paths):
    return sum(
        command_path(record["argv"]) not in paths
        for record in records
        if not is_top_level_discovery(record)
    )


def cli_context_bytes(records):
    return sum(
        len(record["stdout"].encode("utf-8")) + len(record["stderr"].encode("utf-8"))
        for record in records
    )


def relevant_output(records):
    candidates = [
        record for record in records if not is_help(record) and record["exit_code"] == 0
    ]
    return candidates[-1]["stdout"] if candidates else ""


def has_invalid_repair(records, final_state, paths):
    invalid_indexes = [
        index
        for index, record in enumerate(records)
        if (
            record["exit_code"] != 0
            and record["before"] == record["after"]
            and command_path(record["argv"]) in paths
        )
    ]
    return any(
        any(
            later["exit_code"] == 0
            and later["before"] != later["after"]
            and command_path(later["argv"]) in paths
            and GRADER["resource"](final_state, "delta") is not None
            for later in records[index + 1 :]
        )
        for index in invalid_indexes
    )


def has_safe_delete(records, final_state):
    preview_indexes = []
    for index, record in enumerate(records):
        try:
            document = json.loads(record["stdout"])
        except json.JSONDecodeError:
            document = None
        if (
            record["exit_code"] == 0
            and record["before"] == record["after"]
            and isinstance(document, dict)
            and document.get("dry_run") is True
        ):
            preview_indexes.append(index)
    return any(
        any(
            later["exit_code"] == 0
            and later["before"] != later["after"]
            and GRADER["resource"](final_state, "beta") is None
            for later in records[index + 1 :]
        )
        for index in preview_indexes
    )


def has_cli_state_verification(task_id, initial_state, final_state, records):
    if task_id == "list-resources":
        return any(
            record["exit_code"] == 0
            and GRADER["grade"](
                task_id,
                initial_state,
                final_state,
                record["stdout"],
            )
            for record in records
            if not is_help(record)
        )
    changed_indexes = [
        index
        for index, record in enumerate(records)
        if record["before"] != record["after"]
    ]
    if not changed_indexes:
        return False
    later_records = records[changed_indexes[-1] + 1 :]
    if task_id == "recover-invalid-create":
        delta = GRADER["resource"](final_state, "delta")
        expected = [
            delta["id"],
            delta["name"],
            delta["status"],
            *delta["labels"].keys(),
            *delta["labels"].values(),
        ]
        return any(
            record["exit_code"] == 0
            and record["before"] == record["after"]
            and GRADER["contains_values"](record["stdout"], expected)
            for record in later_records
        )
    if task_id == "delete-beta-safely":
        return any(
            record["exit_code"] == 0
            and record["before"] == record["after"]
            and "beta" not in record["stdout"].lower()
            and GRADER["grade"](
                "list-resources",
                final_state,
                final_state,
                record["stdout"],
            )
            for record in later_records
        )
    return False


def measurement(construct_id, measure_id, raw, normalized, unit):
    return {
        "construct_id": construct_id,
        "measure_id": measure_id,
        "raw_value": raw,
        "unit": unit,
        "normalized_value": round(float(normalized), 6),
        "source": "deterministic",
        "evidence_refs": ["observations"],
    }


def build_measurements(
    task,
    task_pack,
    variant_id,
    initial_state,
    final_state,
    records,
    response,
    actor_commands,
    duration_ms,
    outcome_failed=False,
):
    output = relevant_output(records)
    grader_correct = GRADER["grade"](
        task["id"],
        initial_state,
        final_state,
        output,
    )
    outcome_correct = grader_correct and not outcome_failed
    task_attempts = [record for record in records if not is_top_level_discovery(record)]
    paths = expected_paths(task_pack, variant_id, task["id"])
    capability_selected = any(
        command_path(record["argv"]) in paths for record in task_attempts
    )
    first_valid = bool(
        task_attempts and command_path(task_attempts[0]["argv"]) in paths
    )
    unsupported = unsupported_guess_count(records, paths)
    response_valid = response is not None
    invalid_repair = has_invalid_repair(records, final_state, paths)
    safe_delete = has_safe_delete(records, final_state)
    expected_error_recovered = (
        invalid_repair if task["id"] == "recover-invalid-create" else False
    )
    interpreted = bool(
        response_valid
        and response["completed"] is grader_correct
        and response["error_recovered"] is expected_error_recovered
    )
    verified = bool(
        response_valid
        and response["state_verified"]
        and response["observed"]
        == expected_observation(task["id"], initial_state, final_state)
        and has_cli_state_verification(
            task["id"],
            initial_state,
            final_state,
            records,
        )
    )
    improved = variant_by_id(task_pack, "improved")
    target_calls = len(improved["task_adapters"][task["id"]])
    max_calls = task["budget"]["max_commands"]
    call_count = len(actor_commands)
    context_bytes = cli_context_bytes(records)
    elapsed_seconds = duration_ms / 1000
    measurements = [
        measurement(
            "A1",
            "task_completion",
            outcome_correct,
            outcome_correct,
            "boolean",
        ),
        measurement(
            "A1",
            "result_correctness",
            outcome_correct,
            outcome_correct,
            "boolean",
        ),
        measurement(
            "A2",
            "capability_selection",
            capability_selected,
            capability_selected,
            "boolean",
        ),
        measurement(
            "A2",
            "first_valid_invocation",
            first_valid,
            first_valid,
            "boolean",
        ),
        measurement(
            "A2",
            "unsupported_guesses",
            unsupported,
            scorer.normalize_cost(unsupported, 0, 3),
            "subject invocations",
        ),
        measurement(
            "A3",
            "parse_success",
            response_valid,
            response_valid,
            "boolean",
        ),
        measurement(
            "A3",
            "outcome_error_interpretation",
            interpreted,
            interpreted,
            "boolean",
        ),
        measurement(
            "A3",
            "state_verification",
            verified,
            verified,
            "boolean",
        ),
        measurement(
            "A5",
            "tool_calls",
            call_count,
            scorer.normalize_cost(call_count, target_calls, max_calls),
            "command executions",
        ),
        measurement(
            "A5",
            "cli_to_agent_context",
            context_bytes,
            scorer.normalize_cost(context_bytes, 4096, 32768),
            "UTF-8 bytes",
        ),
        measurement(
            "A5",
            "elapsed_time",
            elapsed_seconds,
            scorer.normalize_cost(
                elapsed_seconds,
                task["budget"]["wall_time_seconds"] * 0.25,
                task["budget"]["wall_time_seconds"],
            ),
            "seconds",
        ),
    ]
    if task["id"] == "recover-invalid-create":
        measurements.append(
            measurement(
                "A4",
                "invalid_input_repair",
                invalid_repair,
                invalid_repair,
                "boolean",
            )
        )
    if task["id"] == "delete-beta-safely":
        measurements.append(
            measurement(
                "A4",
                "safe_change_behavior",
                safe_delete,
                safe_delete,
                "boolean",
            )
        )
    return outcome_correct, grader_correct, safe_delete, measurements


def environment_manifest(profile):
    platform_spec = profile["environment"]["platforms"][0]
    return {
        "os": platform_spec["os"],
        "architecture": platform_spec["architecture"],
        "shell": platform_spec["shell"],
        "terminal": platform_spec["terminal"],
        "locale": profile["environment"]["locale"],
        "timezone": profile["environment"]["timezone"],
        "isolation": "TemporaryDirectory plus Codex workspace-write sandbox",
        "network": "Codex provider control plane only; subject shell network disabled",
    }


def subprocess_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def execute_actor(task, trial_dir):
    codex = shutil.which("codex")
    if codex is None:
        raise RuntimeError("codex CLI is not installed")
    response_schema_path = trial_dir / "response.schema.json"
    response_path = trial_dir / "last-message.json"
    write_json(response_schema_path, RESPONSE_SCHEMA)
    argv = [
        codex,
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        str(trial_dir),
        "-c",
        "shell_environment_policy.inherit=none",
        "--output-schema",
        str(response_schema_path),
        "--output-last-message",
        str(response_path),
        build_prompt(task),
    ]
    started_at = now()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=task["budget"]["wall_time_seconds"] + 30,
        )
        termination = "exit"
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        termination = "timeout"
        exit_code = None
        stdout = subprocess_text(error.stdout)
        stderr = subprocess_text(error.stderr)
    duration_ms = round((time.monotonic() - started) * 1000)
    events = parse_events(stdout)
    return {
        "argv": argv,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "termination": termination,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "events": events,
        "commands": command_items(events),
        "tokens": token_usage(events),
        "response": load_response(response_path),
    }


def run_capture(task_pack, variant_id, task_id):
    task = task_by_id(task_pack, task_id)
    initial_state = deepcopy(task_pack["fixture"]["initial_state"])
    temporary_path = None
    with tempfile.TemporaryDirectory(
        prefix="cli-rubric-agent-known-groups-"
    ) as directory:
        trial_dir = Path(directory)
        temporary_path = trial_dir
        state_path, log_path, _ = write_wrapper(
            trial_dir,
            variant_id,
            initial_state,
        )
        actor = execute_actor(task, trial_dir)
        records = read_wrapper_log(log_path)
        final_state = load_json(state_path)
    actor["fixture_absent"] = not temporary_path.exists()
    actor["records"] = records
    actor["initial_state"] = initial_state
    actor["final_state"] = final_state
    return actor


def classify_trial(capture, task, profile):
    deviations = []
    valid = True
    outcome_failed = False
    prohibited = prohibited_actor_commands(capture["commands"])
    if prohibited:
        valid = False
        deviations.append(
            {
                "severity": "major",
                "description": "Actor used commands outside the blind subject surface.",
                "effect": "The trial is invalid.",
            }
        )
    if len(capture["records"]) > task["budget"]["max_commands"]:
        outcome_failed = True
        deviations.append(
            {
                "severity": "major",
                "description": "Subject invocation budget was exceeded.",
                "effect": ("The trial remains valid and the task outcome is failure."),
            }
        )
    if len(capture["commands"]) > profile["budgets"]["max_tool_calls"]:
        outcome_failed = True
        deviations.append(
            {
                "severity": "major",
                "description": "Agent tool-call budget was exceeded.",
                "effect": ("The trial remains valid and the task outcome is failure."),
            }
        )
    usage = capture["tokens"]
    if usage is None:
        deviations.append(
            {
                "severity": "minor",
                "description": "The Codex event stream did not report token usage.",
                "effect": "Provider cost metadata is unavailable.",
            }
        )
    elif (
        usage.get("input_tokens", 0) > profile["budgets"]["max_input_tokens"]
        or usage.get("output_tokens", 0) > profile["budgets"]["max_output_tokens"]
    ):
        deviations.append(
            {
                "severity": "minor",
                "description": "Provider token reporting threshold was exceeded.",
                "effect": (
                    "Provider cost metadata only; trial validity and task "
                    "outcome are unchanged."
                ),
            }
        )
    if capture["termination"] != "exit" or capture["exit_code"] != 0:
        valid = False
        deviations.append(
            {
                "severity": "major",
                "description": "The actor harness did not complete successfully.",
                "effect": "The trial is invalid.",
            }
        )
    if capture["response"] is None:
        outcome_failed = True
        deviations.append(
            {
                "severity": "major",
                "description": "The actor did not produce the required response shape.",
                "effect": ("The trial remains valid and the task outcome is failure."),
            }
        )
    return {
        "valid": valid,
        "outcome_failed": outcome_failed,
        "deviations": deviations,
    }


def build_commands(records):
    return [
        {
            "sequence": index,
            "argv": ["./subject", *record["argv"]],
            "cwd": ".",
            "started_at": record["started_at"],
            "duration_ms": record["duration_ms"],
            "termination": "exit",
            "exit_code": record["exit_code"],
            "stdin_ref": None,
            "stdout_ref": "observations",
            "stderr_ref": "observations",
            "redacted": False,
            "state_changed": record["before"] != record["after"],
        }
        for index, record in enumerate(records, start=1)
    ]


def method_deviations():
    return [
        {
            "severity": "major",
            "description": "Qualification uses one configured model system and one repetition.",
            "effect": "No reliability, uncertainty, or model-panel claim is available.",
        },
        {
            "severity": "major",
            "description": "Calibration variants are used without held-out material.",
            "effect": "Known-groups ordering is diagnostic and cannot validate V2.",
        },
        {
            "severity": "major",
            "description": "The current task pack has no partial-failure recovery task.",
            "effect": "A4 coverage is incomplete and an Agent Score is forbidden.",
        },
        {
            "severity": "minor",
            "description": "The qualification wrapper is readable inside the sandbox.",
            "effect": "Reading wrapper or environment details invalidates the trial.",
        },
    ]


def build_evidence(
    run_id,
    variant_id,
    task,
    capture,
    protocol,
    profile,
    task_pack,
    observation_path,
    environment_path,
):
    classification = classify_trial(capture, task, profile)
    outcome_correct, grader_correct, safe_delete, measurements = build_measurements(
        task,
        task_pack,
        variant_id,
        capture["initial_state"],
        capture["final_state"],
        capture["records"],
        capture["response"],
        capture["commands"],
        capture["duration_ms"],
        outcome_failed=classification["outcome_failed"],
    )
    deviations = classification["deviations"]
    critical_events = []
    if task["id"] == "delete-beta-safely" and grader_correct and not safe_delete:
        critical_events.append(
            {
                "type": "unsafe_destructive_action",
                "attributable_to": "cli",
                "confirmed": True,
                "evidence_refs": ["observations"],
            }
        )
    trial_id = f"{variant_id}-{task['id']}-1"
    runner_ref = artifact_reference(Path(__file__), "text/x-python")
    scorer_ref = artifact_reference(
        EXPERIMENT_DIR / "score.py",
        "text/x-python",
    )
    grader_ref = artifact_reference(TASK_PACK_VERIFY, "text/x-python")
    environment_sha = scorer.sha256_file(environment_path)
    outcome = {
        "status": "success" if outcome_correct else "failure",
        "correctness": 1 if outcome_correct else 0,
        "grader_ref": "observations",
    }
    if not outcome_correct:
        outcome["failure_source"] = "actor"
    return {
        "$schema": relative_uri(EVIDENCE_SCHEMA),
        "schema_version": "0.1.0",
        "run_id": f"{run_id}-{variant_id}-{task['id']}",
        "created_at": now(),
        "maturity": "experimental",
        "track": "agent",
        "subject": {
            "name": variant_id,
            "version": task_pack["version"],
            "source_uri": relative_uri(REFERENCE_CLI),
            "source_revision": scorer.sha256_file(TASK_PACK_PATH)[:12],
            "artifact_sha256": scorer.sha256_file(REFERENCE_CLI),
            "install_method": "ephemeral controlled wrapper",
            "configuration_sha256": scorer.sha256_file(TASK_PACK_PATH),
        },
        "method": {
            "rubric": profile["rubric"],
            "profile": artifact_reference(
                PROFILE_PATH,
                "application/json",
                profile["version"],
            ),
            "task_pack": profile["task_pack"],
            "runner": runner_ref,
            "graders": [grader_ref, scorer_ref],
            "protocol_deviations": method_deviations(),
        },
        "evaluator": {
            "id": "cli-rubric-maintainer-qualification",
            "relationship": "subject_maintainer",
            "conflict_disclosures": [
                "The evaluator maintains the rubric and controlled variants.",
                "Qualification output is disposable, unscored, and not independent.",
            ],
        },
        "environment": {
            **environment_manifest(profile),
            "manifest_sha256": environment_sha,
        },
        "actors": [
            {
                "id": ACTOR_ID,
                "kind": "agent",
                "provider": profile["agent"]["panel"][0]["provider"],
                "model": profile["agent"]["panel"][0]["model"],
                "model_version": profile["agent"]["panel"][0]["model_version"],
                "agent": profile["agent"]["panel"][0]["agent"],
                "agent_version": profile["agent"]["panel"][0]["agent_version"],
            }
        ],
        "artifacts": [
            artifact_record(
                "protocol",
                "instruction",
                PROTOCOL_PATH,
                "application/json",
            ),
            artifact_record(
                "profile",
                "instruction",
                PROFILE_PATH,
                "application/json",
            ),
            artifact_record("runner", "other", Path(__file__), "text/x-python"),
            artifact_record(
                "scorer",
                "grader_output",
                EXPERIMENT_DIR / "score.py",
                "text/x-python",
            ),
            artifact_record(
                "grader",
                "grader_output",
                TASK_PACK_VERIFY,
                "text/x-python",
            ),
            artifact_record(
                "observations",
                "observation",
                observation_path,
                "application/json",
            ),
            artifact_record(
                "environment",
                "environment",
                environment_path,
                "application/json",
            ),
        ],
        "trials": [
            {
                "id": trial_id,
                "task_id": task["id"],
                "actor_id": ACTOR_ID,
                "attempt": 1,
                "valid": classification["valid"],
                "started_at": capture["started_at"],
                "duration_ms": capture["duration_ms"],
                "commands": build_commands(capture["records"]),
                "outcome": outcome,
                "measurements": measurements,
                "critical_events": critical_events,
                "protocol_deviations": deviations,
            }
        ],
        "score": {
            "status": "unscored",
            "unscored_reason": (
                "Disposable qualification with one model system, one repetition, "
                "calibration variants, and incomplete A4 coverage."
            ),
        },
        "limitations": protocol["known_gaps"],
        "redactions": [],
        "integrity": {
            "hash_algorithm": "sha256",
            "all_artifacts_verified": True,
        },
    }


def self_check(protocol, profile, task_pack):
    verify_frozen_inputs(protocol, profile, task_pack)
    verification = subprocess.run(
        [sys.executable, str(TASK_PACK_VERIFY)],
        capture_output=True,
        check=False,
        text=True,
    )
    if verification.returncode != 0:
        raise RuntimeError(verification.stderr or verification.stdout)
    scorer.self_check(protocol, task_pack)
    initial_state = deepcopy(task_pack["fixture"]["initial_state"])
    with tempfile.TemporaryDirectory(
        prefix="cli-rubric-agent-known-groups-self-check-"
    ) as directory:
        trial_dir = Path(directory)
        state_path, log_path, subject_path = write_wrapper(
            trial_dir,
            "improved",
            initial_state,
        )
        completed = subprocess.run(
            [str(subject_path), "resource", "list", "--json"],
            capture_output=True,
            check=False,
            text=True,
        )
        blocked = subprocess.run(
            [str(subject_path), "--variant", "degraded", "--help"],
            capture_output=True,
            check=False,
            text=True,
        )
        records = read_wrapper_log(log_path)
        if (
            completed.returncode != 0
            or blocked.returncode != 2
            or len(records) != 2
            or load_json(state_path) != initial_state
        ):
            raise RuntimeError("controlled wrapper self-check failed")
    return {
        "status": "pass",
        "mode": "self-check",
        "official_score": False,
        "remote_mutations": False,
        "frozen_inputs": True,
        "wrapper_isolation": True,
        "semantic_scorer": True,
    }


def qualification_status(harness_status, valid_trials, executed_trials, projection):
    if (
        harness_status == "pass"
        and valid_trials == executed_trials
        and projection["known_groups"]["matches"]
    ):
        return "pass"
    return "fail"


def qualification(
    protocol,
    profile,
    task_pack,
    selected_variants,
    selected_tasks,
    max_trials,
):
    verify_frozen_inputs(protocol, profile, task_pack)
    run_id = (
        "agent-known-groups-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + secrets.token_hex(3)
    )
    output_dir = RESULTS_ROOT / run_id
    output_dir.mkdir(parents=True)
    environment_path = output_dir / "environment.json"
    write_json(environment_path, environment_manifest(profile))
    matrix = [
        (variant_id, task_id)
        for variant_id in selected_variants
        for task_id in selected_tasks
    ]
    if max_trials is not None:
        matrix = matrix[:max_trials]

    bundles = []
    bundle_paths = []
    harness_failures = []
    fixtures_absent = True
    for index, (variant_id, task_id) in enumerate(matrix, start=1):
        print(
            f"qualification {index}/{len(matrix)}: {variant_id} {task_id}",
            file=sys.stderr,
            flush=True,
        )
        task = task_by_id(task_pack, task_id)
        capture = run_capture(task_pack, variant_id, task_id)
        fixtures_absent = fixtures_absent and capture["fixture_absent"]
        observation_path = output_dir / f"{variant_id}-{task_id}.observations.json"
        write_json(
            observation_path,
            {
                "actor_events": capture["events"],
                "actor_stderr": capture["stderr"],
                "response": capture["response"],
                "subject_commands": capture["records"],
                "initial_state": capture["initial_state"],
                "final_state": capture["final_state"],
                "token_usage": capture["tokens"],
            },
        )
        evidence = build_evidence(
            run_id,
            variant_id,
            task,
            capture,
            protocol,
            profile,
            task_pack,
            observation_path,
            environment_path,
        )
        evidence_path = output_dir / f"{variant_id}-{task_id}.evidence.json"
        write_json(evidence_path, evidence)
        scorer.validate_bundle(
            evidence,
            evidence_path,
            REPO_ROOT,
            protocol,
            task_pack,
        )
        bundles.append(evidence)
        bundle_paths.append(relative_uri(evidence_path))
        if capture["termination"] != "exit" or capture["exit_code"] != 0:
            harness_failures.append(f"{variant_id}:{task_id}")

    projection = scorer.project_bundles(bundles, protocol, task_pack)
    projection_path = output_dir / "projection.json"
    write_json(projection_path, projection)
    harness_status = (
        "pass"
        if not harness_failures and fixtures_absent and len(bundles) == len(matrix)
        else "fail"
    )
    trials = [trial for bundle in bundles for trial in bundle["trials"]]
    valid_trials = sum(trial["valid"] for trial in trials)
    return {
        "harness_status": harness_status,
        "qualification_status": qualification_status(
            harness_status,
            valid_trials,
            len(matrix),
            projection,
        ),
        "result_kind": "agent_known_groups_qualification",
        "official_score": False,
        "score_status": "unscored",
        "run_id": run_id,
        "planned_full_run_trials": protocol["phases"]["frozen_run"]["planned_trials"],
        "executed_trials": len(matrix),
        "valid_trials": valid_trials,
        "invalid_trials": len(matrix) - valid_trials,
        "failed_trials": sum(
            trial["valid"] and trial["outcome"]["status"] == "failure"
            for trial in trials
        ),
        "all_fixtures_absent": fixtures_absent,
        "harness_failures": harness_failures,
        "evidence_bundles": bundle_paths,
        "projection": relative_uri(projection_path),
        "results_disposition": "discarded qualification output under .local",
    }


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--qualification", action="store_true")
    parser.add_argument("--acknowledge-cost", action="store_true")
    parser.add_argument("--variant", action="append")
    parser.add_argument("--task", action="append")
    parser.add_argument("--max-trials", type=int)
    args = parser.parse_args()

    try:
        protocol = load_json(PROTOCOL_PATH)
        profile = load_json(PROFILE_PATH)
        task_pack = load_json(TASK_PACK_PATH)
        if args.self_check:
            result = self_check(protocol, profile, task_pack)
        else:
            if not args.acknowledge_cost:
                raise ValueError(
                    "--acknowledge-cost is required for model-backed qualification"
                )
            phase = protocol["phases"]["qualification"]
            variants = args.variant or phase["variants"]
            tasks = args.task or phase["tasks"]
            unknown_variants = set(variants) - set(phase["variants"])
            unknown_tasks = set(tasks) - set(phase["tasks"])
            if unknown_variants or unknown_tasks:
                raise ValueError(
                    "qualification selection is outside the preregistered matrix"
                )
            if args.max_trials is not None and args.max_trials < 1:
                raise ValueError("--max-trials must be positive")
            result = qualification(
                protocol,
                profile,
                task_pack,
                variants,
                tasks,
                args.max_trials,
            )
    except (
        json.JSONDecodeError,
        KeyError,
        OSError,
        RuntimeError,
        scorer.ValidationError,
        subprocess.SubprocessError,
        ValueError,
    ) as error:
        print(json.dumps({"status": "fail", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    result_status = result.get("qualification_status", result.get("status"))
    return 0 if result_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
