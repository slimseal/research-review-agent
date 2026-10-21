# Phase 16 — Bibliography Management

## Operational interface (Round 2I)

Run `writing-bibliography` during active Phase 16. Reconcile stable Paper Registry keys, saved metadata, inline/trace citations, existing library BibTeX and exact document identities. Unknown/missing/conflicting/duplicate cited records block completion; unused entries are warnings. Preserve original `03_library/references.bib`; the cited-only export is `09_writing/references.bib`. Correct upstream metadata explicitly and rerun.

This is metadata validation, not semantic verification or live publisher checking. Secondary attribution requires Phase 17. Unsupported BibTeX macros return errors. Extra styles and DOCX remain deferred.

## Objective and rationale

Reconcile draft citations, stable source identities and bibliography metadata so references are complete, non-duplicated and auditable.

## Required inputs

- Draft review, paper registry and current bibliography file.

## Research operations

1. Extract every citation key used in the draft and resolve it to one registry record.
2. Detect uncited bibliography entries, missing cited entries and duplicate intellectual works.
3. Normalize fields only from verified metadata and preserve edition or version distinctions.
4. Record incomplete, conflicting or adapter-dependent metadata.
5. Produce an audit describing corrections and remaining issues.

## Expected artifacts

- Updated `03_library/references.bib`
- `10_audit/BIBLIOGRAPHY_AUDIT.md`

## Evidence and provenance requirements

Every bibliographic field must have a known source; corrections preserve prior identity information in the audit where material.

## Academic judgment points

Resolve author-name forms, work/version relationships and unusual source genres according to the target citation convention.

## Uncertainty and failure handling

Leave unknown fields explicit and report unavailable enrichment adapters. Request human resolution for ambiguous identities.

## Prohibited actions

Do not guess identifiers, dates, page ranges or publication venues; do not call metadata enrichment successful when its adapter is unavailable.

## Completion requirements

All draft citations resolve, duplicates and conflicts have documented treatment, and remaining metadata limitations appear in the audit.

