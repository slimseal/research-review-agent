# Scientific reading contracts — Round 2G

Version: reading contract 1.0.0, additive over Evidence Schema v2. Implemented in `research_review_agent/reading/contracts.py` and `reading/pipeline.py`; executable contract inventory: `rragent reading-schema`.

## Objects and authority

- PaperReadingNote: stable reading_note_id; immutable revision_id and supersedes_revision; paper_id, document_id, document_sha256, document_version; protocol_version; screening_decision_reference; reading_procedure_version; generator; created_at; reading_status; source_coverage; unresolved_material; verification_status; review_status; content; dependencies.
- EvidenceItem: all 13 existing universal v2 fields, plus reading_note_id/revision, document_id/SHA, source_anchor_ids, extraction_run_id/status, review_status, result_kind, source_scope, citation_basis, support_boundaries and revisions.
- Extraction coverage disposition: paper_id, current note revision, exact evidence revisions, status, explanation, named review assertion if genuinely provided.
- Existing PaperRecord, DocumentVersion, ParsedDocument and SourceAnchor retain their original identifiers and contracts.

The existing `.review/state.json` and checksummed `.review/events.jsonl` are authoritative; no second workflow controller. JSON, Markdown and CSV exports are recoverable projections. One writer per project, not an authenticated database or concurrency platform.

## Reading content

All 25 fields listed by reading-schema must be present. Applicable content has status=present, text, epistemic_role and anchor IDs. Unavailable precise support requires an explicit grounding_unavailable_reason and blocks formal completion. Other statuses are not_reported, not_applicable, not_reliably_extractable and unavailable, each with a reason. These are not interchangeable.

Coverage names inspected sections, page numbers, visual pages, layout assessment and unresolved material. Completed notes account for all PDF pages; this is a declared reading account, not machine proof of attention. Conceptual work need not have empirical Methods/Results. A partial note is a valid provisional artifact, not a completed phase.

## Compatibility

The universal v2 core is unchanged; extra fields are additive CSV columns and richer versioned JSON. Existing v1/v2 structural validators still read old projects. A legacy v1 project's original matrix is never rewritten into v2: new output is EVIDENCE_MATRIX_V2.csv and formal Phase 8 is blocked pending an explicit reviewed migration, not implemented here. Existing v2 matrix bytes are archived before the first new projection. Old free-form notes or a CSV row are not silently promoted to reviewed source-grounded records.
