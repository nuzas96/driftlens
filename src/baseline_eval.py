#!/usr/bin/env python3
"""Deterministic Phase 1 positive-baseline evaluator for DriftLens.

This harness deliberately mirrors the EVTX path used by SigmaHQ regression
testing: evtx-sigma-checker + the THOR log-source configuration. It stages each
locked rule beside its paired official EVTX artifact, runs the checker once,
then counts only matches where RuleId and EVTX filename stem both equal the
locked Sigma rule ID.

No external Python packages are required.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "metadata" / "pilot_manifest.json"
DEFAULT_CHECKER = ROOT / "tools" / "bin" / "evtx-sigma-checker.exe"
DEFAULT_THOR = ROOT / "config" / "thor.yml"
DEFAULT_RESULTS = ROOT / "results" / "baseline" / "baseline_results.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify DriftLens Phase 1 positive baselines")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    p.add_argument("--thor-config", type=Path, default=DEFAULT_THOR)
    p.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--timeout", type=int, default=600)
    return p.parse_args()


def rel_or_abs(path_value: str) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else ROOT / p


def filename_stem_any_platform(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    return os.path.splitext(name)[0]


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"{label} is zero bytes: {path}")


def preflight(manifest: dict[str, Any], checker: Path, thor: Path) -> list[dict[str, Any]]:
    require_file(checker, "evtx-sigma-checker")
    require_file(thor, "THOR config")

    expected_checker_hash = (
        manifest.get("evtx_checker", {}).get("windows_sha256", "").strip().lower()
    )
    actual_checker_hash = sha256_file(checker)
    if expected_checker_hash and actual_checker_hash != expected_checker_hash:
        raise ValueError(
            "evtx-sigma-checker SHA256 mismatch. "
            f"Expected {expected_checker_hash}, got {actual_checker_hash}"
        )

    prepared: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in manifest.get("rules", []):
        rid = item["id"]
        if rid in seen_ids:
            raise ValueError(f"Duplicate rule ID in manifest: {rid}")
        seen_ids.add(rid)

        rule_path = rel_or_abs(item["rule_path"])
        evtx_path = rel_or_abs(item["evtx_path"])
        json_path = rel_or_abs(item["json_path"])
        info_path = rel_or_abs(item["info_path"])

        require_file(rule_path, f"Rule {rid}")
        require_file(evtx_path, f"EVTX {rid}")
        require_file(json_path, f"JSON {rid}")
        require_file(info_path, f"info.yml {rid}")

        if evtx_path.stem != rid:
            raise ValueError(
                f"EVTX filename must equal rule ID: {evtx_path.name} vs {rid}"
            )

        # Lightweight consistency checks without adding a YAML dependency.
        rule_text = rule_path.read_text(encoding="utf-8")
        info_text = info_path.read_text(encoding="utf-8")
        if f"id: {rid}" not in rule_text:
            raise ValueError(f"Rule file does not contain expected ID {rid}: {rule_path}")
        if f"id: {rid}" not in info_text:
            raise ValueError(f"info.yml does not reference expected ID {rid}: {info_path}")

        prepared.append(
            {
                **item,
                "_rule_path": rule_path,
                "_evtx_path": evtx_path,
                "_json_path": json_path,
                "_info_path": info_path,
                "_rule_sha256": sha256_file(rule_path),
                "_evtx_sha256": sha256_file(evtx_path),
                "_json_sha256": sha256_file(json_path),
                "_info_sha256": sha256_file(info_path),
            }
        )

    if not prepared:
        raise ValueError("Manifest contains no pilot rules")

    return prepared


def run_checker(
    prepared: list[dict[str, Any]],
    checker: Path,
    thor: Path,
    timeout: int,
) -> tuple[subprocess.CompletedProcess[str], dict[str, list[dict[str, Any]]], list[str]]:
    with tempfile.TemporaryDirectory(prefix="driftlens_baseline_") as td:
        temp_root = Path(td)
        rules_dir = temp_root / "rules"
        evtx_dir = temp_root / "evtx"
        rules_dir.mkdir()
        evtx_dir.mkdir()

        for item in prepared:
            rid = item["id"]
            shutil.copy2(item["_rule_path"], rules_dir / f"{rid}.yml")
            shutil.copy2(item["_evtx_path"], evtx_dir / f"{rid}.evtx")

        cmd = [
            str(checker),
            "--log-source",
            str(thor),
            "--evtx-path",
            str(evtx_dir),
            "--rule-level",
            "informational",
            "--rule-path",
            str(rules_dir),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        matches: dict[str, list[dict[str, Any]]] = {}
        non_json_stdout: list[str] = []

        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                non_json_stdout.append(line)
                continue

            rid = obj.get("RuleId")
            evtx_stem = filename_stem_any_platform(str(obj.get("File", "")))
            if rid and evtx_stem == rid:
                matches.setdefault(rid, []).append(obj)

        return result, matches, non_json_stdout


def serializable_item(item: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def main() -> int:
    args = parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    checker = args.checker if args.checker.is_absolute() else ROOT / args.checker
    thor = args.thor_config if args.thor_config.is_absolute() else ROOT / args.thor_config
    results_path = args.results if args.results.is_absolute() else ROOT / args.results

    require_file(manifest_path, "Pilot manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    try:
        prepared = preflight(manifest, checker, thor)
    except Exception as exc:
        print(f"[PREFLIGHT FAIL] {exc}", file=sys.stderr)
        return 2

    print("DriftLens Phase 1 Baseline Evaluation")
    print("=" * 68)
    print(f"SigmaHQ commit : {manifest.get('sigmahq_commit')}")
    print(f"Checker        : {manifest.get('evtx_checker', {}).get('version')}")
    print(f"Pilot rules    : {len(prepared)}")
    print()

    try:
        proc, matches, non_json_stdout = run_checker(
            prepared, checker, thor, args.timeout
        )
    except subprocess.TimeoutExpired:
        print(f"[FAIL] evtx-sigma-checker timed out after {args.timeout}s", file=sys.stderr)
        return 3

    if proc.returncode != 0:
        print(f"[FAIL] evtx-sigma-checker exited with code {proc.returncode}", file=sys.stderr)
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        return 4

    rows: list[dict[str, Any]] = []
    all_pass = True

    for item in prepared:
        rid = item["id"]
        expected = int(item["expected_match_count"])
        observed = len(matches.get(rid, []))

        # SigmaHQ regression semantics: fewer than expected is a failure;
        # more than expected is a warning.
        passed = observed >= expected
        warning = observed > expected
        if not passed:
            all_pass = False

        if passed and warning:
            status = "PASS_WITH_WARNING"
        elif passed:
            status = "PASS"
        else:
            status = "FAIL"

        print(
            f"[{status}] {item['title']} | "
            f"expected={expected} observed={observed}"
        )

        rows.append(
            {
                **serializable_item(item),
                "observed_match_count": observed,
                "status": status,
                "rule_sha256": item["_rule_sha256"],
                "evtx_sha256": item["_evtx_sha256"],
                "json_sha256": item["_json_sha256"],
                "info_sha256": item["_info_sha256"],
                "match_records": matches.get(rid, []),
            }
        )

    report = {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": manifest.get("purpose"),
        "sigmahq_commit": manifest.get("sigmahq_commit"),
        "checker": {
            **manifest.get("evtx_checker", {}),
            "local_sha256": sha256_file(checker),
        },
        "thor_config": {
            "path": str(thor.relative_to(ROOT)) if thor.is_relative_to(ROOT) else str(thor),
            "sha256": sha256_file(thor),
            "source": manifest.get("thor_config_source"),
        },
        "overall_status": "PASS" if all_pass else "FAIL",
        "passed_rules": sum(1 for r in rows if r["status"].startswith("PASS")),
        "total_rules": len(rows),
        "rules": rows,
        "checker_stderr": proc.stderr.splitlines(),
        "non_json_stdout": non_json_stdout,
    }

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print()
    print("=" * 68)
    print(f"Overall: {report['overall_status']} ({report['passed_rules']}/{report['total_rules']})")
    print(f"Evidence written to: {results_path}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
