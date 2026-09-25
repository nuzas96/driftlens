from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

PROFILE_ID = "sigma-logical-fields-v1"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def stable_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def event_sha256(event: dict[str, Any]) -> str:
    return sha256_bytes(stable_json_bytes(event))

def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"{label} is zero bytes: {path}")

def load_json_stream(path: Path) -> list[dict[str, Any]]:
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
    cmd = ["sigma", "convert", "-t", "golang_expr", "--without-pipeline", str(rule_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"sigma convert failed for {rule_path.name}: {(proc.stderr or proc.stdout).strip()}"
        )
    expr = proc.stdout.strip()
    if not expr:
        raise RuntimeError(f"sigma produced an empty expression for {rule_path.name}")
    return expr

def serialize_events_for_matcher(events: list[dict[str, Any]]) -> tuple[str, bytes]:
    if not events:
        raise ValueError("At least one event is required")
    if len(events) == 1:
        serialized = (
            json.dumps(events[0], ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        return "json", serialized
    serialized = "\n".join(
        json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in events
    ).encode("utf-8")
    return "ndjson", serialized

def run_matcher(
    matcher: Path,
    expr: str,
    events: list[dict[str, Any]],
) -> tuple[int, list[int], list[str], str]:
    with tempfile.TemporaryDirectory(prefix="driftlens_json_") as td:
        temp = Path(td)
        test_type, serialized = serialize_events_for_matcher(events)
        event_path = temp / ("event.json" if test_type == "json" else "events.ndjson")
        event_path.write_bytes(serialized)
        cmd = [
            str(matcher), "--event", str(event_path), "--expr", expr, "--test-type", test_type
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"json_matcher failed: {(proc.stderr or proc.stdout).strip()}")
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        matched_indexes: list[int] = []
        if test_type == "json":
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
