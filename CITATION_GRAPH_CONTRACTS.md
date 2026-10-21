# Citation graph contracts — v1.0.0

Authoritative dataclasses: `research_review_agent/citations/contracts.py`. Additive to Evidence Schema v1/v2, not a migration of scientific evidence fields. JSON mirrors and CSV cells use UTF-8. Nested fields in CSV are JSON.

| Contract | Core fields | Invariant |
|---|---|---|
| SeedSet | id/version, protocol version/content hash, selected IDs/reasons/selector/time, approval, depth, provider plan, round request/candidate limits, identity snapshot | Existing canonical identities only. Registration is pending review. `pilot_selected` can never approve an official review. |
| CitationExpansionRun | id/project/protocol/seed version/round/direction/provider/query/time/status, raw paths/hashes, cursor, five counts, warnings/errors/coverage | Each start has a fresh ID. Resume appends checkpoints/error history to that run; old responses never overwritten. |
| ExpansionCandidate | id/run/seed/direction/round/provider IDs, metadata, identity/duplicate status, paper ID or null, raw reference/pointer, relevance/screening | `not_assessed` and `not_screened`; registration is not inclusion. |
| CitationEdge | id, citing/cited identity, seed/direction/round/provider/provider record, raw pointer/time, relation/identity status/basis, provenance array | **citing → cited**, never recommended → similar. Each provenance links to an actual candidate/raw row. |

Runtime run extensions: initial canonical ID snapshot; full seed metadata snapshot; relation pages with input cursor, next record and completion flag; metadata/seed-identity raw page cache; request reservations; error history; stop reason; mode. These make interruption/replay accounting deterministic. Dates are UTC in records; reports may show local date.

Canonical IDs remain the existing `P0000001` format. Candidate IDs hash run + raw path/hash/index. Edge IDs hash the ordered endpoint pair. External unresolved endpoints use `external:doi:<normalized-doi>` or `external:reference:<raw-reference-hash>`. An external node is not a Paper Registry row. Graph dedup and paper dedup are separate; multiple source observations append provenance. A legitimate self-edge remains a relation and adds no new paper.

`relation_status=provider_reported` is not full-text verified. Identity status distinguishes exact registered DOI, conservative existing normalizer/Registry matching, ambiguous identities, metadata missing, missing identifiers and multiple-DOI endpoints. Unstructured strings and literal deposited author/year/title remain visible. No implicit DOI creation or fabricated bibliographic fields.

## Counts

- discovered: processed source-row observations, including unresolved references;
- resolved: observations with canonical IDs;
- unresolved: discovered minus resolved;
- duplicate: observations matching IDs present at run start or earlier in that run;
- unique_new: distinct resolved IDs absent at run start;
- provider_row_count: number returned in a raw relation page; may exceed processed observations;
- requests: reserved HTTP attempts, including failed requests and identity/metadata lookups. A crash before actual dispatch can conservatively overcount, never reset a budget.

Rows retained but not processed are exposed by `provider_row_count - next_record`, not mislabeled as resolved or screened. Run new-ID totals must not be summed blindly across overlapping resumed runs; round report uses a distinct set. No universal completeness denominator is asserted.

## Compatibility

No existing scientific project was migrated. CSV managed exports now preserve PDF fields, license/hash, custom columns and custom extension keys. Unmanaged legacy IDs are reserved against allocation; DOI matches to unmanaged CSV rows are unresolved pending explicit reconciliation. Existing exact DOI/provider/fingerprint matching and preprint version handling remain reused. Historical unresolved graph nodes are not silently rewritten to later canonical nodes; manual graph reconciliation is future work.
