#!/usr/bin/env python3
"""Validate the locked Phase 1 pilot against official SigmaHQ JSON telemetry.

Evaluation path:
1. Read the official SigmaHQ JSON representation.
2. Parse one or more concatenated Windows event JSON objects.
3. Project Event.EventData fields into a stable Sigma-logical-field contract.
4. Compile the original Sigma rule with SigmaHQ sigma-cli + golang_expr.
5. Evaluate the canonical JSON event(s) with SigmaHQ json_matcher.
6. Require the observed match count to equal the locked expected count.

This same canonical JSON + Sigma evaluation path is intended to be reused for
later baseline-vs-telemetry-change experiments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "metadata" / "pilot_manifest.json"
DEFAULT_MATCHER = ROOT / "tools" / "bin" / "json_matcher"
DEFAULT_RESULTS = ROOT / "results" / "json_baseline" / "json_baseline_results.json"

PROFILE_ID = "sigma-logical-fields-v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"{label} is zero bytes: {path}")


def load_json_stream(path: Path) -> list[dict[str, Any]]:
    """Parse one or more JSON objects separated only by whitespace.

    SigmaHQ's registry example contains two JSON objects in one file rather
    than a JSON array, so a normal json.load() is not sufficient.
    """
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    idx = 0
    objects: list[dict[str, Any]] = []

    while True:
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break

        obj, end = decoder.raw_decode(text, idx)
        if not isinstance(obj, dict):
            raise ValueError(f"Expected JSON object in {path}, got {type(obj).__name__}")
        objects.append(obj)
        idx = end

    if not objects:
        raise ValueError(f"No JSON events found in {path}")
    return objects


def to_sigma_logical_event(source: dict[str, Any]) -> dict[str, Any]:
    """Project a SigmaHQ Windows event JSON object to the Phase 1 v1 contract.

    The source representation stores detection fields under Event.EventData.
    The v1 contract exposes those fields at the top level with their Sigma
    logical names (CommandLine, Image, TargetFilename, TargetObject, etc.).

    Selected system context is also retained without altering EventData values.
    """
    event = source.get("Event")
    if not isinstance(event, dict):
        raise ValueError("Missing or invalid Event object")

    event_data = event.get("EventData")
    if not isinstance(event_data, dict):
        raise ValueError("Missing or invalid Event.EventData object")

    logical = dict(event_data)

    system = event.get("System")
    if isinstance(system, dict):
        if "EventID" in system:
            logical.setdefault("EventID", system["EventID"])
        if "Channel" in system:
            logical.setdefault("Channel", system["Channel"])
        if "Computer" in system:
            logical.setdefault("Computer", system["Computer"])

        provider = system.get("Provider")
        if isinstance(provider, dict):
            attrs = provider.get("#attributes")
            if isinstance(attrs, dict) and "Name" in attrs:
                logical.setdefault("ProviderName", attrs["Name"])

    return logical


def compile_rule(rule_path: Path) -> str:
    cmd = [
        "sigma",
        "convert",
        "-t",
        "golang_expr",
        "--without-pipeline",
        str(rule_path),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"sigma convert failed for {rule_path.name}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )

    expr = proc.stdout.strip()
    if not expr:
        raise RuntimeError(f"sigma produced an empty expression for {rule_path.name}")
    return expr


def run_matcher(
    matcher: Path,
    expr: str,
    events: list[dict[str, Any]],
) -> tuple[int, list[int], list[str], str]:
    """Run json_matcher and return exact positive match count and indexes."""
    with tempfile.TemporaryDirectory(prefix="driftlens_json_") as td:
        temp = Path(td)

        if len(events) == 1:
            test_type = "json"
            event_path = temp / "event.json"
            serialized = (
                json.dumps(events[0], ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
        else:
            test_type = "ndjson"
            event_path = temp / "events.ndjson"
            serialized = "\n".join(
                json.dumps(e, ensure_ascii=False, separators=(",", ":"))
                for e in events
            ).encode("utf-8")

        event_path.write_bytes(serialized)

        cmd = [
            str(matcher),
            "--event",
            str(event_path),
            "--expr",
            expr,
            "--test-type",
            test_type,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"json_matcher failed: {(proc.stderr or proc.stdout).strip()}"
            )

        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        matched_indexes: list[int] = []

        if test_type == "json":
            # Exact comparison is intentional: NO-MATCH must never be counted.
            if lines == ["MATCH"]:
                matched_indexes = [0]
            elif lines == ["NO-MATCH"]:
                matched_indexes = []
            else:
                raise RuntimeError(f"Unexpected json_matcher output: {lines!r}")
        else:
            for line in lines:
                m = re.fullmatch(r"Line (\d+): (MATCH|NO-MATCH)", line)
                if not m:
                    raise RuntimeError(f"Unexpected json_matcher output line: {line!r}")
                if m.group(2) == "MATCH":
                    matched_indexes.append(int(m.group(1)))

        return len(matched_indexes), matched_indexes, lines, sha256_bytes(serialized)


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


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

            print(
                f"[{status}] {item['title']} | "
                f"expected={expected} observed={observed}"
            )

            rows.append(
                {
                    "slug": item["slug"],
                    "title": item["title"],
                    "id": rid,
                    "logsource": item["logsource"],
                    "sysmon_event_id": item["sysmon_event_id"],
                    "rule_path": item["rule_path"],
                    "json_path": item["json_path"],
                    "info_path": item["info_path"],
                    "source_event_count": len(source_events),
                    "expected_match_count": expected,
                    "observed_match_count": observed,
                    "matched_event_indexes": matched_indexes,
                    "status": status,
                    "compiled_golang_expr": expr,
                    "matcher_output": matcher_lines,
                    "rule_sha256": sha256_file(rule_path),
                    "source_json_sha256": sha256_file(json_path),
                    "info_sha256": sha256_file(info_path),
                    "logical_event_stream_sha256": logical_sha256,
                }
            )
        except Exception as exc:
            all_pass = False
            print(f"[ERROR] {item.get('title', rid)} | {exc}")
            rows.append(
                {
                    "slug": item.get("slug"),
                    "title": item.get("title"),
                    "id": rid,
                    "expected_match_count": expected,
                    "status": "ERROR",
                    "error": str(exc),
                }
            )

    report = {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "Phase 1 official JSON baseline verification before telemetry-change experiments",
        "telemetry_profile": {
            "id": PROFILE_ID,
            "source_representation": "SigmaHQ Windows event JSON",
            "projection": "Event.EventData fields -> top-level Sigma logical fields",
            "system_context_retained": [
                "EventID",
                "Channel",
                "Computer",
                "ProviderName",
            ],
            "field_values_modified": False,
        },
        "sigmahq_commit": manifest.get("sigmahq_commit"),
        "tooling": {
            "sigma_cli_version": package_version("sigma-cli"),
            "golangexpr_backend_version": package_version(
                "pysigma-backend-golangexpr"
            ),
            "json_matcher_sha256": sha256_file(matcher_path),
        },
        "overall_status": "PASS" if all_pass else "FAIL",
        "passed_rules": sum(1 for r in rows if r.get("status") == "PASS"),
        "total_rules": len(rows),
        "rules": rows,
    }

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print(
        f"Overall: {report['overall_status']} "
        f"({report['passed_rules']}/{report['total_rules']})"
    )
    print(f"Evidence written to: {results_path}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
