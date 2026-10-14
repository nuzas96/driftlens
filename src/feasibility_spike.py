#!/usr/bin/env python3
"""Development-only feasibility spike for DriftLens-X (not held-out evidence).

S1: strong observable-evidence deterministic diagnosis, 15 historical pilot cases.
S2: one scoped FIELD_ALIAS recovery using the existing pinned Sigma/json_matcher.
S3: abstain if critical structured field is absent without an observed equivalent.

NEVER supply transformation labels to the D0 prediction function. They are used
only by the separate development scorer after the prediction is frozen.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import datetime as dt
import json
from pathlib import Path
import sys

import yaml

from json_eval_core import (
    compile_rule, load_json_stream, run_matcher, to_sigma_logical_event
)
from telemetry_transform import apply_case
from valid_drift_gate import canonical_registry_numeric, canonical_registry_path, validate_drift

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "metadata/telemetry_changes_v1.json"
MANIFEST = ROOT / "metadata/pilot_manifest.json"
MATCHER = ROOT / "tools/bin/json_matcher"
OUT = ROOT / "results/feasibility_spike/development_spike.json"

def required_fields(rule_path: Path) -> set[str]:
    rule = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
    detection = rule.get("detection") or {}
    fields = set()
    def walk(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if key != "condition" and not key.startswith("1 of ") and not key.startswith("all of "):
                    if not isinstance(child, (dict, list)) and "|" in key or (
                        not isinstance(child, (dict, list)) and key not in ("timeframe", "condition")
                    ):
                        fields.add(key.split("|", 1)[0])
                walk(child)
        elif isinstance(node, list):
            for x in node:
                walk(x)
    for k, v in detection.items():
        if k not in ("condition", "timeframe"):
            walk(v)
    return fields

def numeric_equal(a, b):
    try:
        return canonical_registry_numeric(a) == canonical_registry_numeric(b)
    except (ValueError, TypeError, OverflowError):
        return False

def path_equal(a, b):
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return (canonical_registry_path(a).casefold() == canonical_registry_path(b).casefold()
            and a != b)

def diagnosis_d0(before_events: list[dict], after_events: list[dict],
                 rule_fields: set[str], observed_impact: str) -> dict:
    """Uses ONLY currently observable before/after snapshots and rule dependencies."""
    if observed_impact == "UNAFFECTED":
        return {"category": "NO_DETECTION_LOSS", "evidence_refs": ["observed_rule_match"]}
    if observed_impact != "AFFECTED":
        return {"category": "INSUFFICIENT_EVIDENCE", "evidence_refs": ["admission_inconclusive"]}
    votes = []
    evidence = []
    for i, (before, after) in enumerate(zip(before_events, after_events)):
        for field in sorted(rule_fields):
            if field not in before:
                continue
            if field not in after:
                matches = [k for k, v in after.items() if k not in before and v == before[field]]
                if len(matches) == 1:
                    votes.append("FIELD_RELOCATION")
                    evidence.append(f"event:{i}:observed_removed:{field}:observed_candidate:{matches[0]}")
                elif not matches:
                    votes.append("ESSENTIAL_FIELD_LOSS")
                    evidence.append(f"event:{i}:observed_missing:{field}")
                else:
                    votes.append("INSUFFICIENT_EVIDENCE")
                    evidence.append(f"event:{i}:multiple_candidates:{field}")
            elif before[field] != after[field]:
                if field in ("Details",) and numeric_equal(before[field], after[field]):
                    votes.append("VALUE_REPRESENTATION")
                    evidence.append(f"event:{i}:typed_registry_value:{field}")
                elif field in ("TargetObject",) and path_equal(before[field], after[field]):
                    votes.append("VALUE_REPRESENTATION")
                    evidence.append(f"event:{i}:registry_hive_alias:{field}")
                else:
                    votes.append("INSUFFICIENT_EVIDENCE")
                    evidence.append(f"event:{i}:unsupported_changed_value:{field}")
    counts = Counter(votes)
    if not counts:
        category = "INSUFFICIENT_EVIDENCE"
    elif len(counts) == 1:
        category = next(iter(counts))
    else:
        category = "INSUFFICIENT_EVIDENCE"  # contradictory evidence: conservative abstention
    return {"category": category, "evidence_refs": evidence}

def apply_alias(changed_events: list[dict], original_field: str, observed_field: str) -> list[dict]:
    """Minimal, scoped non-destructive adapter. Original rule YAML remains untouched."""
    out = deepcopy(changed_events)
    for event in out:
        if observed_field not in event or original_field in event:
            raise ValueError("unsupported/missing/colliding mapping")
        event[original_field] = event.pop(observed_field)
    return out

def run(matcher: Path, output: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    catalog = json.loads(CASES.read_text(encoding="utf-8"))
    by_rule = {x["id"]: x for x in manifest["rules"]}
    expr_cache = {}
    rows = []
    snapshots = {}
    for case in catalog["cases"]:
        rule = by_rule[case["rule_id"]]
        rule_path = ROOT / rule["rule_path"]
        source = load_json_stream(ROOT / rule["json_path"])
        before = [to_sigma_logical_event(e) for e in source]
        after, transformation_evidence = apply_case(before, case)
        valid = validate_drift(before, after, case, transformation_evidence)
        if valid["status"] != "PASS":
            rows.append({"case_id": case["id"], "status": "INVALID_DRIFT"}); continue
        expr = expr_cache.setdefault(case["rule_id"], compile_rule(rule_path))
        _n1, orig_matches, *_ = run_matcher(matcher, expr, before)
        _n2, changed_matches, *_ = run_matcher(matcher, expr, after)
        if set(orig_matches) - set(changed_matches):
            impact = "AFFECTED"
        elif orig_matches == changed_matches:
            impact = "UNAFFECTED"
        else:
            impact = "DETECTION_SET_CHANGED"
        # D0 sees only observed rule, events and measured impact (no case/category/operation).
        prediction = diagnosis_d0(before, after, required_fields(rule_path), impact)
        # Experimental labels are accessed here, after D0 prediction, for DEV-only scoring.
        gold = ("NO_DETECTION_LOSS" if impact == "UNAFFECTED" else
                {"field_schema_change": "FIELD_RELOCATION",
                 "missing_telemetry": "ESSENTIAL_FIELD_LOSS",
                 "value_format_change": "VALUE_REPRESENTATION",
                 "non_impact_control": "NO_DETECTION_LOSS"}.get(case["category"], "UNKNOWN"))
        row = {"case_id": case["id"], "status": "VALID", "impact": impact,
               "d0_prediction": prediction["category"], "dev_expected_category": gold,
               "correct": prediction["category"] == gold,
               "evidence_refs": prediction["evidence_refs"]}
        rows.append(row)
        snapshots[case["id"]] = (before, after, expr, orig_matches, changed_matches)
    valid_rows = [r for r in rows if r.get("status") == "VALID"]
    # S2 actual matcher positive recovery, NOT full benign-safety evaluation.
    before, after, expr, original, changed = snapshots["SC-CERT-01"]
    try:
        adapted = apply_alias(after, "CommandLine", "process.command_line")
        _n, recovered, *_ = run_matcher(matcher, expr, adapted)
        s2 = {"scenario": "SC-CERT-01", "original_positive_indexes": original,
              "changed_positive_indexes": changed, "recovered_positive_indexes": recovered,
              "positive_recovery_pass": bool(set(original) - set(changed))
                                        and set(original).issubset(set(recovered)),
              "unchanged_original_sigma_rule": True,
              "benign_gate": "NOT_RUN_NO_INDEPENDENT_BENIGN_CAPTURE",
              "full_safe_recovery_pass": False}
    except Exception as e:
        s2 = {"scenario": "SC-CERT-01", "positive_recovery_pass": False,
              "error": str(e), "full_safe_recovery_pass": False}
    # S3 no restoration from pre-change values. Under this strict observation rule, abstain.
    miss_before, miss_after, miss_expr, _o, _c = snapshots["MT-CERT-01"]
    candidates = [k for k, v in miss_after[0].items()
                  if k not in miss_before[0] and v == miss_before[0].get("CommandLine")]
    s3 = {"scenario": "MT-CERT-01",
          "source_field_in_current_structured_event": "CommandLine" in miss_after[0],
          "observed_equivalent_candidate_count": len(candidates),
          "decision": "ABSTAIN" if "CommandLine" not in miss_after[0] and not candidates else "REVIEW",
          "historical_baseline_backfill_used": False}
    summary = {
      "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
      "study_stage": "DEVELOPMENT_ONLY_PILOT_NOT_HELDOUT",
      "runner": "pinned_repo_sigma_golangexpr_json_matcher",
      "sample_size": len(catalog["cases"]),
      "valid_scored": len(valid_rows),
      "observed_affected": sum(r["impact"]=="AFFECTED" for r in valid_rows),
      "observed_unaffected": sum(r["impact"]=="UNAFFECTED" for r in valid_rows),
      "d0_correct": sum(r["correct"] for r in valid_rows),
      "d0_accuracy": round(sum(r["correct"] for r in valid_rows)/len(valid_rows), 4) if valid_rows else None,
      "d0_by_gold": {cat: {"n": sum(r["dev_expected_category"]==cat for r in valid_rows),
                            "correct": sum(r["correct"] for r in valid_rows if r["dev_expected_category"]==cat)}
                     for cat in sorted(set(r["dev_expected_category"] for r in valid_rows))},
      "s2": s2, "s3": s3,
      "dataset_feasibility": {
        "rules_in_runtime_pilot_manifest": len(manifest["rules"]),
        "planned_rules": 10,
        "planned_final_base_rule_windows": 200,
        "final_independent_capture_inventory": "NOT_DOCUMENTED_IN_CURRENT_REPO",
        "plan_10_30_200_verified": False,
        "note": "Five verified pilot rule/source paths are not evidence for 10 independent positive captures per rule."
      },
      "limitations": [
        "D0 code/known mappings are informed by previously inspected 15 pilot cases.",
        "Before/after paired evidence is provided to all methods as a declared assumption.",
        "No new source captures or independent held-out windows are scored.",
        "S2 tests positive recovery only; matched provenance-independent benign safety is pending.",
        "No LLM or agentic AI calls were made; no claims about their accuracy."
      ]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "cases": rows},
                                 indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--matcher", type=Path, default=MATCHER)
    p.add_argument("--output", type=Path, default=OUT)
    args = p.parse_args()
    try:
        summary = run(args.matcher, args.output)
        if not summary["s2"]["positive_recovery_pass"]:
            return 3
        if summary["s3"]["decision"] != "ABSTAIN":
            return 4
        return 0
    except Exception as e:
        print(f"FEASIBILITY_SPIKE_ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
