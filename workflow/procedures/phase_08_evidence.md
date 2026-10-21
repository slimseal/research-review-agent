# Phase 8 — Evidence Extraction

## Objective and rationale

Create consistent evidence records that support later synthesis across research traditions without imposing irrelevant empirical fields.

## Required inputs

- Structured reading notes with exact provenance.
- Universal evidence schema and protocol-approved extension schema.

## Research operations

### Executable extraction procedure (EvidenceItem v1, universal Schema v2)

1. Require current Gate 1 and current, completed Phase 7. Start Phase 8 through `advance`. Read the approved extension schema, the complete current note and all relevant source passages. Do not infer evidence from titles or abstracts.
2. Enumerate distinct findings, arguments, null/negative/mixed results and conditions before coding. Produce multiple rows where outcomes or propositions differ; do not discard apparently unsupportive results. Extraction completeness requires a documented per-paper review, not a row-count target.
3. Build each JSON item with all universal v2 fields; lists/objects are native JSON before CSV export. Add `reading_note_id`, `document_id`, `document_sha256`, `source_anchor_ids`, `extraction_run_id`, `extraction_status`, `generator`, `result_kind`, `citation_basis`, `source_scope`, `inference_class` and `support_boundaries`. The CLI creates stable evidence IDs, revisions, exact locators and pending review status. The input `research_question` must match the active Protocol.
4. `support_boundaries` has five non-empty fields: `source_reports`, `author_interpretation`, `codex_inference`, `uncertainty`, `cannot_support`. Identify design, sampling, geography/time, measurement, selection, alternative explanations, causal identification, source criticism and translation limits as applicable. Empty or unavailable categories must be stated explicitly rather than invented.
5. Use row-specific `research_types` selected by the Protocol and only applicable `extension_json` fields. Preserve units, denominator and uncertainty for literal reported estimates in `reported_values` (each needs anchor_id/literal/units/denominator/uncertainty). Association cannot be promoted to a causal label without a stated identification basis; this declaration still needs semantic review. A numeric literal matching a source does not prove the effect interpretation is correct.
6. Set `citation_basis=secondary_report` and `secondary_source_reference` when reporting another cited source. The record remains evidence of what this source says, not verification of the cited original. `source_scope` is body_text/table/figure/equation/supplement. Non-body supported records require visual-page inspection and a representation assessment; exact-text anchors do not supply geometric table-cell verification.
7. `evidence-submit --config <json>` stores the proposal; `evidence-inspect --id <id>` follows anchors to the PDF. Missing support can be stored only as uncertain/incomplete/unsupported with `grounding_unavailable_reason`, never verified. Never estimate from scrambled figures or inaccessible supplements.
8. Actual humans use `evidence-review --action accept|reject|correct|uncertain|incomplete|reread|comment --id <id> --by <human> --comment <reason> [--changes <json>]`. Correction changes text/anchors only through a new revision and returns pending. Old versions remain in the journal. Model proposals cannot import approval fields. Named reviewer assertions are not authentication.
9. Use `evidence-close --paper-id <id> --status complete|no_relevant_findings|incomplete|failed --explanation <inspection account>` to declare per-paper extraction coverage. Add `--by <human>` only after genuine review of the exact note and current evidence revisions. New evidence/corrections invalidate closure. Zero evidence needs explicit no-relevant-findings review; no rows alone never indicate no results.
10. Inspect `reading-coverage`, `reading-validate`, `reading-queue`, `evidence-gate`, then use `advance --phase 8 --status completed` only when allowed. Gate 2 additionally requires the completed phase and current v2 matrix. Unresolved/rejected/uncertain extractions require correction/rereading, not silent deletion. Do not proceed to synthesis in the Round 2G development pilot.

All commands take `--project <path>`. Submission replays are idempotent; a superseded request is returned as stale. Formal v1 projects stay readable, but their new v2 extraction sidecar requires a future explicit reviewed migration; never overwrite their original matrix. Recovery uses `reading-recover`, not a second controller.

1. Assign a stable `evidence_id` to each distinct finding, argument or proposition.
2. Fill universal identity, question, source basis, context, evidence type, research types, finding/argument/proposition, locator, limitation and verification fields.
3. Apply any compatible combination of quantitative, qualitative, historical/documentary, theoretical/conceptual and archaeological/material extensions.
4. Use explicit nulls or missing-value statements; do not coerce unavailable fields.
5. Link related evidence records without merging contradictory or differently bounded results.

## Expected artifacts

- `06_evidence/EVIDENCE_MATRIX.csv`

## Evidence and provenance requirements

Rows resolve to a registered paper, use allowed source-basis and verification values, and contain exact evidence locations. Extension fields follow `DOMAIN_EXTENSION_SCHEMA.json`.

## Academic judgment points

Choose the appropriate unit of evidence, applicable research types, coding granularity and strength limits; preserve context needed for interpretation.

## Uncertainty and failure handling

Mark unverified or partially verified evidence explicitly. Return to reading when a locator or interpretation cannot be substantiated.

## Prohibited actions

Do not require population, sample size, exposure, outcome or effect size outside applicable extensions; do not fabricate missing values or promote metadata to result evidence.

## Completion requirements

The matrix contains validated, source-linked rows covering all material included-source contributions, with uncertainty and extension validity explicit.

