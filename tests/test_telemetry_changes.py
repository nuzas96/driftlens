from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from telemetry_transform import apply_transformation
from valid_drift_gate import (
    canonical_registry_numeric,
    canonical_registry_path,
    validate_drift,
)

class TransformationTests(unittest.TestCase):
    def test_move_field_preserves_value_and_passes_gate(self):
        before = {"EventID":1,"ProviderName":"Microsoft-Windows-Sysmon","Computer":"x","CommandLine":"abc","Other":"same"}
        case = {"id":"T1","operation":"move_field","source_field":"CommandLine","target_field":"process.command_line"}
        after, evidence = apply_transformation(before, case)
        gate = validate_drift([before],[after],case,[evidence])
        self.assertEqual(gate["status"], "PASS")
        self.assertNotIn("CommandLine", after)
        self.assertEqual(after["process.command_line"], "abc")

    def test_remove_field_passes_gate(self):
        before = {"EventID":1,"ProviderName":"Microsoft-Windows-Sysmon","Computer":"x","CommandLine":"abc","Other":"same"}
        case = {"id":"T2","operation":"remove_field","source_field":"CommandLine"}
        after, evidence = apply_transformation(before, case)
        self.assertEqual(validate_drift([before],[after],case,[evidence])["status"], "PASS")

    def test_registry_numeric_equivalence(self):
        self.assertEqual(canonical_registry_numeric("DWORD (0x00000000)"), 0)
        self.assertEqual(canonical_registry_numeric("0"), 0)
        before = {"EventID":13,"ProviderName":"Microsoft-Windows-Sysmon","Computer":"x","Details":"DWORD (0x00000000)"}
        case = {"id":"T3","operation":"replace_exact_value","source_field":"Details","from_value":"DWORD (0x00000000)","to_value":"0","semantic_equivalence":"registry_numeric"}
        after, evidence = apply_transformation(before, case)
        self.assertEqual(validate_drift([before],[after],case,[evidence])["status"], "PASS")

    def test_registry_hive_alias_equivalence(self):
        a = canonical_registry_path("HKLM\\System\\X")
        b = canonical_registry_path("HKEY_LOCAL_MACHINE\\System\\X")
        self.assertEqual(a.casefold(), b.casefold())

    def test_gate_rejects_unrelated_change(self):
        before = {"EventID":1,"ProviderName":"Microsoft-Windows-Sysmon","Computer":"x","CommandLine":"abc","Other":"same"}
        case = {"id":"T4","operation":"remove_field","source_field":"CommandLine"}
        after, evidence = apply_transformation(before, case)
        after["Other"] = "changed-too"
        self.assertEqual(validate_drift([before],[after],case,[evidence])["status"], "FAIL")

class CatalogueTests(unittest.TestCase):
    def test_phase1_catalogue_shape(self):
        catalog = json.loads((ROOT / "metadata" / "telemetry_changes_v1.json").read_text(encoding="utf-8"))
        cases = catalog["cases"]
        self.assertEqual(len(cases), 15)
        self.assertEqual(len({c["id"] for c in cases}), 15)
        counts = {}
        for case in cases:
            counts[case["category"]] = counts.get(case["category"], 0) + 1
        self.assertEqual(counts, {
            "field_schema_change":5,
            "missing_telemetry":3,
            "value_format_change":2,
            "non_impact_control":5,
        })

if __name__ == "__main__":
    unittest.main()
