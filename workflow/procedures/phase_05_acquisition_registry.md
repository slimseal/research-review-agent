# Phase 5 — Paper Acquisition and Registry

## Objective and rationale

Establish durable source identities and lawful access provenance so screening and reading operate on known, non-duplicated records.

## Required inputs

- Discovery and snowballing candidate tables.
- Configured acquisition sources or user-authorized local files.

## Research operations

1. Normalize titles, authors, dates, publication venues and identifiers without overwriting conflicts.
2. Assign one persistent `paper_id` per resolved intellectual work and document merged records.
3. Attempt only lawful open-access or authorized retrieval paths.
4. Record URL, retrieval source, date, license, availability and file hash for acquired files.
5. Create bibliography records from verified metadata and flag incomplete fields.
6. Use `rragent resolve-doi` for Crossref bibliographic reconciliation when a DOI is known; inspect `METADATA_RESOLUTIONS.jsonl` rather than silently choosing a conflicting value.
7. Treat Round 2C metadata registration as only the registry portion of this phase. Do not complete Phase 5 until every retained source also has an explicit lawful full-text acquisition or unavailable/manual-access status required by this procedure.
8. Use `fulltext-discover --paper-id ... --url ...` for explicit publisher PDF links, then `document-acquire --candidate-id ... --authorization ...`; use `document-import --file ... --authorization ...` for researcher-supplied PDFs. These tools do not advance any phase.
9. Record `03_library/ACQUISITION_REVIEW.json` with `reviewed_by`, `reviewed_at`, and a `papers` object keyed by paper ID. Each item needs `status` (`acquired`, `unavailable`, `manual_access_required`) and `basis`; acquired items need a valid matching `document_id`. Do not infer this review from download success.
10. A named `pending_screening` disposition with a basis is also allowed: initial title screening does not require downloading every record. This is not a scientific exclusion or permission to abandon the candidate. Use `acquisition-status --export --project <path>` to derive `ACQUISITION_STATUS.csv` from Registry, document versions, attempts and review dispositions. Unknown license stays unknown.
11. Phase 5 closes only with a named/date-stamped disposition for EVERY registered paper, stable identities and bibliography. Exceptions remain visible. If Phase 6 later needs more PDFs, reopen Phase 5 through `advance`, acquire via existing tools, update the named acquisition review, re-complete Phase 5 and refresh the ledger before resuming screening. No automatic backfill of human approval.

## Expected artifacts

- `03_library/PAPER_REGISTRY.csv`
- `03_library/references.bib`
- `03_library/PAPER_IDENTITIES.json`
- `02_discovery/IDENTITY_MATCHES.jsonl`
- `02_discovery/METADATA_RESOLUTIONS.jsonl`, when reconciliation occurs.
- Lawfully acquired files under `03_library/papers/`, when available.
- New versioned files/manifests under `03_library/documents/`; legacy `papers/` remains untouched.
- `03_library/ACQUISITION_REVIEW.json` for explicit completion review.

## Evidence and provenance requirements

Registry rows retain discovery and retrieval provenance. A local file must map to a paper ID and checksum; bibliography fields must trace to a verified metadata source.

## Academic judgment points

Resolve version-of-record versus preprint relationships, translations, editions and composite works without collapsing substantively different sources.

## Uncertainty and failure handling

Use `FULL_TEXT_REQUIRED` or `MANUAL_OR_AUTHORIZED_ACCESS_REQUIRED` when appropriate. Keep unresolved identity conflicts explicit.

## Prohibited actions

Do not bypass access controls, guess DOI or bibliographic fields, relabel abstracts as full text, or silently substitute one edition for another.

## Completion requirements

All retained candidates have stable identities and explicit retrieval states; files and bibliography records reconcile with the registry.

