# Phase 3 — Scholarly Discovery

## Objective and rationale

Execute approved searches against configured sources and build a reproducible candidate set. Discovery identifies sources; it does not establish their detailed findings.

## Required inputs

- Approved search strings and protocol.
- A configured scholarly adapter or a documented manual export.

## Research operations

1. Confirm adapter configuration with `rragent capabilities` and `rragent provider-status`.
2. Verify that the exact provider query is represented in the reviewed Phase 2 strategy and assign a search-strategy version.
3. Run `rragent scholarly-search --project <path> --provider <openalex|crossref> --query <exact-query> --strategy-version <version>`; add provider-specific `--filter key=value` values only when documented in `SEARCH_STRINGS.md`.
4. Inspect the returned SearchRun status, result accounting, errors, coverage limitations and cursor before treating the attempt as complete.
5. Preserve raw responses, checksums, provider-response records and source identifiers. Resume a partial run with the same request plus `--resume-run <id>`; do not start an unrecorded replacement.
6. Inspect conservative identity matches, ambiguous candidates and metadata conflicts. Discovery does not decide eligibility.

## Expected artifacts

- `01_search/SEARCH_LOG.csv`
- `02_discovery/SEED_PAPERS.csv`
- `02_discovery/DISCOVERY_MASTER.csv`
- `02_discovery/SEARCH_RUNS.jsonl`
- `02_discovery/PROVIDER_RESPONSES.jsonl`
- `02_discovery/raw/<provider>/<search_run_id>/`

## Evidence and provenance requirements

Every candidate records its discovery source and identifier; every query attempt records success or an explicit failure code. Metadata and abstracts remain discovery-level bases.

## Academic judgment points

Assess candidate relevance provisionally, decide when query refinement requires a documented protocol-consistent iteration, and evaluate source coverage.

## Uncertainty and failure handling

Use the stable provider failure code as recorded by the adapter. OpenAlex cursor paging beyond its first page requires `OPENALEX_API_KEY`; an anonymous first-page success does not prove full coverage. Preserve failed or partial attempts and their last safe cursor; do not replace them with remembered citations.

## Prohibited actions

Do not invent papers, identifiers or result counts; do not report an unavailable database as searched; do not infer methods or results not present in the captured basis.

## Completion requirements

All planned searches are logged as executed or failed, candidate provenance is complete, and unresolved coverage limitations are presented for human review.

