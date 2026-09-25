from __future__ import annotations

from copy import deepcopy
from typing import Any

from json_eval_core import event_sha256

def apply_transformation(
    event: dict[str, Any],
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    changed = deepcopy(event)
    op = case["operation"]
    field = case.get("source_field")
    before_hash = event_sha256(event)

    evidence: dict[str, Any] = {
        "operation": op,
        "source_field": field,
        "before_event_sha256": before_hash,
    }

    if op == "move_field":
        target = case["target_field"]
        if field not in changed:
            raise ValueError(f"{case['id']}: source field missing: {field}")
        if target in changed:
            raise ValueError(f"{case['id']}: target field already exists: {target}")
        value = changed.pop(field)
        changed[target] = value
        evidence.update({"target_field": target, "old_value": value, "new_value": value})

    elif op == "remove_field":
        if field not in changed:
            raise ValueError(f"{case['id']}: source field missing: {field}")
        old_value = changed.pop(field)
        evidence.update({"removed_value": old_value})

    elif op == "replace_exact_value":
        if field not in changed:
            raise ValueError(f"{case['id']}: source field missing: {field}")
        expected = case["from_value"]
        if changed[field] != expected:
            raise ValueError(
                f"{case['id']}: expected {field}={expected!r}, got {changed[field]!r}"
            )
        changed[field] = case["to_value"]
        evidence.update({"old_value": expected, "new_value": case["to_value"]})

    elif op == "replace_prefix":
        if field not in changed:
            raise ValueError(f"{case['id']}: source field missing: {field}")
        value = changed[field]
        if not isinstance(value, str) or not value.startswith(case["from_prefix"]):
            raise ValueError(
                f"{case['id']}: {field} does not start with {case['from_prefix']!r}"
            )
        new_value = case["to_prefix"] + value[len(case["from_prefix"]):]
        changed[field] = new_value
        evidence.update({"old_value": value, "new_value": new_value})

    else:
        raise ValueError(f"{case['id']}: unsupported operation: {op}")

    evidence["after_event_sha256"] = event_sha256(changed)
    return changed, evidence

def apply_case(
    events: list[dict[str, Any]],
    case: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    changed_events: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        changed, item = apply_transformation(event, case)
        item["event_index"] = index
        changed_events.append(changed)
        evidence.append(item)
    return changed_events, evidence
