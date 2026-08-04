#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path


def state_path():
    value = os.environ.get("CLI_RUBRIC_STATE")
    if not value:
        raise RuntimeError("CLI_RUBRIC_STATE is required")
    return Path(value)


def load_state():
    return json.loads(state_path().read_text())


def save_state(state):
    path = state_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def find_resource(state, resource_id):
    return next(
        (item for item in state["resources"] if item["id"] == resource_id),
        None,
    )


def emit(variant, payload, plain):
    if variant == "improved":
        print(json.dumps(payload, sort_keys=True))
    else:
        print(plain)
    return 0


def fail(variant, code, message, hint):
    if variant == "degraded":
        print("no")
        return 0
    if variant == "neutral":
        print("error: request failed", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "hint": hint,
                }
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 2


def parse_labels(values):
    labels = {}
    for value in values:
        if "=" not in value:
            raise ValueError("labels must use key=value")
        key, label_value = value.split("=", 1)
        if not key or not label_value:
            raise ValueError("labels must use non-empty key=value")
        labels[key] = label_value
    return labels


def parse_options(args):
    values = {}
    labels = []
    flags = set()
    index = 0
    value_flags = {"--id", "--name", "--status", "--label"}
    boolean_flags = {"--json", "--dry-run", "--force", "--yes"}

    while index < len(args):
        token = args[index]
        if token in boolean_flags:
            flags.add(token)
            index += 1
            continue
        if token not in value_flags or index + 1 >= len(args):
            raise ValueError(f"invalid option: {token}")
        value = args[index + 1]
        if token == "--label":
            labels.append(value)
        else:
            values[token] = value
        index += 2

    values["--labels"] = parse_labels(labels)
    return values, flags


def list_resources(variant):
    state = load_state()
    resources = sorted(state["resources"], key=lambda item: item["id"])
    if variant == "degraded":
        plain = " ".join(item["id"] for item in resources)
    else:
        plain = "\n".join(
            f"{item['id']} {item['name']} {item['status']} "
            f"{json.dumps(item['labels'], sort_keys=True)}"
            for item in resources
        )
    return emit(variant, {"resources": resources}, plain)


def show_resource(variant, resource_id):
    state = load_state()
    resource = find_resource(state, resource_id)
    if resource is None:
        return fail(
            variant,
            "resource_not_found",
            f"resource {resource_id} does not exist",
            "List resources and choose an existing identifier.",
        )
    if variant == "degraded":
        plain = resource["name"]
    else:
        plain = (
            f"{resource['id']} {resource['name']} {resource['status']} "
            f"{json.dumps(resource['labels'], sort_keys=True)}"
        )
    return emit(variant, {"resource": resource}, plain)


def create_resource(variant, resource_id, name, status, labels):
    if not resource_id or not name or not status:
        return fail(
            variant,
            "missing_required_field",
            "id, name, and status are required",
            "Provide --id, --name, and --status, then retry.",
        )

    state = load_state()
    if find_resource(state, resource_id) is not None:
        return fail(
            variant,
            "resource_exists",
            f"resource {resource_id} already exists",
            "Choose a new identifier or update the existing resource.",
        )

    resource = {
        "id": resource_id,
        "name": name,
        "status": status,
        "labels": labels,
    }
    state["resources"].append(resource)
    state["resources"].sort(key=lambda item: item["id"])
    save_state(state)
    return emit(
        variant,
        {"action": "create", "resource": resource},
        f"created {resource_id}",
    )


def update_resource(variant, resource_id, status, labels):
    state = load_state()
    resource = find_resource(state, resource_id)
    if resource is None:
        return fail(
            variant,
            "resource_not_found",
            f"resource {resource_id} does not exist",
            "List resources and choose an existing identifier.",
        )
    if not status:
        return fail(
            variant,
            "missing_required_field",
            "status is required",
            "Provide --status, then retry.",
        )

    resource["status"] = status
    resource["labels"].update(labels)
    save_state(state)
    return emit(
        variant,
        {"action": "update", "resource": resource},
        f"updated {resource_id}",
    )


