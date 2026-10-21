# Acquisition status and targeted eligibility

No new downloader was built. `acquisition-status --export` derives a ledger from canonical Paper Registry identities, existing DocumentVersions, AcquisitionAttempts, `ACQUISITION_REVIEW.json` and eligibility history. One row represents a paper-document version; papers without a local version receive an explicit placeholder. Count papers by distinct ID, not by document rows.

Fields include bibliographic registration, identity verification, full-text availability, document ID/version, attempt status, access basis, license, local reference, document-parser status, eligibility assessment status, remaining action and human-review requirement. A document with matching bytes is still not independently identity-verified; the eligibility packet adds an observed identity passage. Unknown license stays unknown, and article access does not establish software-license rights.

Phase 5 can close when all registered records have stable identities, bibliography and a named/date-stamped per-paper access disposition with a basis: acquired (matching valid DocumentVersion), unavailable, manual_access_required or pending_screening. The latter permits title-first work, not silent dropping. Pending or unavailable records must still be resolved in Phase 6 or explicitly omitted from a bounded human-approved scope. An inaccessible study is not automatically irrelevant or excluded.

Acquisition statuses and eligibility statuses are separate. Eligibility distinguishes available-not-assessed, assessed-provisional/approved, unavailable, currently unauthorized route, extraction insufficient, wrong document/version, awaiting authorized import and unresolved judgment. Missing local text does NOT prove global inaccessibility. An attempted HTTP failure must not be described as “no paper exists.”

Additional acquisition uses the existing Phase 5 tools after reopening Phase 5 through the controller, maintaining Phase 4 approval requirements. Update the explicit acquisition review, close Phase 5 and refresh the ledger before resuming Phase 6. No automatic human review is written.

Targeted Phase 6 inspection reads only designated eligibility pages, with exact PDF hash/version/location and quoted identity/eligibility passages. Existing `document-parse` and `anchor-create` remain Phase 7 operations. After Gate 1, they also reject a different or non-included document version. Standalone document infrastructure labs retain their original testing behavior; screening labs cannot use them to bypass reading gates.

Formal eligibility judgments still require a researcher. Parser success is not complete readability or content verification. No OCR, paywall bypass, credential use or Evidence Matrix extraction was added.
