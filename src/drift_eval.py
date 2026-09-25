#!/usr/bin/env python3
"""Run the Phase 1 paired baseline-vs-controlled-telemetry-change pilot."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any

from json_eval_core import (
    PROFILE_ID,
    compile_rule,
    load_json_stream,
    package_version,
    require_file,
    run_matcher,
    sha256_file,
    stable_json_bytes,
    to_sigma_logical_event,
)
from telemetry_transform import apply_case
from valid_drift_gate import validate_drift

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "metadata" / "pilot_manifest.json"
DEFAULT_CATALOG = ROOT / "metadata" / "telemetry_changes_v1.json"
DEFAULT_MATCHER = ROOT / "tools" / "bin" / "json_matcher"
DEFAULT_RESULTS = ROOT / "results" / "drift_pilot" / "drift_pilot_results.json"
DEFAULT_VARIANTS = ROOT / "results" / "drift_pilot" / "variants"

def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run DriftLens Phase 1 telemetry-change pilot")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    p.add_argument("--matcher", type=Path, default=DEFAULT_MATCHER)
    p.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--variants-dir", type=Path, default=DEFAULT_VARIANTS)
    return p.parse_args()

def classify(baseline_indexes: list[int], changed_indexes: list[int]) -> tuple[str, list[int], list[int]]:
    baseline = set(baseline_indexes)
    changed = set(changed_indexes)
    lost = sorted(baseline - changed)
    gained = sorted(changed - baseline)
    if lost:
        return "AFFECTED", lost, gained
    if baseline == changed:
        return "UNAFFECTED", lost, gained
    return "DETECTION_SET_CHANGED", lost, gained

def write_variant(path: Path, case: dict[str, Any], events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case["id"],
        "rule_id": case["rule_id"],
        "category": case["category"],
        "baseline_profile": PROFILE_ID,
        "events": events,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")

def main() -> int:
    args = parse_args()
    manifest_path, catalog_path = resolve(args.manifest), resolve(args.catalog)
    matcher_path, results_path = resolve(args.matcher), resolve(args.results)
    variants_dir = resolve(args.variants_dir)

    try:
        require_file(manifest_path, "Pilot manifest")
        require_file(catalog_path, "Telemetry-change catalogue")
        require_file(matcher_path, "SigmaHQ json_matcher")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[PREFLIGHT FAIL] {exc}", file=sys.stderr)
        return 2

    rules = {item["id"]: item for item in manifest["rules"]}
    expr_cache: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    fatal = False

    print("DriftLens Phase 1 Controlled Telemetry-Change Pilot")
    print("=" * 78)
    print(f"Baseline profile : {catalog.get('baseline_profile')}")
    print(f"Catalogue        : {catalog.get('catalog_id')}")
    print(f"Cases            : {len(catalog.get('cases', []))}")
    print()

    for case in catalog.get("cases", []):
        case_id = case["id"]
        rid = case["rule_id"]
        item = rules.get(rid)
        if item is None:
            fatal = True
            rows.append({"case_id":case_id,"status":"ERROR","error":f"rule not in pilot manifest: {rid}"})
            continue

        try:
            rule_path = resolve(Path(item["rule_path"]))
            json_path = resolve(Path(item["json_path"]))
            require_file(rule_path, f"Rule {rid}")
            require_file(json_path, f"JSON {rid}")

            source_events = load_json_stream(json_path)
            baseline_events = [to_sigma_logical_event(e) for e in source_events]
            expr = expr_cache.setdefault(rid, compile_rule(rule_path))

            baseline_count, baseline_idx, baseline_lines, baseline_stream_hash = run_matcher(
                matcher_path, expr, baseline_events
            )
            expected = int(item["expected_match_count"])
            if baseline_count != expected:
                raise RuntimeError(
                    f"baseline gate failed: expected {expected}, observed {baseline_count}"
                )

            changed_events, transform_evidence = apply_case(baseline_events, case)
            gate = validate_drift(baseline_events, changed_events, case, transform_evidence)
            if gate["status"] != "PASS":
                print(f"[INVALID] {case_id} | valid-drift gate failed")
                rows.append({
                    "case_id":case_id, "rule_id":rid, "title":item["title"],
                    "category":case["category"], "status":"INVALID_DRIFT",
                    "gate":gate, "transform_evidence":transform_evidence,
                })
                fatal = True
                continue

            changed_count, changed_idx, changed_lines, changed_stream_hash = run_matcher(
                matcher_path, expr, changed_events
            )
            classification, lost, gained = classify(baseline_idx, changed_idx)
            transitions = [
                {
                    "event_index":i,
                    "baseline":"TP" if i in baseline_idx else "FN",
                    "changed":"TP" if i in changed_idx else "FN",
                }
                for i in range(len(baseline_events))
            ]

            write_variant(variants_dir / f"{case_id}.json", case, changed_events)
            print(
                f"[PASS] {case_id} | {classification} | "
                f"baseline={baseline_count} changed={changed_count}"
            )

            rows.append({
                "case_id":case_id, "rule_id":rid, "title":item["title"],
                "category":case["category"], "operation":case["operation"],
                "hypothesis":case.get("hypothesis"), "grounding":case.get("grounding"),
                "status":"PASS", "classification":classification,
                "expected_baseline_match_count":expected,
                "baseline_match_count":baseline_count, "changed_match_count":changed_count,
                "baseline_matched_event_indexes":baseline_idx,
                "changed_matched_event_indexes":changed_idx,
                "lost_detection_event_indexes":lost, "gained_detection_event_indexes":gained,
                "transitions":transitions, "valid_drift_gate":gate,
                "transform_evidence":transform_evidence,
                "source_json_sha256":sha256_file(json_path),
                "baseline_event_stream_sha256":baseline_stream_hash,
                "changed_event_stream_sha256":changed_stream_hash,
                "baseline_matcher_output":baseline_lines,
                "changed_matcher_output":changed_lines,
            })
        except Exception as exc:
            fatal = True
            print(f"[ERROR] {case_id} | {exc}")
            rows.append({
                "case_id":case_id, "rule_id":rid, "title":item.get("title"),
                "category":case.get("category"), "status":"ERROR", "error":str(exc),
            })

    summary = {
        "affected":sum(1 for r in rows if r.get("classification")=="AFFECTED"),
        "unaffected":sum(1 for r in rows if r.get("classification")=="UNAFFECTED"),
        "detection_set_changed":sum(1 for r in rows if r.get("classification")=="DETECTION_SET_CHANGED"),
        "invalid":sum(1 for r in rows if r.get("status")=="INVALID_DRIFT"),
        "errors":sum(1 for r in rows if r.get("status")=="ERROR"),
    }
    completed = sum(1 for r in rows if r.get("status")=="PASS")
    report = {
        "schema_version":1,
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "catalog_id":catalog.get("catalog_id"),
        "baseline_profile":PROFILE_ID,
        "sigmahq_commit":manifest.get("sigmahq_commit"),
        "tooling":{
            "sigma_cli_version":package_version("sigma-cli"),
            "golangexpr_backend_version":package_version("pysigma-backend-golangexpr"),
            "json_matcher_sha256":sha256_file(matcher_path),
        },
        "overall_status":"PASS" if not fatal and completed==len(catalog.get("cases",[])) else "FAIL",
        "completed_cases":completed,
        "total_cases":len(catalog.get("cases",[])),
        "summary":summary,
        "cases":rows,
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print()
    print("=" * 78)
    print(f"Overall: {report['overall_status']} ({completed}/{report['total_cases']} valid completed cases)")
    print(f"Affected={summary['affected']} Unaffected={summary['unaffected']} Invalid={summary['invalid']} Errors={summary['errors']}")
    print(f"Evidence written to: {results_path}")
    return 0 if report["overall_status"]=="PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
