# Search Provenance and Recovery

## Immutable inputs and replaceable derivatives

Each successful provider response is written byte-for-byte to:

`02_discovery/raw/<provider>/<search_run_id>/page-000001.json`

The SHA-256 digest is stored in both the SearchRun and ProviderResponse ledger. A same-path write is accepted only if bytes have the same digest; a collision fails loudly. Raw files are inputs for replay and are not silently overwritten.

Derived artifacts—normalized candidates, canonical registry rows and managed BibTeX—can be regenerated from checksummed raw responses. `rragent replay-search` verifies every digest before parsing and creates a distinct replay SearchRun referencing the original.

## Checkpoint and resume

After every successful page the pipeline persists:

- raw response and checksum;
- provider response metadata;
- parsed/duplicate/ambiguous/unique/rejected counts;
- processed provider IDs;
- next cursor;
- registry and discovery artifacts.

If a later request fails, status becomes `partial` and the cursor for the failed page remains. Resume requires the same project, Protocol version, strategy version, provider, query and filters. Previous current-attempt errors move to `error_history`; a successful continuation can finish as `complete` without duplicating provider records or changing paper IDs.

The pipeline emits a `scholarly_search_finished` event into the existing checksummed state journal. It does not create a second workflow-state system and does not mark the phase complete.

## Failure semantics

- HTTP/network/authentication/quota/timeouts are failures, never zero-result successes.
- A valid 200 response with no items is `complete_empty` plus an `EMPTY_SUCCESS` warning.
- A page cap with a remaining cursor is `complete_with_limit`, not a claim of exhaustive coverage.
- Malformed records are counted as rejected; a malformed response envelope fails the run.
- A stalled cursor stops retrieval with an explicit error.
- One provider's success does not erase another provider's failure or imply complete database coverage.

## Private configuration

Only credential-presence booleans and environment-variable names are reportable. `OPENALEX_API_KEY`, `CROSSREF_MAILTO` and `CROSSREF_PLUS_API_TOKEN` values are not written to URLs, SearchRuns, logs or reports. The `.gitignore` policy should exclude research workspaces, `.env` files, credentials and private raw stores before public release.

## Recovery commands

- Resume network pagination: repeat `rragent scholarly-search` with the original arguments and `--resume-run <id>`.
- Replay deterministic processing: `rragent replay-search --project <path> --run-id <id>`.
- Recover controller state: `rragent recover --project <path>`.

These operations are distinct. Search replay cannot repair a corrupt workflow state, and controller recovery does not recreate missing raw provider bytes.
