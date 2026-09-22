# DriftLens

FYP: **Development of an Agentic Artificial Intelligence System for Repairing and Validating Detection Rules Affected by Telemetry Changes**

## Phase 1 methodology checkpoint

The Phase 1 pilot uses five SigmaHQ rules and their official regression artifacts pinned to:

`16eb58704e941956d29b1a27da6f967c5525a9bb`

Baseline evaluation follows the same EVTX execution path documented by SigmaHQ regression testing: **evtx-sigma-checker + THOR log-source configuration**.

## Locked Phase 1 implementation order

1. Create repository/folder structure. **Complete**
2. Lock five representative Sigma pilot rules. **Complete**
3. Import authoritative SigmaHQ EVTX/JSON regression artifacts. **Complete**
4. Build deterministic baseline evaluation harness. **Implemented**
5. Prove all five rules match their official positive baseline telemetry. **Next run**
6. Define machine-readable controlled drift transformations.
7. Run paired baseline-versus-drift evaluation.
8. Generate affected-rule evidence records.
9. Add agentic AI diagnosis and candidate repair.
10. Independently validate repaired rules and retain human approval evidence.

## Baseline harness

### 1. Install the pinned checker

From PowerShell at the repository root:

```powershell
.\tools\setup_baseline_checker.ps1
```

The setup script downloads **evtx-sigma-checker v0.8.5** for Windows and verifies its SHA256 before use.

### 2. Run the baseline evaluation

```powershell
python .\src\baseline_eval.py
```

Expected Phase 1 result:

```text
Overall: PASS (5/5)
```

The machine-readable evidence report is written to:

`results/baseline/baseline_results.json`

## Pilot manifest

`metadata/pilot_manifest.json` is the source of truth for the Phase 1 rule-to-telemetry pairing, expected match counts, pinned upstream commit, and checker version/hash.

## Dataset provenance

- `.evtx`: official SigmaHQ raw regression artifact used for baseline execution.
- `.json`: official SigmaHQ event representation retained for inspection and later controlled transformation work.
- `info.yml`: upstream SigmaHQ regression metadata.
- Controlled drift variants will be stored separately and must never be described as original SigmaHQ telemetry.
