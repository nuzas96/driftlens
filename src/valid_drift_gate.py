from __future__ import annotations

import re
from typing import Any

from json_eval_core import event_sha256

ANCHORS = ("EventID", "ProviderName", "Computer")

def event_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    removed = sorted(before_keys - after_keys)
    added = sorted(after_keys - before_keys)
    changed = {
        key: {"before": before[key], "after": after[key]}
        for key in sorted(before_keys & after_keys)
        if before[key] != after[key]
    }
    return {"removed": removed, "added": added, "changed": changed}

def canonical_registry_numeric(value: Any) -> int:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Unsupported registry numeric representation: {value!r}")
    value = value.strip()
    m = re.fullmatch(r"DWORD \(0x([0-9A-Fa-f]+)\)", value)
    if m:
        return int(m.group(1), 16)
    if re.fullmatch(r"[+-]?\d+", value):
        return int(value, 10)
    raise ValueError(f"Unsupported registry numeric representation: {value!r}")

def canonical_registry_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Registry path must be a string: {value!r}")
    aliases = {
        "HKLM\\": "HKEY_LOCAL_MACHINE\\",
        "HKEY_LOCAL_MACHINE\\": "HKEY_LOCAL_MACHINE\\",
    }
    upper = value.upper()
    for prefix, canonical in aliases.items():
        if upper.startswith(prefix):
            return canonical + value[len(prefix):]
    return value

def semantic_equivalent(before: Any, after: Any, kind: str | None) -> bool:
    if kind is None:
        return before == after
    if kind == "registry_numeric":
        return canonical_registry_numeric(before) == canonical_registry_numeric(after)
    if kind == "registry_hive_alias":
        return canonical_registry_path(before).casefold() == canonical_registry_path(after).casefold()
    raise ValueError(f"Unsupported semantic equivalence kind: {kind}")

def validate_drift(
    baseline_events: list[dict[str, Any]],
    changed_events: list[dict[str, Any]],
    case: dict[str, Any],
    transform_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    issues: list[str] = []
    event_results: list[dict[str, Any]] = []

    if len(baseline_events) != len(changed_events):
        issues.append(
            f"event count changed: {len(baseline_events)} -> {len(changed_events)}"
        )

    if len(transform_evidence) != len(baseline_events):
        issues.append("transformation evidence count does not match baseline event count")

    for idx, (before, after) in enumerate(zip(baseline_events, changed_events)):
        local: list[str] = []
        diff = event_diff(before, after)
        op = case["operation"]
        field = case.get("source_field")

        for anchor in ANCHORS:
            if before.get(anchor) != after.get(anchor):
                local.append(f"activity anchor changed: {anchor}")

        if op == "move_field":
            target = case["target_field"]
            if diff["removed"] != [field]:
                local.append(f"unexpected removed fields: {diff['removed']}")
            if diff["added"] != [target]:
                local.append(f"unexpected added fields: {diff['added']}")
            if diff["changed"]:
                local.append(f"unexpected value changes: {sorted(diff['changed'])}")
            if before.get(field) != after.get(target):
                local.append("moved field value was not preserved exactly")

        elif op == "remove_field":
            if diff["removed"] != [field]:
                local.append(f"unexpected removed fields: {diff['removed']}")
            if diff["added"]:
                local.append(f"unexpected added fields: {diff['added']}")
            if diff["changed"]:
                local.append(f"unexpected value changes: {sorted(diff['changed'])}")

        elif op in {"replace_exact_value", "replace_prefix"}:
            if diff["removed"] or diff["added"]:
                local.append("value-format change altered field set")
            if sorted(diff["changed"]) != [field]:
                local.append(f"unexpected changed fields: {sorted(diff['changed'])}")
            if field in before and field in after:
                try:
                    if not semantic_equivalent(
                        before[field], after[field], case.get("semantic_equivalence")
                    ):
                        local.append("before/after values are not semantically equivalent")
                except ValueError as exc:
                    local.append(str(exc))
        else:
            local.append(f"unsupported operation: {op}")

        if idx < len(transform_evidence):
            ev = transform_evidence[idx]
            if ev.get("before_event_sha256") != event_sha256(before):
                local.append("before-event hash does not match transformation evidence")
            if ev.get("after_event_sha256") != event_sha256(after):
                local.append("after-event hash does not match transformation evidence")

        event_results.append(
            {
                "event_index": idx,
                "status": "PASS" if not local else "FAIL",
                "issues": local,
                "diff": diff,
                "before_event_sha256": event_sha256(before),
                "after_event_sha256": event_sha256(after),
            }
        )
        issues.extend(f"event {idx}: {msg}" for msg in local)

    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
        "events": event_results,
    }
