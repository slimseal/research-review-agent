# Future personal-library and bulk-import support

**Deferred scope, not a V1 feature or onboarding path.** V1.1 development starts with a Research Question and an Agent-recommended, user-confirmed database plan. Personal libraries, Collection ingestion and hybrid library-first workflows require separately authorized future development; no delivery version is promised.

The [deferred intake design](personal-library-intake.md) preserves future scoping and privacy requirements. Current entry prompts are [start-review](../../prompts/start-review.md) and [connect-database](../../prompts/connect-database.md).

## Existing components versus missing integrations

| Capability | Actual status |
|---|---|
| Single local PDF | Implemented: `document-import` accepts one authorized PDF in an eligible Phase 5, with explicit Paper ID or unresolved identity, version, SHA-256 and page count. This remains unchanged in V1. |
| Batch PDF folder | Not implemented; individual imports are not folder ingestion or synchronization. |
| RIS / BibTeX batch ingestion | Not implemented. The writing bibliography parser reconciles existing references, not arbitrary imports into Registry. |
| CSV metadata / DOI lists | No general controlled batch importer. `resolve-doi` is one separately authorized Crossref network lookup, not offline list ingestion. |
| Zotero local library / exported Collection / Web API | No native connector, Collection mapping or attachment ingestion. |
| EndNote / Mendeley / Paperpile | No native library connector. Vendor export options do not establish import support here. |
| Native cross-provider identity matching | Existing Registry matches provider IDs, DOI and conservative bibliographic fingerprints; ambiguity, conflicts and related versions are retained. |
| PDF-to-paper binding | Existing explicit Paper ID binding and DocumentVersion storage; not automatic library attachment matching or semantic identity proof. |
| Library + database deduplication | Reusable native components exist, but end-to-end personal-library ingestion and matching are not implemented or verified. |

The prior source audit used code/CLI inspection and six existing isolated offline component tests (PDF import/idempotence/corruption and native identity matching). It did not establish any real personal-library connection. Those tests are not rerun for this documentation-only scope reduction. See [document tooling](../document-tooling.md) for the retained single-PDF feature.

## Formal import-only progression is still missing

- [Phase 3 validation](../../research_review_agent/validation.py) expects search-attempt records and native SearchRun provenance. The additional database adapters do not provide a controlled ImportRun alternative for a fresh library-only review.
- [Citation registration/completion](../../research_review_agent/citations/pipeline.py) requires seeds, a provider plan, planned attempts and human stopping review. There is no reviewed “expansion not requested” completion route.
- [Document acquisition/import](../../research_review_agent/documents/pipeline.py) still requires its formal prerequisites and active Phase 5. A lawful local PDF does not supply missing upstream approvals.

Do not force unwanted searches, fabricate attempts, edit canonical CSVs or use engineering-lab approvals to bridge these gaps.

## Requirements for separately authorized future work

1. Prioritize controlled RIS/BibTeX batch ingestion, then mapped CSV/DOI lists: original IDs, export hashes, ImportRun provenance, validation, conflicts, idempotence and resumable transactions.
2. Define reviewed import-based discovery and no-expansion dispositions within the existing 19 phases, without weakening screening, evidence or human Gates. A format parser alone is insufficient.
3. Reuse Registry matching with per-origin provenance. Test same-work library/database duplicates, no-DOI ambiguity, related versions and distinct reports. Paper duplication and cohort overlap are different judgments.
4. Add scoped attachment/folder mapping, per-file authorization, explicit unresolved outcomes and version/hash checks.
5. Consider read-only manager connectors only after separate authorization and official access review. No write-back or synchronization by default.

## Privacy and evidence boundaries

Private metadata, Collections, notes and attachments require explicit scoped permission. Never recursively inspect unrelated folders or edit a live reference-manager database. Keep personal paths, raw exports, notes, PDFs and API keys outside the software repository and GitHub.

Preserve source type, original identifiers, actual import time, file version/hash, identity conflicts and multiple origins. Planned imports are not completed events. Metadata does not establish full-text access, user ownership does not establish eligibility, and curated libraries do not establish comprehensive search coverage.
