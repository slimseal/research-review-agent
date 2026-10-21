# Paper Identity and Deduplication

## Identity precedence

The registry applies the following order within one research project:

1. Exact provider plus provider-record ID.
2. Exact normalized DOI already registered.
3. Exact normalized title + first author + publication year, only when all three are available and the DOI does not contradict an existing DOI.
4. New identity.

DOIs are normalized by removing DOI URL/label prefixes, URL-decoding, trimming safe terminal punctuation and case-folding only strings that match the DOI syntax. Provider IDs remain separate and are never replaced by the DOI.

`paper_id` values are allocated once as `P0000001`, `P0000002`, and so on inside `PAPER_IDENTITIES.json`. Provider/DOI/fingerprint indexes make repeated retrieval idempotent. Repeated searches append provenance but retain the original project ID.

## Ambiguity policy

A record is not auto-merged when its available metadata cannot discriminate among existing same-title candidates, or when otherwise identical fallback metadata carries conflicting unidentified DOIs. The registry emits an `IdentityMatch` with:

- `status: review_required`
- no selected `paper_id`
- all competing paper IDs
- a human-readable non-merge reason

The candidate remains in `DISCOVERY_MASTER.csv` with its provider/raw provenance and a blank canonical ID. This is intentional; uncertainty is not converted into a duplicate.

## Publication versions

Recognized values are `preprint`, `accepted_manuscript`, `published_version` and `unknown`. Different verified DOIs are not collapsed merely because normalized title/author/year match. When version information indicates a preprint/manuscript/published relationship, each receives its own `paper_id` and both records list one another in `related_versions`.

The adapters do not claim to infer every version relationship. Unknown or conflicting cases remain reviewable.

## Metadata reconciliation

When a provider ID or DOI resolves to an existing paper, each canonical field is handled separately:

- Missing canonical fields may be filled from the new source.
- Equivalent normalized values are confirmed.
- Missing candidate values leave existing values unchanged.
- Conflicting non-empty values are retained side by side in `METADATA_RESOLUTIONS.jsonl`; the canonical value is not silently overwritten.

One provider yields `single_provider`. Agreement from multiple providers yields `verified_cross_provider`. Any retained conflict yields `conflict` plus field-level notes.

These labels concern bibliographic metadata only. They do not verify eligibility, methods, results or scientific claims.

## Provenance

Every canonical record retains provider IDs, SearchRun IDs, raw-response path and record index, retrieval timestamp, verification status, conflict notes and related versions. `PAPER_REGISTRY.csv` exposes these details in `extension_json`, while `PAPER_IDENTITIES.json` is the machine-readable identity source.
