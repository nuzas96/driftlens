# DriftLens-X — Hybrid Agentic AI Scope Revision v1.2 (PROPOSED)
Date: 2026-10-14
Status: INTERNAL TEAM DEVELOPMENT CONTRACT; not Madam-approved; no new scored AI results.
CURRENT CLEAN TEAM SOURCE OF TRUTH (refined v1.2 + Codex decisions): https://docs.google.com/document/d/1WLMoPhUR4BfqItvP7_ApFk-kbKChVYVLWjQ8sDxPPgw/edit
Historical Methodology v1.2 pre-refinement: https://docs.google.com/document/d/1G2iECtud4YShYl35P9vK9KrktLjpbWuiIfgssn7VLRM/edit

## Why this revision?
A deterministic parser bug in the original 15-case dev pilot accounted for both apparent D0 diagnosis misses. Repaired D0 got 15/15 on **seen** development cases, so claiming an AI advantage merely from easy field renaming is indefensible. Preserve the original 13/15 and post-hoc 15/15 as separate development facts; neither generalizes to held-out cases. Do **not** invent ambiguity to favor AI.

## IMPORTANT: TWO SEPARATE MODES (agreed design update)
**FYP RESEARCH / EVALUATION mode** must run D0, one-shot L1, and real tool-using A2 on the SAME eligible case sets with appropriate shared evidence and gates, scoring each module independently. The hybrid operational route is a separately reported arm. Do not let D0 skip all cases so that there is no meaningful AI evaluation. Neither AI needs to beat D0 on every case, but each must have real agent/tool decisions and an independently testable research question.

