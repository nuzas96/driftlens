# DriftLens

FYP: **Development of an Agentic Artificial Intelligence System for Repairing and Validating Detection Rules Affected by Telemetry Changes**

## Phase 1 methodology checkpoint

The Phase 1 pilot uses five SigmaHQ rules and their official regression artifacts pinned to:

`16eb58704e941956d29b1a27da6f967c5525a9bb`

The raw EVTX baseline is already verified **PASS 5/5** using the SigmaHQ-style EVTX path:

**evtx-sigma-checker v0.8.5 + pinned THOR log-source configuration**

The next gate is an independent structured-telemetry baseline using the same JSON evaluation path that will later be reused for controlled telemetry-change experiments.

## Locked Phase 1 implementation order

1. Create repository/folder structure. **Complete**
2. Lock five representative Sigma pilot rules. **Complete**
3. Import authoritative SigmaHQ EVTX/JSON regression artifacts. **Complete**
4. Build deterministic EVTX baseline evaluation harness. **Complete**
5. Verify all five rules against official EVTX positive baselines. **PASS 5/5**
6. Build structured JSON/Sigma baseline evaluation path. **Implemented**
7. Verify all five feasible pilot baselines through the JSON path. **Current gate**
8. Define documented machine-readable controlled telemetry changes.
9. Run paired baseline-versus-change evaluation.
10. Generate affected-rule evidence records.
11. Add agentic AI diagnosis and candidate repair.
12. Independently validate repaired rules and retain human approval evidence.

## EVTX baseline harness

### Install the pinned checker

From PowerShell at the repository root:

```powershell
.\tools\setup_baseline_checker.ps1
```

### Run the EVTX baseline

```powershell
python .\src\baseline_eval.py
```

Verified result:

```text
Overall: PASS (5/5)
```

Evidence:

`results/baseline/baseline_results.json`

## Structured JSON baseline

The JSON baseline uses:

- `sigma-cli==3.1.0`
- `pySigma-backend-golangexpr==1.0.0`
- SigmaHQ `json_matcher v0.0.2`

The matcher release is SHA256-verified in CI.

### Telemetry profile v1

The official SigmaHQ JSON representation stores Windows event detection fields under:

`Event.EventData`

For Phase 1, DriftLens projects those fields into a stable **Sigma logical-field contract** without changing their values:

```text
Event.EventData.CommandLine   -> CommandLine
Event.EventData.Image         -> Image
Event.EventData.TargetObject  -> TargetObject
Event.EventData.Details       -> Details
...
```

Selected system context such as `EventID`, `Channel`, `Computer`, and provider name is retained.

This projection is the baseline telemetry contract, not a drift transformation.

### Run path

The JSON baseline is executed automatically by:

`.github/workflows/json-baseline.yml`

The evaluator:

`src/json_baseline_eval.py`

compiles each original Sigma rule to `golang_expr` and evaluates the canonical event(s) with SigmaHQ `json_matcher`.

Evidence produced by CI:

`results/json_baseline/json_baseline_results.json`

The workflow uploads this report as an artifact; it does **not** automatically commit generated evidence.

## Pilot manifest

`metadata/pilot_manifest.json` is the source of truth for the Phase 1 rule-to-telemetry pairing, expected match counts, pinned upstream commit, and baseline provenance.

## Dataset provenance

- `.evtx`: official SigmaHQ raw regression artifact used for raw baseline execution.
- `.json`: official SigmaHQ structured event representation.
- `info.yml`: upstream SigmaHQ regression metadata.
- Generated telemetry-change variants will be stored separately and must never be described as original SigmaHQ telemetry.

## Scope guard

DriftLens models telemetry/parser/normalization changes as experimental context. Its primary repair target remains the affected **Sigma detection rule/detection content**, consistent with the approved FYP proposal.
