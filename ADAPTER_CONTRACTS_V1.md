# Scholarly Adapter Contracts v1

## Scope

Contract version `1.0.0` covers bibliographic metadata discovery, normalization and project-level registration. It does not cover full-text acquisition, eligibility screening, evidence extraction, claims or review writing.

The implementation has three hard boundaries:

1. Provider adapters perform HTTP GET requests and return provider records plus request/response metadata. They do not edit review CSVs or assign paper IDs.
2. Normalizers translate one provider record into a `PaperCandidate`. They do not decide relevance or canonical identity.
3. The registry assigns persistent project IDs, records identity decisions and materializes registry/bibliography artifacts. It does not decide inclusion.

## Canonical contracts

All persisted contracts include `contract_version: "1.0.0"`.

### `SearchRequest`

Required identity and reproducibility fields are `project_id`, `protocol_version`, `search_strategy_version`, `provider`, `exact_query` and `filters`. Execution controls are `per_page`, `max_pages`, `cursor`, `sort` and `mode`.

Credentials are intentionally absent. Adapters read optional configuration from the process environment and never serialize secret values.

### `SearchRun`

The required audit fields are:

- `search_run_id`, `project_id`, `protocol_version`, `search_strategy_version`
- `provider`, `exact_query`, `filters`, `execution_timestamp`
- `retrieval_status`, `raw_response_path`, `raw_response_sha256`
- `provider_record_ids`, `retrieved_count`, `pagination_cursor`
- `warnings`, `errors`, `coverage_limitations`

Result accounting adds `parsed_count`, `duplicate_count`, `ambiguous_identity_count`, `unique_canonical_count`, `rejected_count`, `pages_completed`, `completed_at` and `error_history`. `replay_of` identifies an offline reprocessing run.

Retrieval statuses are:

- `running`: checkpoint exists; execution has not finalized.
- `complete`: requested retrieval ended without a remaining cursor or error.
- `complete_empty`: successful provider response contained zero records.
- `complete_with_limit`: requested page cap was reached and a cursor remains.
- `partial`: at least one response succeeded before a later failure.
- `failed`: no provider records were safely retrieved.
- `replayed`: checksummed raw responses were processed without a live request.

### `ProviderResponse`

Records the run, provider, page, redacted URL/parameters, HTTP status, safe response headers, timestamp, raw path/checksum, record count and next cursor. Authorization headers, API keys, contact values and Plus tokens are never stored.

### `PaperCandidate`

Contains provider identity, SearchRun/raw-record pointers, title, authors, year, venue, normalized DOI, landing URL, provider work type, version type, optional abstract, additional source IDs and version relations. It remains a discovery candidate and is not an inclusion or evidence record.

### `PaperRecord`

Contains persistent `paper_id`, canonical bibliographic fields, separately retained provider IDs, SearchRun IDs, raw provenance pointers, verification state, conflict notes, related versions and first/last retrieval times.

### `IdentityMatch`

Records the candidate, matching method, verdict, confidence, selected `paper_id` or competing IDs, notes and timestamp. Ambiguous matches use `status=review_required` and are not merged.

### `MetadataResolution`

Records field-by-field existing/candidate values and the deterministic decision (`confirmed`, `filled_from_candidate`, `kept_existing_candidate_missing`, or `conflict_kept_existing`). Conflicts are retained and lower the verification status.

### `ProviderFailure`

Contains a stable code, provider, safe message, timestamp, retryability, attempt count, optional HTTP status and non-secret details.

## Stable error codes

Implemented codes include:

- `REQUIRES_API_KEY`
- `AUTHENTICATION_FAILED`
- `ACCESS_FORBIDDEN`
- `HTTP_RATE_LIMITED`
- `QUOTA_EXHAUSTED`
- `HTTP_SERVER_ERROR`
- `TIMEOUT`
- `NETWORK_UNAVAILABLE`
- `INVALID_REQUEST`
- `IDENTIFIER_NOT_FOUND`
- `PROVIDER_HTTP_ERROR`
- `MALFORMED_RESPONSE`
- `PAGINATION_CURSOR_STALLED`
- `RAW_RESPONSE_INTEGRITY_FAILURE`
- `LOCAL_IO_FAILURE`
- `NORMALIZATION_OR_REGISTRY_FAILURE`

`complete_empty` is not an error. A failed HTTP request is never translated into an empty successful search.

## Portability

The implementation uses only Python 3.11+ standard-library modules. Provider contracts are located under `research_review_agent/scholarly/`; no project/global Codex Skill or third-party runtime package is involved.
