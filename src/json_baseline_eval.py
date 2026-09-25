#!/usr/bin/env python3
"""Validate the locked Phase 1 pilot against official SigmaHQ JSON telemetry."""

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
    to_sigma_logical_event,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "metadata" / "pilot_manifest.json"
DEFAULT_MATCHER = ROOT / "tools" / "bin" / "json_matcher"
DEFAULT_RESULTS = ROOT / "results" / "json_baseline" / "json_baseline_results.json"

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate Phase 1 official JSON baselines")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--matcher", type=Path, default=DEFAULT_MATCHER)
    p.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    return p.parse_args()

def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path

def main() -> int:
    args = parse_args()
    manifest_path = resolve(args.manifest)
    matcher_path = resolve(args.matcher)
    results_path = resolve(args.results)

    try:
        require_file(manifest_path, "Pilot manifest")
        require_file(matcher_path, "SigmaHQ json_matcher")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[PREFLIGHT FAIL] {exc}", file=sys.stderr)
        return 2

    rows: list[dict[str, Any]] = []
    all_pass = True

    print("DriftLens Phase 1 JSON Baseline Evaluation")
    print("=" * 72)
    print(f"Telemetry profile : {PROFILE_ID}")
    print(f"SigmaHQ commit    : {manifest.get('sigmahq_commit')}")
    print(f"Pilot rules       : {len(manifest.get('rules', []))}")
    print()

    for item in manifest.get("rules", []):
        rid = item["id"]
        rule_path = resolve(Path(item["rule_path"]))
        json_path = resolve(Path(item["json_path"]))
        info_path = resolve(Path(item["info_path"]))
        expected = int(item["expected_match_count"])
        try:
            require_file(rule_path, f"Rule {rid}")
            require_file(json_path, f"JSON {rid}")
            require_file(info_path, f"info.yml {rid}")
            source_events = load_json_stream(json_path)
            logical_events = [to_sigma_logical_event(e) for e in source_events]
            expr = compile_rule(rule_path)
            observed, matched_indexes, matcher_lines, logical_sha256 = run_matcher(
                matcher_path, expr, logical_events
            )
            passed = observed == expected
            status = "PASS" if passed else "FAIL"
            all_pass = all_pass and passed
            print(f"[{status}] {item['title']} | expected={expected} observed={observed}")
            rows.append({
                "slug":item["slug"], "title":item["title"], "id":rid,
                "logsource":item["logsource"], "sysmon_event_id":item["sysmon_event_id"],
                "rule_path":item["rule_path"], "json_path":item["json_path"], "info_path":item["info_path"],
                "source_event_count":len(source_events), "expected_match_count":expected,
                "observed_match_count":observed, "matched_event_indexes":matched_indexes,
                "status":status, "compiled_golang_expr":expr, "matcher_output":matcher_lines,
                "rule_sha256":sha256_file(rule_path), "source_json_sha256":sha256_file(json_path),
                "info_sha256":sha256_file(info_path), "logical_event_stream_sha256":logical_sha256,
            })
        except Exception as exc:
            all_pass = False
            print(f"[ERROR] {item.get('title', rid)} | {exc}")
            rows.append({"slug":item.get("slug"),"title":item.get("title"),"id":rid,
                         "expected_match_count":expected,"status":"ERROR","error":str(exc)})

    report = {
        "schema_version":1,
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose":"Phase 1 official JSON baseline verification before telemetry-change experiments",
        "telemetry_profile":{
            "id":PROFILE_ID,
            "source_representation":"SigmaHQ Windows event JSON",
            "projection":"Event.EventData fields -> top-level Sigma logical fields",
            "system_context_retained":["EventID","Channel","Computer","ProviderName"],
            "field_values_modified":False,
        },
        "sigmahq_commit":manifest.get("sigmahq_commit"),
        "tooling":{
            "sigma_cli_version":package_version("sigma-cli"),
            "golangexpr_backend_version":package_version("pysigma-backend-golangexpr"),
            "json_matcher_sha256":sha256_file(matcher_path),
        },
        "overall_status":"PASS" if all_pass else "FAIL",
        "passed_rules":sum(1 for r in rows if r.get("status")=="PASS"),
        "total_rules":len(rows),
        "rules":rows,
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print()
    print("=" * 72)
    print(f"Overall: {report['overall_status']} ({report['passed_rules']}/{report['total_rules']})")
    print(f"Evidence written to: {results_path}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    raise SystemExit(main())
