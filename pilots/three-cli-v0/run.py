#!/usr/bin/env python3

import hashlib
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT_DIR = Path(__file__).resolve().parent
PROTOCOL_PATH = PILOT_DIR / "protocol.json"
PROFILE_PATH = PILOT_DIR / "agent-profile.json"
RUBRIC_PATH = ROOT / "docs/RUBRIC-v0.md"
EVIDENCE_SCHEMA_PATH = ROOT / "schemas/v0/evidence.schema.json"
RESULTS_DIR = PILOT_DIR / "results"
SENSITIVE_KEY = re.compile(
    r"(secret|token|password|authorization|cookie|api[_-]?key)",
    re.IGNORECASE,
)
SENSITIVE_TEXT = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]+\b"),
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer\s+)?)[^\s,]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
]


class PilotError(RuntimeError):
    pass


class SubjectBlocked(PilotError):
    pass


def utc_now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sanitize(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SENSITIVE_KEY.search(key) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def sanitize_text(value):
    stripped = value.strip()
    if stripped:
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            return json.dumps(sanitize(parsed), sort_keys=True)

    sanitized = value
    for pattern in SENSITIVE_TEXT:
        sanitized = pattern.sub(
            lambda match: (
                f"{match.group(1)}[REDACTED]" if match.lastindex else "[REDACTED]"
            ),
            sanitized,
        )
    return sanitized


def invoke(argv, environment=None, timeout=60):
    started_at = utc_now()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "argv": argv,
            "started_at": started_at,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "termination": "timeout",
            "exit_code": None,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "",
        }
    return {
        "argv": argv,
        "started_at": started_at,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "termination": "exit",
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def record_command(
    records,
    task_id,
    step_id,
    result,
    *,
    before=None,
    after=None,
    stdout_override=None,
):
    raw_stdout = result["stdout"]
    raw_stderr = result["stderr"]
    sanitized_stdout = sanitize_text(
        raw_stdout if stdout_override is None else stdout_override
    )
    sanitized_stderr = sanitize_text(raw_stderr)
    redacted = (
        sanitized_stdout != (raw_stdout if stdout_override is None else stdout_override)
        or sanitized_stderr != raw_stderr
        or stdout_override is not None
    )
    record = {
        "sequence": len(records) + 1,
        "task_id": task_id,
        "step_id": step_id,
        "argv": result["argv"],
        "cwd": str(ROOT),
        "started_at": result["started_at"],
        "duration_ms": result["duration_ms"],
        "termination": result["termination"],
        "exit_code": result["exit_code"],
        "stdout": sanitized_stdout,
        "stderr": sanitized_stderr,
        "redacted": redacted,
        "state_before": sanitize(before),
        "state_after": sanitize(after),
        "state_changed": before != after
        if before is not None and after is not None
        else False,
    }
    records.append(record)
    return record


def execute(records, task_id, step_id, argv, environment=None, timeout=60):
    result = invoke(argv, environment, timeout)
    record = record_command(records, task_id, step_id, result)
    return result, record


def parse_json_output(result, context):
    if result["exit_code"] != 0:
        raise PilotError(f"{context} failed: {sanitize_text(result['stderr']).strip()}")
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError as error:
        raise PilotError(f"{context} returned invalid JSON: {error}") from error


def error_is_actionable(result):
    message = f"{result['stdout']}\n{result['stderr']}".lower()
    return result["exit_code"] not in {None, 0} and any(
        token in message
        for token in (
            "required",
            "invalid",
            "unknown",
            "usage",
            "must",
            "expected",
            "provide",
        )
    )


def task_result(criteria, required=None):
    required = required or list(criteria)
    return {
        "status": "success" if all(criteria[item] for item in required) else "failure",
        "criteria": criteria,
    }


def gh_state(records, full_name, task_id, step_id):
    result = invoke(
        [
            "gh",
            "repo",
            "view",
            full_name,
            "--json",
            "nameWithOwner,isPrivate,description",
        ]
    )
    if result["exit_code"] == 0:
        state = {"exists": True, "repository": parse_json_output(result, step_id)}
    else:
        message = f"{result['stdout']}\n{result['stderr']}".lower()
        if (
            "could not resolve to a repository" not in message
            and "not found" not in message
        ):
            raise PilotError(
                f"cannot determine GitHub fixture state: "
                f"{sanitize_text(result['stderr']).strip()}"
            )
        state = {"exists": False}
    record_command(records, task_id, step_id, result, before=state, after=state)
    return state


def run_gh(protocol, sandbox_name):
    subject = next(item for item in protocol["subjects"] if item["id"] == "gh")
    records = []
    tasks = {}
    precondition_clear = False
    cleanup = {"attempted": False, "verified_absent": False}
    full_name = None

    try:
        owner_result, _ = execute(
            records,
            "discover-mutation-contract",
            "resolve-owner",
            ["gh", "api", "user", "--jq", ".login"],
        )
        if owner_result["exit_code"] != 0 or not owner_result["stdout"].strip():
            raise SubjectBlocked("GitHub owner could not be resolved")
        owner = owner_result["stdout"].strip()
        full_name = f"{owner}/{sandbox_name}"
        initial = gh_state(
            records,
            full_name,
            "discover-mutation-contract",
            "precondition-state",
        )
        if initial["exists"]:
            raise SubjectBlocked(f"GitHub fixture already exists: {full_name}")
        precondition_clear = True

        create_help, _ = execute(
            records,
            "discover-mutation-contract",
            "create-help",
            ["gh", "repo", "create", "--help"],
        )
        delete_help, _ = execute(
            records,
            "discover-mutation-contract",
            "delete-help",
            ["gh", "repo", "delete", "--help"],
        )
        tasks["discover-mutation-contract"] = task_result(
            {
                "discovery_exit_zero": (
                    create_help["exit_code"] == 0 and delete_help["exit_code"] == 0
                ),
                "mutation_path_identified": "gh repo create" in create_help["stdout"],
                "destructive_path_identified": "gh repo delete"
                in delete_help["stdout"],
            }
        )

        before = gh_state(
            records,
            full_name,
            "reject-invalid-and-recover",
            "state-before-invalid",
        )
        invalid, invalid_record = execute(
            records,
            "reject-invalid-and-recover",
            "invalid-create",
            [
                "gh",
                "repo",
                "create",
                full_name,
                "--description",
                "CLI Rubric disposable pilot fixture",
            ],
        )
        after_invalid = gh_state(
            records,
            full_name,
            "reject-invalid-and-recover",
            "state-after-invalid",
        )
        invalid_record.update(
            {
                "state_before": before,
                "state_after": after_invalid,
                "state_changed": before != after_invalid,
            }
        )
        recover = None
        recover_record = None
        after_recover = after_invalid
        if not after_invalid["exists"]:
            recover, recover_record = execute(
                records,
                "reject-invalid-and-recover",
                "recover-create",
                [
                    "gh",
                    "repo",
                    "create",
                    full_name,
                    "--private",
                    "--description",
                    "CLI Rubric disposable pilot fixture",
                ],
            )
            after_recover = gh_state(
                records,
                full_name,
                "reject-invalid-and-recover",
                "state-after-recovery",
            )
            recover_record.update(
                {
                    "state_before": after_invalid,
                    "state_after": after_recover,
                    "state_changed": after_invalid != after_recover,
                }
            )
        tasks["reject-invalid-and-recover"] = task_result(
            {
                "invalid_nonzero": invalid["exit_code"] not in {None, 0},
                "invalid_preserves_state": before == after_invalid,
                "recovery_success": recover is not None and recover["exit_code"] == 0,
                "created_state_verified": (
                    after_recover.get("exists") is True
                    and after_recover["repository"]["nameWithOwner"] == full_name
                    and after_recover["repository"]["isPrivate"] is True
                ),
                "actionable_error": error_is_actionable(invalid),
            }
        )
        if not after_recover["exists"]:
            raise PilotError("GitHub recovery did not create the exact fixture")

        before_preview = after_recover
        preview, preview_record = execute(
            records,
            "preview-destructive-change",
            "preview-probe",
            ["gh", "repo", "delete", full_name, "--dry-run"],
        )
        after_preview = gh_state(
            records,
            full_name,
            "preview-destructive-change",
            "state-after-preview",
        )
        preview_record.update(
            {
                "state_before": before_preview,
                "state_after": after_preview,
                "state_changed": before_preview != after_preview,
            }
        )
        preview_supported = (
            preview["exit_code"] == 0
            and before_preview == after_preview
            and any(
                token in f"{preview['stdout']} {preview['stderr']}".lower()
                for token in ("dry run", "dry-run", "would delete", "preview")
            )
        )
        tasks["preview-destructive-change"] = task_result(
            {
                "preview_supported": preview_supported,
                "preview_preserves_state": before_preview == after_preview,
            },
            required=["preview_preserves_state"],
        )
        if not after_preview["exists"]:
            raise PilotError("GitHub preview probe removed the fixture")

        confirmation, confirmation_record = execute(
            records,
            "confirm-and-clean-up",
            "confirmation-probe",
            ["gh", "repo", "delete", full_name],
        )
        after_confirmation = gh_state(
            records,
            full_name,
            "confirm-and-clean-up",
            "state-after-confirmation-probe",
        )
        confirmation_record.update(
            {
                "state_before": after_preview,
                "state_after": after_confirmation,
                "state_changed": after_preview != after_confirmation,
            }
        )
        cli_confirmation_required = (
            confirmation["exit_code"] not in {None, 0} and after_confirmation["exists"]
        )

        delete_result = confirmation
        if after_confirmation["exists"]:
            delete_result, delete_record = execute(
                records,
                "confirm-and-clean-up",
                "confirmed-delete",
                ["gh", "repo", "delete", full_name, "--yes"],
            )
            after_delete = gh_state(
                records,
                full_name,
                "confirm-and-clean-up",
                "state-after-delete",
            )
            delete_record.update(
                {
                    "state_before": after_confirmation,
                    "state_after": after_delete,
                    "state_changed": after_confirmation != after_delete,
                }
            )
        else:
            after_delete = after_confirmation

        tasks["confirm-and-clean-up"] = task_result(
            {
                "cli_confirmation_required": cli_confirmation_required,
                "delete_success": delete_result["exit_code"] == 0,
                "deleted_state_verified": not after_delete["exists"],
            },
            required=["delete_success", "deleted_state_verified"],
        )
        cleanup["verified_absent"] = not after_delete["exists"]
    finally:
        if precondition_clear and full_name:
            residual = gh_state(
                records,
                full_name,
                "confirm-and-clean-up",
                "cleanup-precheck",
            )
            if residual["exists"]:
                cleanup["attempted"] = True
                execute(
                    records,
                    "confirm-and-clean-up",
                    "emergency-cleanup",
                    ["gh", "repo", "delete", full_name, "--yes"],
                )
            final_state = gh_state(
                records,
                full_name,
                "confirm-and-clean-up",
                "cleanup-final-state",
            )
            cleanup["verified_absent"] = not final_state["exists"]

    if not cleanup["verified_absent"]:
        raise PilotError(f"GitHub cleanup failed for {full_name}")
    return {
        "subject": subject,
        "status": "complete",
        "sandbox": {"repository": full_name},
        "tasks": tasks,
        "commands": records,
        "cleanup": cleanup,
    }


def dify_state(records, environment, task_id, step_id):
    result = invoke(
        ["difyctl", "config", "get", "defaults.limit"],
        environment,
    )
    state = {
        "exit_code": result["exit_code"],
        "value": result["stdout"].strip(),
        "error": sanitize_text(result["stderr"]).strip(),
    }
    record_command(records, task_id, step_id, result, before=state, after=state)
    return state


def path_is_within(path, root):
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def run_difyctl(protocol, sandbox_name):
    del sandbox_name
    subject = next(item for item in protocol["subjects"] if item["id"] == "difyctl")
    records = []
    tasks = {}
    temporary_path = None

    with tempfile.TemporaryDirectory(prefix="cli-rubric-difyctl-") as directory:
        temporary_path = Path(directory)
        environment = os.environ.copy()
        environment["DIFY_CONFIG_DIR"] = str(temporary_path)

        path_result, _ = execute(
            records,
            "discover-mutation-contract",
            "resolve-config-path",
            ["difyctl", "config", "path"],
            environment,
        )
        if path_result["exit_code"] != 0:
            raise SubjectBlocked("difyctl could not resolve its config path")
        resolved_path = Path(path_result["stdout"].strip())
        if not path_is_within(resolved_path, temporary_path):
            raise SubjectBlocked(
                f"difyctl config path escaped the temporary root: {resolved_path}"
            )

        set_help, _ = execute(
            records,
            "discover-mutation-contract",
            "set-help",
            ["difyctl", "config", "set", "--help"],
            environment,
        )
        unset_help, _ = execute(
            records,
            "discover-mutation-contract",
            "unset-help",
            ["difyctl", "config", "unset", "--help"],
            environment,
        )
        tasks["discover-mutation-contract"] = task_result(
            {
                "discovery_exit_zero": (
                    set_help["exit_code"] == 0 and unset_help["exit_code"] == 0
                ),
                "mutation_path_identified": "config set" in set_help["stdout"],
                "destructive_path_identified": "config unset" in unset_help["stdout"],
            }
        )

        initial = dify_state(
            records,
            environment,
            "reject-invalid-and-recover",
            "state-before-invalid",
        )
        invalid, invalid_record = execute(
            records,
            "reject-invalid-and-recover",
            "invalid-set",
            ["difyctl", "config", "set", "defaults.limit", "not-an-integer"],
            environment,
        )
        after_invalid = dify_state(
            records,
            environment,
            "reject-invalid-and-recover",
            "state-after-invalid",
        )
        invalid_record.update(
            {
                "state_before": initial,
                "state_after": after_invalid,
                "state_changed": initial != after_invalid,
            }
        )
        recover, recover_record = execute(
            records,
            "reject-invalid-and-recover",
            "recover-set",
            ["difyctl", "config", "set", "defaults.limit", "37"],
            environment,
        )
        after_recover = dify_state(
            records,
            environment,
            "reject-invalid-and-recover",
            "state-after-recovery",
        )
        recover_record.update(
            {
                "state_before": after_invalid,
                "state_after": after_recover,
                "state_changed": after_invalid != after_recover,
            }
        )
        tasks["reject-invalid-and-recover"] = task_result(
            {
                "invalid_nonzero": invalid["exit_code"] not in {None, 0},
                "invalid_preserves_state": initial == after_invalid,
                "recovery_success": recover["exit_code"] == 0,
                "created_state_verified": (
                    after_recover["exit_code"] == 0
                    and after_recover["value"].strip('"') == "37"
                ),
                "actionable_error": error_is_actionable(invalid),
            }
        )

        preview, preview_record = execute(
            records,
            "preview-destructive-change",
            "preview-probe",
            [
                "difyctl",
                "config",
                "unset",
                "defaults.limit",
                "--dry-run",
            ],
            environment,
        )
        after_preview = dify_state(
            records,
            environment,
            "preview-destructive-change",
            "state-after-preview",
        )
        preview_record.update(
            {
                "state_before": after_recover,
                "state_after": after_preview,
                "state_changed": after_recover != after_preview,
            }
        )
        tasks["preview-destructive-change"] = task_result(
            {
                "preview_supported": (
                    preview["exit_code"] == 0
                    and after_preview == after_recover
                    and any(
                        token in f"{preview['stdout']} {preview['stderr']}".lower()
                        for token in ("dry run", "dry-run", "would unset", "preview")
                    )
                ),
                "preview_preserves_state": after_preview == after_recover,
            },
            required=["preview_preserves_state"],
        )

        _confirmation, confirmation_record = execute(
            records,
            "confirm-and-clean-up",
            "confirmation-probe",
            [
                "difyctl",
                "config",
                "unset",
                "defaults.limit",
                "--yes",
            ],
            environment,
        )
        after_confirmation = dify_state(
            records,
            environment,
            "confirm-and-clean-up",
            "state-after-confirmation-probe",
        )
        confirmation_record.update(
            {
                "state_before": after_preview,
                "state_after": after_confirmation,
                "state_changed": after_preview != after_confirmation,
            }
        )
        commit, commit_record = execute(
            records,
            "confirm-and-clean-up",
            "commit-unset",
            ["difyctl", "config", "unset", "defaults.limit"],
            environment,
        )
        after_delete = dify_state(
            records,
            environment,
            "confirm-and-clean-up",
            "state-after-delete",
        )
        commit_record.update(
            {
                "state_before": after_confirmation,
                "state_after": after_delete,
                "state_changed": after_confirmation != after_delete,
            }
        )
        tasks["confirm-and-clean-up"] = task_result(
            {
                "cli_confirmation_required": False,
                "delete_success": commit["exit_code"] == 0,
                "deleted_state_verified": after_delete == initial,
            },
            required=["delete_success", "deleted_state_verified"],
        )

    if temporary_path is None or temporary_path.exists():
        raise PilotError("difyctl temporary config cleanup failed")
    return {
        "subject": subject,
        "status": "complete",
        "sandbox": {"kind": "temporary-config-dir"},
        "tasks": tasks,
        "commands": records,
        "cleanup": {"attempted": True, "verified_absent": True},
    }


def channel_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("channels", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    raise PilotError("awirectl channel list has an unsupported JSON shape")


def awire_state(records, sandbox_name, task_id, step_id):
    samples = []
    stable_state = None
    stable_count = 0
    for index in range(9):
        result = invoke(["awirectl", "channels", "list", "-o", "json"])
        data = parse_json_output(result, f"{step_id}-sample-{index + 1}")
        matches = []
        for item in channel_list(data):
            if isinstance(item, dict) and item.get("name") == sandbox_name:
                matches.append(
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "webhook_url": item.get("webhook_url"),
                    }
                )
        state = {"matching_channels": matches}
        samples.append(state)
        record_command(
            records,
            task_id,
            f"{step_id}-sample-{index + 1}",
            result,
            before=state,
            after=state,
            stdout_override=json.dumps(state, sort_keys=True),
        )
        if state == stable_state:
            stable_count += 1
        else:
            stable_state = state
            stable_count = 1
        if stable_count == 3:
            return state
        if index < 8:
            time.sleep(0.25)
    counts = [len(state["matching_channels"]) for state in samples]
    raise SubjectBlocked(
        f"Awire state oracle did not converge to three matching samples: {counts}"
    )


def awire_channel_state(
    records,
    sandbox_name,
    channel_id,
    task_id,
    step_id,
    *,
    expected_exists,
):
    observed = []
    argv = [
        "awirectl",
        "channels",
        "get",
        "--id",
        channel_id,
        "-o",
        "json",
    ]
    for index in range(9):
        result = invoke(argv)
        if result["exit_code"] == 0:
            data = parse_json_output(result, f"{step_id}-sample-{index + 1}")
            channel = data.get("channel") if isinstance(data, dict) else None
            if not isinstance(channel, dict):
                raise PilotError("awirectl channel get has an unsupported JSON shape")
            state = {
                "matching_channels": [
                    {
                        "id": channel.get("id"),
                        "name": channel.get("name"),
                        "webhook_url": channel.get("webhook_url"),
                    }
                ]
            }
            if channel.get("id") != channel_id or channel.get("name") != sandbox_name:
                raise PilotError("awirectl channel get returned the wrong fixture")
        else:
            message = f"{result['stdout']}\n{result['stderr']}".lower()
            if "http 404" not in message and "channel not found" not in message:
                raise PilotError(
                    f"cannot determine Awire fixture state: "
                    f"{sanitize_text(result['stderr']).strip()}"
                )
            state = {"matching_channels": []}

        record_command(
            records,
            task_id,
            f"{step_id}-sample-{index + 1}",
            result,
            before=state,
            after=state,
            stdout_override=json.dumps(state, sort_keys=True),
        )
        exists = bool(state["matching_channels"])
        observed.append(exists)
        if exists == expected_exists:
            return state
        if index < 8:
            time.sleep(0.25)

    expectation = "present" if expected_exists else "absent"
    raise SubjectBlocked(
        f"Awire channel get did not observe fixture {expectation}: {observed}"
    )


def find_channel_id(value, sandbox_name):
    if isinstance(value, dict):
        if value.get("name") == sandbox_name and value.get("id"):
            return value["id"]
        for item in value.values():
            found = find_channel_id(item, sandbox_name)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = find_channel_id(item, sandbox_name)
            if found:
                return found
    return None


def run_awirectl(protocol, sandbox_name):
    subject = next(item for item in protocol["subjects"] if item["id"] == "awirectl")
    records = []
    tasks = {}
    created_id = None
    precondition_clear = False
    cleanup = {"attempted": False, "verified_absent": False}
    run_error = None
    cleanup_error = None

    try:
        initial = awire_state(
            records,
            sandbox_name,
            "discover-mutation-contract",
            "precondition-state",
        )
        if initial["matching_channels"]:
            raise SubjectBlocked(f"Awire fixture already exists: {sandbox_name}")
        precondition_clear = True

        create_contract, _ = execute(
            records,
            "discover-mutation-contract",
            "create-contract",
            ["awirectl", "commands", "show", "channels", "create", "--json"],
        )
        delete_contract, _ = execute(
            records,
            "discover-mutation-contract",
            "delete-contract",
            ["awirectl", "commands", "show", "channels", "delete", "--json"],
        )
        tasks["discover-mutation-contract"] = task_result(
            {
                "discovery_exit_zero": (
                    create_contract["exit_code"] == 0
                    and delete_contract["exit_code"] == 0
                ),
                "mutation_path_identified": (
                    '"method": "POST"' in create_contract["stdout"]
                    or '"method":"POST"' in create_contract["stdout"]
                ),
                "destructive_path_identified": (
                    '"method": "DELETE"' in delete_contract["stdout"]
                    or '"method":"DELETE"' in delete_contract["stdout"]
                ),
            }
        )

        before = awire_state(
            records,
            sandbox_name,
            "reject-invalid-and-recover",
            "state-before-invalid",
        )
        invalid, invalid_record = execute(
            records,
            "reject-invalid-and-recover",
            "invalid-create",
            ["awirectl", "channels", "create", "--definitely-invalid"],
        )
        after_invalid = awire_state(
            records,
            sandbox_name,
            "reject-invalid-and-recover",
            "state-after-invalid",
        )
        invalid_record.update(
            {
                "state_before": before,
                "state_after": after_invalid,
                "state_changed": before != after_invalid,
            }
        )
        recover, recover_record = execute(
            records,
            "reject-invalid-and-recover",
            "recover-create",
            [
                "awirectl",
                "channels",
                "create",
                "--set",
                f"name={sandbox_name}",
                "--set",
                f"webhook_url=https://example.invalid/{sandbox_name}",
                "-o",
                "json",
            ],
        )
        if recover["exit_code"] == 0:
            try:
                created_id = find_channel_id(
                    json.loads(recover["stdout"]),
                    sandbox_name,
                )
            except json.JSONDecodeError:
                pass
        if created_id:
            after_recover = awire_channel_state(
                records,
                sandbox_name,
                created_id,
                "reject-invalid-and-recover",
                "state-after-recovery",
                expected_exists=True,
            )
        else:
            after_recover = awire_state(
                records,
                sandbox_name,
                "reject-invalid-and-recover",
                "state-after-recovery",
            )
        recover_record.update(
            {
                "state_before": after_invalid,
                "state_after": after_recover,
                "state_changed": after_invalid != after_recover,
            }
        )
        if len(after_recover["matching_channels"]) == 1:
            created_id = after_recover["matching_channels"][0]["id"]
        tasks["reject-invalid-and-recover"] = task_result(
            {
                "invalid_nonzero": invalid["exit_code"] not in {None, 0},
                "invalid_preserves_state": before == after_invalid,
                "recovery_success": recover["exit_code"] == 0,
                "created_state_verified": bool(created_id),
                "actionable_error": error_is_actionable(invalid),
            }
        )
        if not created_id:
            raise PilotError("Awire recovery did not create one exact fixture")

        preview, preview_record = execute(
            records,
            "preview-destructive-change",
            "preview-probe",
            [
                "awirectl",
                "channels",
                "delete",
                "--id",
                created_id,
                "--dry-run",
            ],
        )
        after_preview = awire_channel_state(
            records,
            sandbox_name,
            created_id,
            "preview-destructive-change",
            "state-after-preview",
            expected_exists=True,
        )
        preview_record.update(
            {
                "state_before": after_recover,
                "state_after": after_preview,
                "state_changed": after_recover != after_preview,
            }
        )
        tasks["preview-destructive-change"] = task_result(
            {
                "preview_supported": (
                    preview["exit_code"] == 0
                    and after_preview == after_recover
                    and any(
                        token in f"{preview['stdout']} {preview['stderr']}".lower()
                        for token in ("dry run", "dry-run", "would delete", "preview")
                    )
                ),
                "preview_preserves_state": after_preview == after_recover,
            },
            required=["preview_preserves_state"],
        )

        _confirmation, confirmation_record = execute(
            records,
            "confirm-and-clean-up",
            "confirmation-probe",
            [
                "awirectl",
                "channels",
                "delete",
                "--id",
                created_id,
                "--yes",
            ],
        )
        after_confirmation = awire_channel_state(
            records,
            sandbox_name,
            created_id,
            "confirm-and-clean-up",
            "state-after-confirmation-probe",
            expected_exists=True,
        )
        confirmation_record.update(
            {
                "state_before": after_preview,
                "state_after": after_confirmation,
                "state_changed": after_preview != after_confirmation,
            }
        )

        commit, commit_record = execute(
            records,
            "confirm-and-clean-up",
            "commit-delete",
            [
                "awirectl",
                "channels",
                "delete",
                "--id",
                created_id,
                "-o",
                "json",
            ],
        )
        after_delete = awire_channel_state(
            records,
            sandbox_name,
            created_id,
            "confirm-and-clean-up",
            "state-after-delete",
            expected_exists=False,
        )
        commit_record.update(
            {
                "state_before": after_confirmation,
                "state_after": after_delete,
                "state_changed": after_confirmation != after_delete,
            }
        )
        tasks["confirm-and-clean-up"] = task_result(
            {
                "cli_confirmation_required": False,
                "delete_success": commit["exit_code"] == 0,
                "deleted_state_verified": not after_delete["matching_channels"],
            },
            required=["delete_success", "deleted_state_verified"],
        )
        cleanup["verified_absent"] = not after_delete["matching_channels"]
    except (OSError, PilotError, ValueError) as error:
        run_error = error
    finally:
        if precondition_clear:
            try:
                cleanup_id = created_id
                if cleanup_id is None:
                    residual = awire_state(
                        records,
                        sandbox_name,
                        "confirm-and-clean-up",
                        "cleanup-precheck",
                    )
                    if len(residual["matching_channels"]) == 1:
                        cleanup_id = residual["matching_channels"][0]["id"]
                if cleanup_id:
                    cleanup["attempted"] = True
                    execute(
                        records,
                        "confirm-and-clean-up",
                        "emergency-cleanup",
                        [
                            "awirectl",
                            "channels",
                            "delete",
                            "--id",
                            cleanup_id,
                            "-o",
                            "json",
                        ],
                    )
                if cleanup_id:
                    final_state = awire_channel_state(
                        records,
                        sandbox_name,
                        cleanup_id,
                        "confirm-and-clean-up",
                        "cleanup-final-state",
                        expected_exists=False,
                    )
                else:
                    final_state = awire_state(
                        records,
                        sandbox_name,
                        "confirm-and-clean-up",
                        "cleanup-final-state",
                    )
                cleanup["verified_absent"] = not final_state["matching_channels"]
            except (OSError, PilotError, ValueError) as error:
                cleanup_error = error

    error = cleanup_error or run_error
    if error is not None or not cleanup["verified_absent"]:
        if error is None:
            error = PilotError(f"Awire cleanup failed for channel {created_id}")
        tasks["protocol-execution"] = {
            "status": "failure",
            "criteria": {"protocol_executed": False},
        }
        return {
            "subject": subject,
            "status": "blocked" if isinstance(error, SubjectBlocked) else "failed",
            "sandbox": {"channel_name": sandbox_name, "channel_id": created_id},
            "tasks": tasks,
            "commands": records,
            "cleanup": cleanup,
            "error": sanitize_text(str(error)),
        }
    return {
        "subject": subject,
        "status": "complete",
        "sandbox": {"channel_name": sandbox_name, "channel_id": created_id},
        "tasks": tasks,
        "commands": records,
        "cleanup": cleanup,
    }


def verify_frozen_inputs(protocol, profile):
    if protocol["result_kind"] != "real_cli_pilot_rehearsal":
        raise PilotError("unexpected protocol result kind")
    if protocol["official_score"] is not False:
        raise PilotError("pilot protocol must forbid an official score")
    if profile["track"] != "agent":
        raise PilotError("pilot profile must remain agent-only")
    if profile["safety"]["production_credentials"] is not False:
        raise PilotError("profile safety contract changed")

    expected = {
        PROFILE_PATH: None,
        PROTOCOL_PATH: profile["task_pack"]["sha256"],
        RUBRIC_PATH: profile["rubric"]["sha256"],
    }
    for path, digest in expected.items():
        if not path.is_file():
            raise PilotError(f"missing frozen input: {path}")
        if digest is not None and sha256_file(path) != digest:
            raise PilotError(f"frozen input digest mismatch: {path}")

    for subject in protocol["subjects"]:
        path = Path(subject["path"])
        if not path.is_file():
            raise PilotError(f"subject binary is missing: {path}")
        if sha256_file(path) != subject["artifact_sha256"]:
            raise PilotError(f"subject artifact digest mismatch: {subject['id']}")


def environment_manifest(run_id):
    return {
        "run_id": run_id,
        "os": f"macOS {platform.mac_ver()[0]}",
        "architecture": platform.machine(),
        "shell": "zsh 5.9",
        "locale": os.environ.get("LC_ALL") or os.environ.get("LANG") or "unknown",
        "timezone": "America/New_York",
        "isolation": (
            "exact remote fixture names for gh and awirectl; "
            "TemporaryDirectory plus DIFY_CONFIG_DIR for difyctl"
        ),
        "network": "allowlisted real service endpoints",
        "cwd": str(ROOT),
    }


def artifact(path, artifact_id, role, root):
    return {
        "id": artifact_id,
        "role": role,
        "uri": str(path.relative_to(root)),
        "media_type": (
            "application/json" if path.suffix == ".json" else "text/x-python"
        ),
        "byte_length": path.stat().st_size,
        "sha256": sha256_file(path),
        "redacted": artifact_id == "observations",
    }


def artifact_reference(path, root, version=None):
    value = {
        "uri": str(path.relative_to(root)),
        "sha256": sha256_file(path),
        "media_type": (
            "application/json"
            if path.suffix == ".json"
            else "text/markdown"
            if path.suffix == ".md"
            else "text/x-python"
        ),
    }
    if version:
        value["version"] = version
    return value


def deviation(description, effect, severity="major"):
    return {
        "severity": severity,
        "description": description,
        "effect": effect,
    }


def construct_for(criterion):
    if criterion.startswith("discovery") or "path_identified" in criterion:
        return "A2"
    if "state_verified" in criterion or "preserves_state" in criterion:
        return "A3"
    if any(
        token in criterion
        for token in ("invalid", "recovery", "preview", "confirmation", "delete")
    ):
        return "A4"
    return "A1"


def evidence_commands(records):
    commands = []
    for record in records:
        command = {
            "sequence": record["sequence"],
            "argv": record["argv"],
            "cwd": record["cwd"],
            "started_at": record["started_at"],
            "duration_ms": record["duration_ms"],
            "termination": record["termination"],
            "stdin_ref": None,
            "stdout_ref": "observations",
            "stderr_ref": "observations",
            "redacted": record["redacted"],
            "state_changed": record["state_changed"],
        }
        if record["termination"] == "exit":
            command["exit_code"] = record["exit_code"]
        commands.append(command)
    return commands


def build_trials(subject_result, actor_id):
    trials = []
    records = subject_result["commands"]
    for task_id, result in subject_result["tasks"].items():
        task_records = [item for item in records if item["task_id"] == task_id]
        criteria = result["criteria"]
        measurements = [
            {
                "construct_id": construct_for(criterion),
                "measure_id": criterion,
                "raw_value": value,
                "unit": "boolean",
                "normalized_value": 1 if value else 0,
                "source": "deterministic",
                "evidence_refs": ["observations"],
            }
            for criterion, value in criteria.items()
        ]
        if not measurements:
            measurements = [
                {
                    "construct_id": "A1",
                    "measure_id": "protocol_executed",
                    "raw_value": False,
                    "unit": "boolean",
                    "normalized_value": 0,
                    "source": "deterministic",
                    "evidence_refs": ["observations"],
                }
            ]
        started_at = (
            task_records[0]["started_at"]
            if task_records
            else subject_result["started_at"]
        )
        trial = {
            "id": f"{subject_result['subject']['id']}-{task_id}-1",
            "task_id": task_id,
            "actor_id": actor_id,
            "attempt": 1,
            "valid": True,
            "started_at": started_at,
            "duration_ms": sum(item["duration_ms"] for item in task_records),
            "commands": evidence_commands(task_records),
            "outcome": {
                "status": result["status"],
                "correctness": 1 if result["status"] == "success" else 0,
                "grader_ref": "observations",
            },
            "measurements": measurements,
            "critical_events": [],
            "protocol_deviations": [],
        }
        if result["status"] != "success":
            trial["outcome"]["failure_source"] = "cli"
        trials.append(trial)
    return trials


def build_evidence(
    run_id,
    subject_result,
    observations_path,
    environment_path,
    environment,
    created_at,
):
    subject = subject_result["subject"]
    actor_id = "openai-codex-session"
    protocol_deviations = [
        deviation(
            "The acting agent inspected every subject before execution.",
            "Discovery and first-use behavior are not valid Agent Core observations.",
        ),
        deviation(
            "Only one model session and one repetition were used.",
            "No repeatability, uncertainty, or generalized Agent claim is available.",
        ),
        deviation(
            "The runner executed adapters selected during protocol design.",
            "The run tests instrumentation and CLI behavior, not autonomous command selection.",
        ),
        deviation(
            "GitHub and Awire used production-scoped credentials against exact disposable fixtures.",
            "The run violates the profile safety requirement and must remain unscored.",
        ),
    ]
    relationship = (
        "subject_maintainer" if subject["id"] == "awirectl" else "commissioned"
    )
    conflict_disclosures = [
        "This run was performed in a maintainer-controlled workspace.",
        "The result is experimental, unscored, and not independently reproduced.",
    ]
    if subject["id"] == "awirectl":
        conflict_disclosures.append(
            "awirectl is generated by Lathe and evaluated by the same project owner."
        )

    subject_value = {
        "name": subject["id"],
        "version": subject["version"],
        "source_uri": subject["source_uri"],
        "artifact_sha256": subject["artifact_sha256"],
        "install_method": f"preinstalled binary at {subject['path']}",
    }
    if subject.get("source_revision"):
        subject_value["source_revision"] = subject["source_revision"]

    runner_path = Path(__file__).resolve()
    artifacts = [
        artifact(PROTOCOL_PATH, "protocol", "instruction", ROOT),
        artifact(PROFILE_PATH, "profile", "instruction", ROOT),
        artifact(runner_path, "runner", "other", ROOT),
        artifact(observations_path, "observations", "observation", ROOT),
        artifact(environment_path, "environment", "environment", ROOT),
    ]
    evidence = {
        "$schema": "https://raw.githubusercontent.com/lathe-cli/cli-rubric/main/schemas/v0/evidence.schema.json",
        "schema_version": "0.1.0",
        "run_id": f"{run_id}-{subject['id']}",
        "created_at": created_at,
        "maturity": "experimental",
        "track": "agent",
        "subject": subject_value,
        "method": {
            "rubric": artifact_reference(RUBRIC_PATH, ROOT, "0.1.0"),
            "profile": artifact_reference(PROFILE_PATH, ROOT, "0.1.0"),
            "task_pack": artifact_reference(PROTOCOL_PATH, ROOT, "0.1.0"),
            "runner": artifact_reference(runner_path, ROOT),
            "graders": [artifact_reference(runner_path, ROOT)],
            "protocol_deviations": protocol_deviations,
        },
        "evaluator": {
            "id": "cli-rubric-maintainer-pilot",
            "relationship": relationship,
            "conflict_disclosures": conflict_disclosures,
        },
        "environment": {
            "os": environment["os"],
            "architecture": environment["architecture"],
            "shell": environment["shell"],
            "terminal": "non-interactive subprocess",
            "locale": environment["locale"],
            "timezone": environment["timezone"],
            "isolation": environment["isolation"],
            "network": environment["network"],
            "manifest_sha256": sha256_file(environment_path),
        },
        "actors": [
            {
                "id": actor_id,
                "kind": "agent",
                "provider": "OpenAI",
                "model": "GPT-5",
                "model_version": "session-unreported",
                "agent": "Codex Desktop",
                "agent_version": "session-unreported",
            }
        ],
        "artifacts": artifacts,
        "trials": build_trials(subject_result, actor_id),
        "score": {
            "status": "unscored",
            "unscored_reason": (
                "Protocol rehearsal with one exposed agent session, one repetition, "
                "fixed adapters, and production-scoped credential deviations."
            ),
        },
        "limitations": [
            "No Human Track participants were run.",
            "No clean-history Agent trial was run.",
            "The three capability domains are not directly comparable.",
            "Preview support is observed as a criterion and is not synthesized by the runner.",
            "No score, band, ranking, or uncertainty interval is produced.",
        ],
        "redactions": [
            {
                "scope": (
                    "Secret-like JSON fields and token-shaped strings; unrelated "
                    "Awire channel list entries."
                ),
                "reason": "Prevent credential, signing-secret, and unrelated resource disclosure.",
                "effect_on_reproducibility": (
                    "Outcome and exact fixture state remain reproducible; unrelated "
                    "resource metadata and secret values are unavailable."
                ),
            }
        ],
        "integrity": {
            "hash_algorithm": "sha256",
            "all_artifacts_verified": True,
        },
    }
    return evidence


def failed_subject(subject, error, started_at):
    task_id = "protocol-execution"
    return {
        "subject": subject,
        "status": "blocked" if isinstance(error, SubjectBlocked) else "failed",
        "started_at": started_at,
        "sandbox": {},
        "tasks": {
            task_id: {
                "status": "failure",
                "criteria": {"protocol_executed": False},
            }
        },
        "commands": [],
        "cleanup": {"attempted": False, "verified_absent": False},
        "error": sanitize_text(str(error)),
    }


def self_check():
    protocol = load_json(PROTOCOL_PATH)
    profile = load_json(PROFILE_PATH)
    verify_frozen_inputs(protocol, profile)
    if sanitize({"token": "secret-value"}) != {"token": "[REDACTED]"}:
        raise PilotError("structured secret redaction failed")
    if "[REDACTED]" not in sanitize_text("token=gho_exampletoken"):
        raise PilotError("token-shaped text redaction failed")

    temporary_path = None
    with tempfile.TemporaryDirectory(prefix="cli-rubric-difyctl-check-") as directory:
        temporary_path = Path(directory)
        environment = os.environ.copy()
        environment["DIFY_CONFIG_DIR"] = str(temporary_path)
        result = invoke(["difyctl", "config", "path"], environment)
        if result["exit_code"] != 0:
            raise PilotError("difyctl config path self-check failed")
        if not path_is_within(Path(result["stdout"].strip()), temporary_path):
            raise PilotError("difyctl ignores the temporary config root")
    if temporary_path is None or temporary_path.exists():
        raise PilotError("temporary config self-check cleanup failed")

    print(
        json.dumps(
            {
                "status": "pass",
                "mode": "self-check",
                "remote_mutations": False,
                "frozen_inputs": True,
                "secret_redaction": True,
                "difyctl_isolation": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main():
    started_at = utc_now()
    run_id = datetime.now(UTC).strftime(
        "three-cli-%Y%m%dT%H%M%SZ-"
    ) + secrets.token_hex(2)
    sandbox_name = datetime.now(UTC).strftime(
        "cli-rubric-pilot-%Y%m%d-"
    ) + secrets.token_hex(3)
    result_dir = RESULTS_DIR / run_id
    protocol = load_json(PROTOCOL_PATH)
    profile = load_json(PROFILE_PATH)
    verify_frozen_inputs(protocol, profile)

    subject_runners = {
        "gh": run_gh,
        "difyctl": run_difyctl,
        "awirectl": run_awirectl,
    }
    subject_results = {}
    for subject in protocol["subjects"]:
        subject_started = utc_now()
        try:
            result = subject_runners[subject["id"]](protocol, sandbox_name)
            result["started_at"] = subject_started
        except (
            json.JSONDecodeError,
            OSError,
            PilotError,
            subprocess.SubprocessError,
            ValueError,
        ) as error:
            result = failed_subject(subject, error, subject_started)
        subject_results[subject["id"]] = result

    completed_at = utc_now()
    environment = environment_manifest(run_id)
    environment_path = result_dir / "environment.json"
    write_json(environment_path, environment)

    observations = {
        "run_id": run_id,
        "created_at": started_at,
        "completed_at": completed_at,
        "result_kind": protocol["result_kind"],
        "official_score": False,
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "profile_sha256": sha256_file(PROFILE_PATH),
        "subjects": subject_results,
        "comparison": {
            "status": "not_directly_comparable",
            "reason": "Subjects use matched task archetypes across different capability domains.",
        },
    }
    observations_path = result_dir / "observations.json"
    write_json(observations_path, observations)

    evidence_paths = []
    for subject_id, subject_result in subject_results.items():
        evidence = build_evidence(
            run_id,
            subject_result,
            observations_path,
            environment_path,
            environment,
            completed_at,
        )
        evidence_path = result_dir / f"{subject_id}.evidence.json"
        write_json(evidence_path, evidence)
        evidence_paths.append(evidence_path)

    fixtures_absent = all(
        result["cleanup"]["verified_absent"] for result in subject_results.values()
    )
    subjects_complete = all(
        result["status"] == "complete" for result in subject_results.values()
    )
    summary = {
        "status": "pass" if subjects_complete and fixtures_absent else "fail",
        "result_kind": protocol["result_kind"],
        "official_score": False,
        "score_status": "unscored",
        "run_id": run_id,
        "subjects": {
            subject_id: {
                "status": result["status"],
                "cleanup_verified": result["cleanup"]["verified_absent"],
                "criteria": {
                    task_id: task["criteria"]
                    for task_id, task in result["tasks"].items()
                },
                **({"error": result["error"]} if result.get("error") else {}),
            }
            for subject_id, result in subject_results.items()
        },
        "all_fixtures_absent": fixtures_absent,
        "evidence_dir": str(result_dir.relative_to(ROOT)),
        "evidence_manifests": [str(path.relative_to(ROOT)) for path in evidence_paths],
    }
    write_json(result_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        raise SystemExit(self_check())
    if sys.argv[1:]:
        raise SystemExit("usage: run.py [--self-check]")
    raise SystemExit(main())
