# PaperReadingNote implementation

The implementation is a deterministic infrastructure plus an ordinary Phase 7 research procedure, not a standalone model API. Codex/researchers perform scientific interpretation; the CLI checks and persists the supplied result.

## Execution

1. Actual Gate 1 passes for the exact current paper/document version; Phase 7 is active.
2. Existing document-parse freezes page text. Official successful parsing synchronizes the derived acquisition ledger; no screening decision changes.
3. reading-context returns verified identity, SHA, parse reference, pages, parser limitations and Protocol.
4. Read full relevant source material and render important pages. Use existing anchor-create and anchor-lookup.
5. reading-submit validates the 25-field content contract, page bounds, precise anchors and current source dependencies; it always sets review_status=pending.
6. reading-inspect shows source resolution and history. Only actual humans may accept/correct/reread. Phase 7 completion requires current completed, accepted notes for every eligible paper.

Canonical exports: 05_reading_notes/READING_NOTES.json (all revisions), plus one derived RN-*.md per current note. Extraction never uses the Markdown file as an authority.

## Methodological scope

The procedure separately covers quantitative sampling/estimands/identification, qualitative cases/reflexivity/themes, historical provenance/source criticism, conceptual premises/inference, and material provenience/chronology/taphonomy. Applicability is not inferred from a fixed population–exposure–outcome template. The real pilot consists of two software-design papers, classified provisionally as conceptual/design propositions; it does not empirically validate all five traditions.

## Unsupported material

pypdf remains a page-text parser, not OCR, table-cell recognition or equation understanding. Visual inspection is a recorded Codex/researcher declaration. SourceAnchor remains an exact text-span locator, not a geometric table/figure locator. Image-only/encrypted documents retain the pre-existing explicit errors; missing supplements, scrambling and uncertainty must not be filled from memory.

The current reading corpus binds one screened main DocumentVersion per paper. Multi-document supplementary-source aggregation and non-PDF primary-source ingestion are not implemented by this new module; unavailable supplements must remain explicitly unresolved. Archived/documentary and material-evidence schema support is not a claim that every archival format can now be ingested.
