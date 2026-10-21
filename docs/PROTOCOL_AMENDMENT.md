# Draft RQ amendments and independent evaluation

This additive patch preserves the No-Skills architecture, all 19 phases and the original three hard Gates. It does not implement amendments to an approved or progressed study.

## Controlled RQ change

Run `python -m research_review_agent amend-protocol-question --project PROJECT --request REQUEST.json`.

The request requires `request_id`, `expected`, `new_question`, `new_version`, `reason`, `source_path`, `source_sha256`, `consistency_review`, and optional `draft_patch`.

- `expected` contains exactly `project_id`, `protocol_version`, `protocol_sha256`, `state_sha256`, `journal_sha256`, and `old_question`. Hashes are SHA-256 of raw file bytes, not reserialized JSON.
- `consistency_review` contains substantive explanations for `subquestions`, `concepts`, `search_plan`, `screening`, and `extensions`. The CLI checks presence; academic consistency must actually be reviewed by the operator.
- The narrow patch permits decision/provenance/policy fields, subquestions and concepts. It cannot change identity, approval, scope, evidence extensions or search budget. Eligibility criteria version follows the new draft version.
- Preconditions: draft, no approval/history, Phase 0 only, matching Protocol/state identity and journal, no nonempty downstream artifacts except exact header-only scaffold CSVs, and no conflicting CLI operation.
- The source receipt, request, exact pre-change bytes, transaction and result are retained under `.review/protocol-amendments/REQUEST_ID/`. Original journal bytes are retained as a prefix.
- All project CLI operations share an OS advisory lock. External programs/direct filesystem edits do not participate in that lock. Do not run older CLI versions or direct Python writers concurrently.
- Prepared changes roll forward after interruption through `recover --project PROJECT`. While pending, normal CLI access is blocked. Unexpected third-state edits cause recovery to stop instead of overwriting them. Replaying an identical request is idempotent; changed content with the same ID is rejected.
- The tests exercise process/operation interruption boundaries. This is a recoverable multi-file transaction, not an atomic multi-file filesystem or a guarantee against disk loss/power failure. Keep an external snapshot. Do not restore individual protected files from the snapshot into a newer project.

`update-protocol` retains its protected RQ restriction. Neither amendment nor recovery approves the Protocol or advances phases.

## Independent evaluation checkpoint

This is opt-in for legacy compatibility. The amended pilot stores the requirement in Protocol, state and a separate marker; ordinary policy deletion/phase flags do not release it. Old projects with no requirement return `not_required`, which is not a claim of independent validation.

Use these interfaces only at their appropriate later checkpoint:

```bash
python -m research_review_agent independent-evaluation-gate --project PROJECT
python -m research_review_agent independent-evaluation-context --project PROJECT
# Actual human only, after genuine evaluation and separate human confirmation:
python -m research_review_agent independent-evaluation-register --project PROJECT \
  --record REVIEW.json --source EVALUATOR_SOURCE --confirmation CONFIRMATION_SOURCE \
  --human-attestation
```

Context requires current human-reviewed Phase 8 and eligible corpus. It returns the exact manifest/version/hash and ten required checks. The minimal contract conservatively covers **every current eligible EvidenceItem and every included paper's omission review**, not a sampled subset. A future sampling policy needs separate review and implementation; no uninspected item is implicitly approved.

The `independent-evaluation/1` record includes that exact manifest/hash, example-data classification, `human_source_first` method, completed review, evaluator, time, independence statement, source-first method, limitations, correction history, human confirmation source, and a separate confirming person's declaration/basis. Source and confirmation bytes must be distinct, checksummed and preserved. Each EvidenceItem binds its revision and all ten check judgments to source anchors. Per-paper coverage binds the approved document version and omission review. Unresolved findings block entry. See `independent_evaluation.validate_record` and the explicitly fictional contract fixtures for field structure, never for reusable research judgments.

Registration retains both source records and journals the entry. The gate recomputes current corpus/source/version bindings, validates registration provenance, and fails closed for missing, changed, stale, copied or labeled fictional/model records. It is also checked by direct synthesis and downstream writing entry points, not only phase advancement.

The CLI cannot authenticate identity, independence, honesty, or scientific fidelity. A user with full filesystem control can forge an entire history; checksums are not signatures. Humans must inspect the original evaluation and confirming record. The implementation must never describe a technically valid record as authenticated independent research validation.

Resolved evaluator deferral is distinct from unfinished evaluation. Before genuine Protocol approval, even Phase 1 remains blocked. Afterwards other stages remain subject to all existing reviews/Gates; Phase 9–18 remain held until the current evaluation checkpoint passes.
