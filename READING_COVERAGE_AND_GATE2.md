# Coverage accounting and Gate 2

reading-coverage reconciles the current Gate-1-eligible corpus with per-paper note status, source/visual coverage, unresolved material, review state, evidence counts, valid anchored items, unsupported/ambiguous items, stale items and extraction dispositions. Lab selection is reported separately: eligible_papers=0, pilot_selected_papers=N.

Reading statuses: not_started (derived), in_progress, partial, completed, blocked. Awaiting review is a separate dimension, not confused with reading progress.

Per-document parser_status and parsing_limitations remain visible, including the parser's standing no-OCR/no-table-cell/reading-order warnings. documents_with_parser_limitations counts those warnings conservatively even when a reader inspected the rendered page; it does not claim that visual inspection upgraded the parser.

Extraction dispositions: complete, no_relevant_findings, incomplete, failed. Full text availability/exclusion remain upstream screening/acquisition concepts. Official corpus excludes excluded papers; lost/changed eligible documents produce source errors, not “no findings.” Zero evidence is never automatically interpreted as no relevant result.

## Completion rules

Phase 7: current Gate 1; exact approved documents and parse/anchor bindings; completed notes with page coverage and explicit missing material; no ungrounded present content; actual declared-human note acceptance.

Phase 8: all Phase 7 requirements plus valid source-grounded evidence, applicable extensions, reviewed current per-paper extraction closure and accepted supported items. A zero-row matrix is permitted only with actual human-reviewed, documented no-relevant-findings dispositions for the entire eligible corpus. No arbitrary minimum row count substitutes for coverage.

Gate 2: Phase 8 must also be completed through the workflow controller, and its matrix/reading/coverage must remain valid. A new downstream current-artifact check prevents using a stale manually retained Phase 8 completed flag. Phase order and prerequisites are unchanged. Gate 1 is still mandatory; Gate 3 claim-map requirements are untouched.

A small structurally valid CSV or a Markdown note cannot pass. A lab cannot pass formal completion, even if its sources are structurally valid. Corrected evidence invalidates completeness review. Formal v1-to-v2 migration needs future explicit human-reviewed migration; legacy reading alone does not silently approve it.

## Inspect versus act

evidence-gate reports completion readiness; it does not advance Phase 8. Use the existing advance command only after permitted and genuine review. Saved reports are not authorization tokens. Missing optional parser/source files give explicit errors; no model-memory substitute.
