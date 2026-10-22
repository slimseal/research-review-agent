# Deferred personal-library intake design

**Future planning only — not a V1 entry prompt or an implemented connection.** V1 onboarding uses [start-review](../../prompts/start-review.md) and [connect-database](../../prompts/connect-database.md). See [future support requirements](personal-library-support.md).

Before a separately authorized implementation, resolve:

- Manager: Zotero, EndNote, Mendeley, Paperpile or local files; whole library versus a named Collection or selected items.
- Input: metadata, PDFs, notes or attachments; supplied format and original identifiers.
- Permission: exact read-only metadata scope, separately authorized attachments, no source edits or synchronization.
- Optional supplementary search/citation tracking, selected providers and budgets; never force an unwanted online search.
- Private destination and provenance: source type, item/Collection IDs, actual import timestamps, export/PDF hashes and versions, conflicts and multiple origins.
- Controlled ingestion, identity matching, conservative duplicate handling, resumability and a valid formal Phase 3–5 path.

Never inspect private libraries merely because this design exists. Metadata is not full text; library membership is not inclusion. Do not upload private paths, exports, notes, PDFs or keys. Do not fake SearchRuns, approvals or completed phases to compensate for missing functionality.