def delete_resource(variant, resource_id, preview, confirmed):
    state = load_state()
    resource = find_resource(state, resource_id)
    if resource is None:
        return fail(
            variant,
            "resource_not_found",
            f"resource {resource_id} does not exist",
            "List resources and choose an existing identifier.",
        )

    if variant == "improved" and preview:
        return emit(
            variant,
            {"action": "delete", "dry_run": True, "resource": resource},
            f"would delete {resource_id}",
        )
    if variant == "neutral" and preview:
        return fail(
            variant,
            "unsupported_option",
            "preview is not supported",
            "Use --force to delete immediately.",
        )
    if variant == "improved" and not confirmed:
        return fail(
            variant,
            "confirmation_required",
            "deletion requires confirmation",
            "Run with --dry-run first, then repeat with --yes.",
        )
    if variant == "neutral" and not confirmed:
        return fail(
            variant,
            "confirmation_required",
            "deletion requires confirmation",
            "Repeat with --force.",
        )

    state["resources"] = [
        item for item in state["resources"] if item["id"] != resource_id
    ]
    save_state(state)
    return emit(
        variant,
        {"action": "delete", "deleted": resource_id},
        f"deleted {resource_id}",
    )


def run_degraded(args):
    if not args:
        return fail("degraded", "unknown_command", "missing command", "Use lsr.")

    command = args[0]
    if command == "lsr":
        return list_resources("degraded")
    if command == "get" and len(args) >= 2:
        return show_resource("degraded", args[1])
    if command == "mk":
        resource_id = args[1] if len(args) > 1 else ""
        name = args[2] if len(args) > 2 else ""
        status = args[3] if len(args) > 3 else ""
        try:
            labels = parse_labels(args[4:])
        except ValueError:
            labels = {}
        return create_resource("degraded", resource_id, name, status, labels)
    if command == "set":
        resource_id = args[1] if len(args) > 1 else ""
        status = args[2] if len(args) > 2 else ""
        try:
            labels = parse_labels(args[3:])
        except ValueError:
            labels = {}
        return update_resource("degraded", resource_id, status, labels)
    if command == "rm" and len(args) >= 2:
        return delete_resource("degraded", args[1], False, True)
    return fail(
        "degraded",
        "unknown_command",
        "unknown command",
        "Use lsr, get, mk, set, or rm.",
    )


def run_standard(variant, args):
    if args == ["--help"]:
        print(
            "resource list\n"
            "resource show ID\n"
            "resource create OPTIONS\n"
            "resource update ID OPTIONS\n"
            "resource delete ID OPTIONS"
        )
        return 0
    if len(args) < 2 or args[0] != "resource":
        return fail(
            variant,
            "unknown_command",
            "expected a resource command",
            "Use resource list, show, create, update, or delete.",
        )

    command = args[1]
    rest = args[2:]
    if command == "list":
        return list_resources(variant)
    if command == "show" and rest:
        return show_resource(variant, rest[0])

    positional = []
    option_args = rest
    if command in {"update", "delete"} and rest:
        positional = [rest[0]]
        option_args = rest[1:]

    try:
        options, flags = parse_options(option_args)
    except ValueError as error:
        return fail(
            variant,
            "invalid_option",
            str(error),
            "Inspect command help and correct the option.",
        )

    if command == "create":
        return create_resource(
            variant,
            options.get("--id", ""),
            options.get("--name", ""),
            options.get("--status", ""),
            options["--labels"],
        )
    if command == "update" and positional:
        return update_resource(
            variant,
            positional[0],
            options.get("--status", ""),
            options["--labels"],
        )
    if command == "delete" and positional:
        confirmed = "--yes" in flags if variant == "improved" else "--force" in flags
        return delete_resource(
            variant,
            positional[0],
            "--dry-run" in flags,
            confirmed,
        )
    return fail(
        variant,
        "unknown_command",
        f"unknown resource command: {command}",
        "Use resource list, show, create, update, or delete.",
    )


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--variant":
        print("usage: reference_cli.py --variant VARIANT COMMAND...", file=sys.stderr)
        return 2

    variant = sys.argv[2]
    args = sys.argv[3:]
    if variant == "degraded":
        return run_degraded(args)
    if variant in {"neutral", "improved"}:
        return run_standard(variant, args)
    print(f"unknown variant: {variant}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
