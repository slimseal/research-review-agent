# V1.1 implementation plan and scope decisions

Updated 2026-10-22. Product goal: a beginner supplies an RQ and scope; Codex recommends complementary lawful sources, asks once for source/query/budget confirmation, and handles authentication only when needed. See [access specification](database-access.md) and [validation](V1_1_VALIDATION.md).

## Baseline actually found

- Local and GitHub branch enumeration showed only `main`, at `09a728015081c300ad653f987e725f627741f876`. No existing V1.1 feature branch or implementation was found.
- Nine tracked Markdown edits and four new Markdown files from the prior source-selection work were preserved and revised, not discarded.
- Existing native metadata adapters: Crossref/OpenAlex. `provider-status` previously reported configuration booleans only. Existing citation, single-PDF, Registry, SearchRun, screening, evidence and writing infrastructure were retained.
- Work now lives on local `codex/v1.1-database-access`. No push, tag, Release, license change or old-project run is part of this work.

## Priority batches

| Priority | Scope | Current outcome / remaining condition |
|---|---|---|
| 1 | Endpoint-scoped access states and credential-safe checks | Implemented: offline `not_verified`, explicit bounded live probe, specified failure classifications, no credentials in reports. Tested synthetically and public endpoint probes. |
| 2 | Crossref/OpenAlex continuity | Existing search retained; bounded HTTP receipts added. OpenAlex search is independent of quota inspection; missing quota key makes no request. Crossref live success; OpenAlex live quota exhaustion honestly retained. No activated-key validation possible without a configured key. |
| 3 | Important no-key/low-configuration APIs | Implemented PubMed ESearch/EFetch, Europe PMC core search, Semantic Scholar relevance search; existing normalization/Registry/SearchRun/replay used. PubMed/Europe PMC live success; Semantic Scholar anonymous rate limiting, not successful retrieval. |
| 4 | Free-key / institutional expansion | Optional free-key headers/parameters and bounded verification implemented. OpenAlex enrollment assessed, not automated. Scopus/WoS/PsycINFO catalogued as unimplemented with separate access requirements. Actual adapters and entitlement-specific live validation remain unfinished. |
| 5 | Beginner recommendations and coverage | Offline source-plan heuristic, prompts, five-category planning and read-only coverage accounting implemented. Codex supplies discipline-specific judgment. Whole-plan transactional execution/budget enforcement and automatic relevant-unique-candidate assessment are not claimed. |

## Acceptance requirements for unfinished institutional work

Batch 2 implemented and live-tested ERIC, arXiv and OpenAIRE Graph v3, with cross-provider identifiers, source-preserving replay and expanded coverage accounting. See [Batch 2 validation](V1_1_BATCH2_VALIDATION.md) and the [role-specific provider roadmap](provider-roadmap.md). CORE is catalogued but not implemented; detailed official contract access was blocked during verification. Do not confuse that documentation failure with a tested CORE search failure.

For each provider/endpoint, verify official request and response contracts, pagination, data-use rules, API entitlement and relevant subscribed product/view. Implement normalization, preserved provider IDs, raw provenance, duplicates/conflicts and per-request budget receipts; add malformed/auth/quota/resume/offline tests. Mark implementation and live verification separately.

Do not assume a website subscription, personal subscription, API key, institutional IP or token by itself permits every endpoint. Do not borrow or share institutional credentials or automatically buy access. Missing rights keep that path `not_executed` with `requires_institutional_access`, while already-authorized public paths can continue. PsycINFO access may require project-specific permission; Web of Science Starter and advanced products must not be conflated.

## Non-goals and preserved controls

No Zotero/personal-library/bulk import; no new model runtime or Skills; no alteration to the 19-phase registry or scientific approval/Gate rules. No account registration without separate consent. No institutional query without genuine access. No raw private records, PDFs, API keys or actual reviewer identities in GitHub.

The CLI's new HTTP cap is per run/probe. Until a separate shared executor is implemented and tested, Codex must allocate and sum the approved whole-plan budget; this limitation is explicit. Do not call the current implementation a fully unattended multi-database review service.