**OPERATIONAL HYBRID** may invoke D0 for solved, well-supported cases and call A2 selectively for unresolved evidence/candidate decisions. Freeze escalation/routing policy before held-out testing; measure skipped calls and resource cost. D0 remains STRONG and may access the same permitted schema/reference evidence as A2.

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
  "alternative_hypotheses": ["ESSENTIAL_FIELD_LOSS"],
  "evidence_refs": ["observed_event_snapshot_A#field_1", "observed_event_snapshot_B#field_7"],
  "evidence_sufficiency": "SUPPORTED",
  "uncertainty_or_stop_reason": "SUPPORTED_AFTER_EVIDENCE_CHECK",
  "tool_trace_refs": ["tool_call_01", "tool_call_02"],
  "requires_human_review": false
}
```
The core diagnosis contract intentionally has **NO mandatory recommended_action or recommended_route**. Nuzhmi makes the recovery decision himself; at most a non-binding optional hint can be tested as a separate ablation. `alternative_hypotheses` is a list of independently supportable unresolved explanations, NOT labels disclosed from experimental metadata.

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
  "gate_results": {"G1": "PENDING", "G2": "PENDING", "G3": "PENDING", "G4": "PENDING", "G5": "PENDING"},
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
**FAIR EVIDENCE RULE:** L1 (one-shot) receives the COMPLETE case-specific admissible evidence bundle UPFRONT. A2 can retrieve the SAME evidence from its fixed read-only tool catalogue; neither may receive privileged oracle information. Strong D0 has the same permitted information/schema references. Freeze the per-case evidence catalogue, **maximum bundle size**, overflow/truncation/exclusion policy, and query/call budgets before experiments; no silent withholding of relevant facts from L1. If bundle overflow prevents the promised complete evidence, declare and handle that case under the pre-registered rule rather than reporting an equal-evidence comparison. Log A2 retrieval cost and first-attempt versus multi-attempt workflow budgets separately.

## Evaluation contract
- D0 strong deterministic baseline (not deliberately broken)
- L1 one-shot LLM (one candidate)
- A2 bounded tool-using Agentic AI (at most 3 TOTAL attempts on development: initial+2)
- Hybrid D0->A2 in operational routing, evaluated separately
- G1 schema; G2 semantics/no fabrication; G3 DEV positive replay; G4 ZERO NEW rule-window matches on PREDECLARED accurately labelled DEV benign windows relative to the unchanged original Sigma rule **without the candidate adapter on the corresponding changed benign telemetry**; G5 unchanged Sigma+audit. Record pre-existing baseline benign matches/false positives separately.
- DEV_ACCEPTED requires PASS on EVERY mandatory gate G1–G5. A missing/failed/inconclusive mandatory gate MUST PREVENT acceptance (INCONCLUSIVE or REJECTED). No 'available gates only' exceptions. Candidates, scope and parameters are frozen BEFORE terminal held-out; final scored results are never fed back into refinement. A DEV_ACCEPTED candidate is NOT yet a held-out validated recovery.
- Report root-cause affected denominator separately from no-impact controls; safe recovery separately from abstention; paired positive/benign rule-window outcomes; costs/runtime.
- NO case-specialized/answer-leaking adapters: the transformation MUST apply consistently within declared source/rule scope and MUST NOT branch on opaque case IDs, positive-event values/signatures, expected labels, hidden oracle mapping or held-out outcomes. Identical frozen mapping/logic is applied to positive and benign windows in development and final evaluation.
- No assumption that A2 beats D0. A legitimate negative result is still valid, but do not claim demonstrated AI advantage before testing.

## Scope guard and evidence gate
Working targets unchanged: 10 rules, 30 case configurations (10 relocation, 6 essential-field loss, 4 value representation, 10 nonimpact), 200 held-out BASE rule-windows (10 positive + 10 benign per rule) pending provenance feasibility.
Source-positive smoke tests: 10/10 rule candidates now runnable (five original, five pinned external CI); source/session independence and final 30 cases NOT established.
Only independently evidenced, realistic unknown/competing mappings count as genuinely uncertain. Pre-register simple/evidence-needed/unresolvable/nonimpact strata; do not invent hard examples or hide info from D0. COMPOUND DRIFT is an OPTIONAL exploratory extension only if a new multi-change validity gate is separately built/reviewed; it is NOT required for the MVP or a fixed part of the 30-case target. If no real evidence-needed cases exist, openly narrow Agentic AI claims and request any scope change before final testing.

## Dataset experiment design — cross-cutting strata, NOT fabricated quotas
Preserve the old **working** 10/30/200 totals until source feasibility and supervisor confirmation; the 30 configurations remain grouped 10 field relocation + 6 essential structured field loss + 4 typed value representation + 10 non-impact controls. In addition, annotate *evidence difficulty* as a SECOND DIMENSION (uniquely known mapping, plausible multi-candidate, supported compound observed changes, genuinely absent current data/abstain). Do not misrepresent them as new disjoint 30-case categories. The 5/4/1/etc. scenario split floated in discussion is just illustrative, NOT approved or source-proven. Compound scenarios require an independently reviewed multi-change validity gate. An official ECS/ASIM schema mapping is useful reference evidence, but alone does not prove which real event field is correct.

Start with five rules as a COMPLETE positive+independent-benign+capture-provenance+oracle checkpoint, then extend toward ten when data permits. This is NOT an unannounced reduced FYP target. Source-identical or transformed windows must remain grouped across train/dev/final held-out split. If no genuinely evidence-dependent cases exist, disclose the limitation rather than force AI to 'win'.

## Safety & stopping semantics
Hazim stops with a clear `uncertainty_or_stop_reason` on insufficient/conflicting evidence, tool exhaustion, verified support or a technical failure. A precise tool-call budget for diagnosis is **not locked yet**. Nuzhmi has maximum 3 TOTAL development candidate attempts (first+2 revisions). AI may inspect DEV feedback only. Full gate outcome G1–G5 controls acceptance and cannot be overruled by a model; missing actual benign G4 replay = INCONCLUSIVE or REJECTED, NEVER fully safe. 'Accepted development candidate' differs from 'held-out validated recovery'. Final test verdict is terminal and cannot be used to revise candidates.

## Three planned demonstrations
1. Controlled drift loss -> evidence-backed diagnosis -> positive & benign DEV recovery gates pass -> selected result; no production safety claim.
2. Essential current field absent with no reliable equivalent -> explain why ABSTAIN is necessary.
3. Plausible candidate fails documented semantic/benign safety validation -> REJECTED; no auto-deployment.

## Team parallelization
Hazim develops mock diagnosis consumer/producers conforming to diagnosis_v1.
Nuzhmi builds recovery consumer and common validator against mock diagnosis_v1 responses (category only in oracle-assisted standalone tests; no exact repair hints).
Integrate early using a single shared rule/evidence store. Do not wait until both AI modules are finished.
Freeze `diagnosis_v1` and `recovery_v1` JSON Schema plus mock fixtures by BOTH students before parallel integration. Until joint sign-off, these names and examples are PROPOSED rather than a claim that frozen schema implementations exist.

## Verified and not-yet-verified development status (14 Oct 2026)
- Ten Sigma rule-level positive smoke baseline examples have run using pinned SigmaHQ data and the real matcher (five original + five newly tested candidates). CI: https://github.com/nuzas96/driftlens/actions/runs/38534218848
- 15 known DEV cases, of which 9 were affected and 6 unaffected. Old buggy field-dependency parser D0: 13/15 overall (7/9 affected); post-hoc corrected D0 on SAME seen cases: 15/15 (9/9 affected). Not blind/generalization, not agentic accuracy.
- One positive FIELD_ALIAS restoration; one conservative missing-data abstention; synthetic negative sanity/collision tests only. NO independently sourced benign held-out validation.
- NO actual L1/A2 agent run, NO fully integrated two-agent UI, NO 200 capture-provenance independent windows, NO 30 finalized cases, NO final AI-benefit result. Main branch unchanged by isolated development.
- THIS REMAINS an internal design fix, not an implemented AI system, completed proposal or supervisor-approved scientific claim.
