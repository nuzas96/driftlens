# DriftLens-X — Hybrid Agentic AI Scope Revision v1.2 (PROPOSED)
Date: 2026-10-14
Status: INTERNAL TEAM DEVELOPMENT CONTRACT; not Madam-approved; no new scored AI results.
Source-of-truth Methodology v1.2 working draft: https://docs.google.com/document/d/1G2iECtud4YShYl35P9vK9KrktLjpbWuiIfgssn7VLRM/edit

## Why this revision?
A deterministic parser bug in the original 15-case dev pilot accounted for both apparent D0 diagnosis misses. Repaired D0 got 15/15 on **seen** development cases, so claiming an AI advantage merely from easy field renaming is indefensible. Preserve the original 13/15 and post-hoc 15/15 as separate development facts; neither generalizes to held-out cases. Do **not** invent ambiguity to favor AI.

## Revised single-system dataflow
```text
Pinned Sigma rule + provenance-tagged observed telemetry
  -> COMMON deterministic admission/impact measurement (fixed)
  -> STRONG D0 first, known-safe resolution/no-change/abstain
  -> HAZIM diagnosis A2 escalation when evidence-dependent or D0 uncertain
  -> NUZHMI recovery A2 escalation when candidate choice/safety is unresolved
  -> COMMON G1-G5 development validator -> freeze candidate
  -> ONE TERMINAL independent held-out evaluation -> human report
```
For research, **each AI module also runs as its own comparison arm**, even when operational hybrid would use D0. D0, L1, A2 and hybrid paths are separately logged.

## Scope / owners
- Hazim (Scope 2): evidence-grounded tool-assisted root-cause investigation under documented uncertainty, evidence references, support/conflict verification, calibrated refusal. Does NOT invent final impact labels or accept privileged transformation metadata.
- Nuzhmi (Scope 1): constrained candidate selection for recovery from Hazim's supported diagnosis, evidence-backed mapping, feedback-guided development retries, safe refusal, positive/benign validation. Does NOT rewrite source Sigma or fabricate missing event values.
- Shared: common telemetry model, deterministic admission gate, reproducible evaluator, oracle/ground truth, provenance grouping, front-end/reporting and complete end-to-end comparison.

## V1 interface: Hazim -> Nuzhmi (proposed)
```json
{
  "contract_version": "diagnosis_v1",
  "opaque_case_id": "case_development_001",
  "admission_status": "VALID_AFFECTED",
  "diagnosis_category": "FIELD_RELOCATION",
  "candidate_causes": ["FIELD_RELOCATION"],
  "evidence_refs": ["observed_event_snapshot_A#field_1", "observed_event_snapshot_B#field_7"],
  "evidence_sufficiency": "SUPPORTED",
  "uncertainty_reason": null,
  "recommended_route": "CONSIDER_ALLOWED_RECOVERY",
  "tool_trace_refs": ["tool_call_01", "tool_call_02"],
  "requires_human_review": false
}
```
Allowed diagnosis categories: FIELD_RELOCATION, VALUE_REPRESENTATION, ESSENTIAL_FIELD_LOSS, INSUFFICIENT_EVIDENCE, NO_DETECTION_LOSS. Admission status (VALID_AFFECTED/VALID_UNAFFECTED/INVALID_DRIFT/EXECUTION_ERROR) comes from common deterministic gate and is not an AI prediction.

## V1 interface: Nuzhmi recovery -> common validator (proposed)
```json
{
  "contract_version": "recovery_v1",
  "opaque_case_id": "case_development_001",
  "diagnosis_ref": "diagnosis_v1/case_development_001",
  "action_type": "FIELD_ALIAS",
  "adapter_proposal": {
    "source_logsource": "windows/sysmon/process_creation",
    "rule_scope": "specified-rule-id",
    "from_current_observed_field": "process.command_line",
    "to_expected_sigma_field": "CommandLine"
  },
  "evidence_refs": ["observed_event_snapshot_B#field_7", "schema_document#evidence_2"],
  "attempts_used_development": 1,
  "validation_status": "PENDING",
  "requires_human_review": true
}
```
Allowed actions ONLY: FIELD_ALIAS, REGISTRY_DWORD_CANONICALIZATION, REGISTRY_HIVE_ALIAS, NO_CHANGE, ABSTAIN. Normalization applies to **structured event representation before the existing pinned matcher**. Source Sigma is immutable. Candidate is *not* accepted just because it appears in JSON; common G1-G5 tests decide. A PENDING status must never be represented as a safe-validated candidate.

## Evidence interface / oracle separation
Allowed read-only evidence tools, conceptual API:
- inspect_rule_dependencies(rule_id)
- summarize_observed_fields(opaque_case_id)
- fetch_provenance_tagged_observations(opaque_case_id, permitted_subset)
- retrieve_pinned_schema_reference(ref_id)
- replay_current_rule_on_allowed_DEV_observations(...)
- test_candidate_in_DEV_positive_and_benign_only(...)

Disallowed for AI/D0 candidate prompts: experimental transformation operation, exact from/to answer, gold cause, true repairability, private oracle labels, final held-out test verdict/metrics, revealing file path labels, or hints derived from hidden gold data.
All methods receive the same **permitted** data and fair budgets. D0 may access the same evidence; initial first-attempt comparisons must use a common materialized evidence packet. Tools used for sequential evidence acquisition must be separately logged and resource-counted.

## Evaluation contract
- D0 strong deterministic baseline (not deliberately broken)
- L1 one-shot LLM (one candidate)
- A2 bounded tool-using Agentic AI (at most 3 TOTAL attempts on development: initial+2)
- Hybrid D0->A2 in operational routing, evaluated separately
- G1 schema; G2 semantics/no fabrication; G3 DEV positive replay; G4 DEV independent benign replay; G5 unchanged Sigma+audit
- All candidate strategies frozen BEFORE terminal held-out. No scored final test feedback for AI refinement.
- Report root-cause affected denominator separately from no-impact controls; safe recovery separately from abstention; paired positive/benign rule-window outcomes; costs/runtime.
- No assumption that A2 beats D0. Successful negative result is still valid, but do not claim demonstrated AI contribution before testing.

## Scope guard and evidence gate
Working targets unchanged: 10 rules, 30 case configurations (10 relocation, 6 essential-field loss, 4 value representation, 10 nonimpact), 200 held-out BASE rule-windows (10 positive + 10 benign per rule) pending provenance feasibility.
Source-positive smoke tests: 10/10 rule candidates now runnable (five original, five pinned external CI); source/session independence and final 30 cases NOT established.
Only independently evidenced, realistic unknown/competing mappings count as genuinely uncertain. Pre-register simple/evidence-needed/unresolvable/nonimpact strata; do not invent hard examples or hide info from D0. If no real evidence-needed cases exist, openly narrow Agentic AI claims and request any scope change before final testing.

## Team parallelization
Hazim develops mock diagnosis consumer/producers conforming to diagnosis_v1.
Nuzhmi builds recovery consumer and common validator against mock diagnosis_v1 responses (category only in oracle-assisted standalone tests; no exact repair hints).
Integrate early using a single shared rule/evidence store. Do not wait until both AI modules are finished.
This v1.2 is a **design fix, not a completed implementation or validated scientific advantage**.
