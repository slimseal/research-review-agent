# Scholarly Discovery Implementation

## Implemented runtime

The Round 2C runtime is additive to the verified Round 2B controller:

| Responsibility | Module |
|---|---|
| Versioned data contracts | `research_review_agent/scholarly/contracts.py` |
| HTTP retries and error mapping | `research_review_agent/scholarly/transport.py` |
| OpenAlex and Crossref requests | `research_review_agent/scholarly/providers.py` |
| Provider-to-common normalization | `research_review_agent/scholarly/normalization.py` |
| Raw/SearchRun persistence | `research_review_agent/scholarly/store.py` |
| Identity, reconciliation and bibliography | `research_review_agent/scholarly/registry.py` |
| Workflow coordination and accounting | `research_review_agent/scholarly/pipeline.py` |

No existing Phase, dependency or hard Quality Gate was removed or weakened. Existing Schema v1/v2 CSV headers remain readable; new provenance data is additive JSON/JSONL or is stored in existing `extension_json` fields.

## OpenAlex

Implemented operations:

- Works keyword search through `GET https://api.openalex.org/works`.
- Provider filters, sort, `per_page` and cursor pagination.
- Optional `OPENALEX_API_KEY` through the `Authorization: Bearer` header.
- Explicit `REQUIRES_API_KEY` before following a non-initial cursor without a key.
- OpenAlex ID and DOI preservation, author/year/source normalization, location/version mapping and inverted-index abstract reconstruction.
- Missing DOI/abstract warnings, raw response preservation, rate/credit header capture and retry/error mapping.

Current official documentation states that casual basic queries can be keyless, a free key increases the daily budget, and following a cursor after the first page requires a key. Supported `per_page` is 1–100, and 429 covers rate or daily-credit exhaustion. The implementation follows the current official [authentication](https://help.openalex.org/api/authentication/), [paging](https://help.openalex.org/api/paging/), [search](https://help.openalex.org/api/searching/), [filter](https://help.openalex.org/api/filtering/) and [error handling](https://help.openalex.org/api/errors/) references checked on 2026-10-15.

The CLI does not silently split very long Boolean searches, translate database syntax or claim complete coverage. These remain reviewed Phase 2 decisions.

## Crossref

Implemented operations:

- Bibliographic search through versioned `GET https://api.crossref.org/v1/works` with `query.bibliographic`, filters, rows and cursor.
- DOI singleton lookup through `GET /v1/works/{doi}`.
- Optional polite identification via `CROSSREF_MAILTO` and optional subscriber token via `CROSSREF_PLUS_API_TOKEN`.
- DOI, title, author, year, container title, type, URL, abstract and deposited relation normalization.
- Cross-provider DOI matching, field-level verification/conflict logs and partial failure reporting.

Crossref's public REST API requires no signup. Current official guidance recommends contact identification, caching, sequential/conservative requests, inspecting rate/concurrency headers and backing off after 429. The implementation follows the current official [REST overview](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [access and authentication](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/), [usage and cursor guidance](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/) and [API versioning](https://www.crossref.org/documentation/retrieve-metadata/api-versioning/) checked on 2026-10-15.

Crossref resolution verifies bibliographic identity only to the extent supported by deposited metadata. It does not verify a paper's findings.

## CLI and workflow checks

`rragent scholarly-search` requires:

- a schema-valid, substantively populated, human-approved Protocol;
- request `project_id` and `protocol_version` matching that Protocol;
- Phase 2 completed;
- Phase 3 currently `in_progress`.

`rragent resolve-doi` uses the same checks and is permitted during active Phase 3 or Phase 5. `rragent replay-search` verifies every raw checksum and requires an active Phase 3 or 5 in a real project.

The commands never change a phase to completed. A successful metadata run is not sufficient to complete Phase 4, and it covers only the registration portion of Phase 5—not lawful full-text acquisition.

## Outputs

- Existing: `SEARCH_LOG.csv`, `DISCOVERY_MASTER.csv`, `PAPER_REGISTRY.csv`, `references.bib`.
- New: `SEARCH_RUNS.jsonl`, per-run JSON, `PROVIDER_RESPONSES.jsonl`, immutable raw JSON, `IDENTITY_MATCHES.jsonl`, `METADATA_RESOLUTIONS.jsonl`, `PAPER_IDENTITIES.json`.

Managed bibliography entries are placed between explicit RRA markers; pre-existing non-managed bibliography text is preserved.

## Deliberately not implemented

- Citation-graph expansion for Phase 4.
- Full-text/PDF acquisition, licensing decisions or paywalled access.
- PDF parsing or full-text scientific reading.
- Screening, Evidence Matrix extraction, claims, gaps, synthesis or drafting.
- Query translation across providers or automatic methodological search design.
