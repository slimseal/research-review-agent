# Provenance, replay and coverage

For each successful HTTP response, record provider, redacted URL/parameters, status/safe response headers, UTC time, immutable project-relative path and SHA-256. Relation pages record seed, input cursor, raw row count and processed offset. Metadata enrichment and seed-ID lookups have their own raw responses. HTTP error responses retain stable failure code/status/allowed headers, but their body is not part of the existing transport contract. Invalid successful JSON bodies are retained before parsing.

Candidates retain the complete original reference/graph row. Edges retain all contributing candidate/run/provider/raw-pointer observations. Registry records retain bibliographic metadata provenance plus citation lineage. This is bibliographic relationship evidence, **not inspected scientific evidence**.

Offline replay validates stored bytes and parses the same source rows without HTTP or registration. It verifies candidate seed/direction/raw row; graph validation checks ordered endpoints and identities. Generated export hashes catch edits or missing files. State journals are checksummed for corruption recovery, not a cryptographic signature against an adversary who rewrites every artifact.

On failure, earlier raw pages, registry IDs and candidates remain. Resume checks current Protocol/seed and hashes before more requests, uses the saved record offset/cursor and does not duplicate committed candidates. Completed/limited runs do not silently restart. New executions get new run IDs; graph relationships can retain multiple provenance observations. A stale seed/Protocol blocks resume; historical results remain visible.

Coverage vocabulary:

- `REFERENCE_LIST_UNAVAILABLE`: provider omitted the reference list, not proof of zero references.
- `SUCCESS_EMPTY_INDEX_RESULT`: a successful empty result at this query/time, not exhaustive absence.
- `DEPOSITED_REFERENCES_ONLY`, `FILTER_CITES_INDEX_ONLY`, `OC_INDEX_ONLY_UNPAGINATED`: source-specific boundaries.
- `METADATA_MISSING` / unresolved identity: graph reference is retained but not a fabricated canonical paper.
- `REQUEST_LIMIT`, `CANDIDATE_LIMIT`: local researcher limits, not saturation or quota.
- `QUOTA_EXHAUSTED`, `HTTP_RATE_LIMITED`, authorization/network/timeouts: external execution limitations.

Scientific quality cannot be inferred from graph degree. Humanities/historical/non-DOI materials can be underrepresented. Multiple DOIs in one OpenCitations endpoint remain ambiguous because they may identify distinct versions. Full-text access, inclusion/exclusion and source interpretation remain downstream tasks.

The real pilot retained 19,536 incoming OC rows for its first seed but processed only 35 before the shared round cap. The other 19,501 are **raw unprocessed records**, not screened papers or resolved identities. Only 80 processed candidate observations became graph relationships (45 backward, 35 forward); 32 endpoints remain unresolved. This is a bounded connectivity/integrity test, not a completed review or an exhaustive bibliography.
