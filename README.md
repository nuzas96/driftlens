# DriftLens

FYP: **Development of an Agentic Artificial Intelligence System for Repairing and Validating Detection Rules Affected by Telemetry Changes**

## Current Phase 1 checkpoint

The five-rule pilot is pinned to SigmaHQ commit:

`16eb58704e941956d29b1a27da6f967c5525a9bb`

Verified baselines:

- Raw EVTX baseline: **PASS 5/5**
- Structured JSON baseline: **PASS 5/5**

The JSON path uses `sigma-cli==3.1.0`, `pySigma-backend-golangexpr==1.0.0`, and SHA256-verified SigmaHQ `json_matcher v0.0.2`.

## Phase 1 flow

```text
Official SigmaHQ EVTX / JSON
        ↓
Sigma logical-field baseline profile
        ↓
Verified baseline
        ↓
Documented controlled telemetry change
        ↓
Valid-drift gate
        ↓
Same original Sigma rule + same evaluator
        ↓
Baseline TP vs changed-telemetry result
        ↓
Affected / Unaffected evidence
```

AI diagnosis and repair deliberately come **after** affected-rule evidence exists.

## Controlled telemetry-change catalogue

`metadata/telemetry_changes_v1.json` contains 15 paired pilot cases:

- 5 field/schema changes
- 3 missing-telemetry cases
- 2 value-format/representation changes
- 5 non-impact controls

Cases are not pre-labelled as affected. Classification is measured:

- baseline TP → changed FN after a valid transformation = **AFFECTED**
- baseline TP → changed TP after a valid transformation = **UNAFFECTED**
- valid-drift gate failure = **INVALID_DRIFT** and cannot support an affected-rule claim

The catalogue uses documented field/value representations where appropriate (Sigma mappings, ECS, and Microsoft ASIM) and keeps the raw SigmaHQ source artifacts unchanged.

## Core implementation

- `src/json_eval_core.py` — shared Sigma JSON evaluation path
- `src/json_baseline_eval.py` — structured baseline verifier
- `src/telemetry_transform.py` — deterministic transformation runner
- `src/valid_drift_gate.py` — validates transformation causality/integrity
- `src/drift_eval.py` — paired baseline-vs-change evaluation and classification
- `tests/test_telemetry_changes.py` — transformation/gate tests

## Reproducibility rules

For every paired experiment DriftLens retains:

- source rule and SigmaHQ provenance
- source JSON hash
- baseline and changed event-stream hashes
- exact transformation ID and evidence
- valid-drift gate result
- baseline and changed match indexes/counts
- per-event TP/FN transition
- pinned evaluator/tool versions

Generated variants are experimental outputs and must never be described as original SigmaHQ telemetry.

## CI

`.github/workflows/json-baseline.yml` verifies the structured baseline.

`.github/workflows/drift-pilot.yml` runs unit tests, re-verifies the JSON baseline, runs all 15 paired experiments, and uploads:

`results/drift_pilot/`

as a workflow artifact. Generated pilot evidence is **not automatically committed**.

## Scope guard

DriftLens models telemetry/parser/normalization changes as experimental context. The primary AI repair target remains the affected **Sigma detection rule / detection content**, consistent with the approved FYP proposal.
