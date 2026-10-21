# Evidence extraction schema and rules

One specific finding, argument, interpretation or proposition per EvidenceItem. Multiple items from the same paper are not independent corroborating studies.

## Input and derived fields

Universal core: evidence_id, paper_id, research_question, source_basis, research_context, evidence_type, research_types, finding_argument_proposition, evidence_locator, limitations_uncertainty, verification_status, example_data, extension_json.

The submit input omits generated evidence_id/locator/verification/review fields; the CLI derives these. Additional required input: reading_note_id, document_id, document_sha256, source_anchor_ids, extraction_run_id, extraction_status, generator, result_kind, citation_basis, source_scope, inference_class, support_boundaries. Exact field requirements are enforced by contracts.py and prepare().

The five support-boundary texts separate source_reports, author_interpretation, codex_inference, uncertainty and cannot_support. A statement such as “not reported” is preferable to inventing an author's interpretation.

Row-level research_types may combine any Protocol-selected types. extension_json is checked against the existing DOMAIN_EXTENSION_SCHEMA.json for required fields, types and applicability. This preserves v1/v2 validation; it does not rename their fields.

## Safeguards

- Result kinds preserve positive, negative, null, mixed, contradictory, conditional, argument, interpretation and uncertain.
- Detailed extraction accepts full_text only; title/abstract metadata cannot enter as detailed evidence.
- Secondary reports require an explicit secondary_source_reference and are not verified original evidence.
- supported needs resolvable anchors already in the note. Uncertain/incomplete/unsupported may retain no precise locator with an explicit reason; they cannot be accepted as supported or complete Gate 2.
- Numeric reported_values require an exact literal in a linked source span plus units/denominator/uncertainty. A populated effect_size requires such source support. Matching text does NOT establish statistical interpretation.
- A causal label requires a stated causal_identification_basis; detecting overclaiming in free prose still requires human semantic review. No NLP causal-correctness guarantee.
- Table/figure/equation/supplement support additionally requires recorded visual inspection and representation assessment. This is not automated table validation.

Stable IDs survive correction, new revisions preserve old content, exact input replay is idempotent, and superseded replay is explicitly stale. CSV exposes review_status and support boundaries. Unsupported/rejected items are retained, not selectively removed to obtain a passing Gate.
