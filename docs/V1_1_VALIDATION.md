# V1.1 validation — implementation is not availability

Date: **2026-10-22**. Local development branch: `codex/v1.1-database-access`. No GitHub push or release. Existing review projects were not read for test data, migrated, screened or advanced.

## Batch 1: access and request controls

Implemented endpoint-scoped configuration/probes, all requested access/failure states plus honest `not_verified`, redacted request receipts, fixed per-run possible-send budgets, retry accounting, redirect refusal and conservative uncertain-send stops. Explicit probes are not background calls. OpenAlex quota failure is not a global search veto; missing quota key sends no request.

Offline tests cover configuration-versus-verification, missing/invalid keys, entitlement, quota and rate limits, quota 401 with independent anonymous search success, retry/reopen accounting, conflicts, timeout/interruption, redirect handling, raw checksum tampering and secret-echo rejection. These use synthetic responses, not real authentication.

## Batch 2: real anonymous endpoint smoke test

One explicit engineering run, query `biodiversity`, one page and at most one record per provider, **six actual HTTP requests total**. No credentials, retries, redirects, hidden DOI lookup, account creation, PDF download or formal review approval. PubMed uses ESearch + metadata EFetch. A failed optional source did not block another source.

| Provider | HTTP sends | Actual outcome | Metadata records parsed | SearchRun |
|---|---:|---|---:|---|
| Crossref | 1 | Success, bounded first page | 1 | `SR-0D320F0834874ACE` |
| OpenAlex | 1 | HTTP 429, `QUOTA_EXHAUSTED` from the search endpoint | — | `SR-A1FA351094DB4F38` |
| PubMed | 2 | ESearch and EFetch succeeded | 1 | `SR-ACFB4EC5F8234DEE` |
| Europe PMC | 1 | Success, bounded first page | 1 | `SR-0A7F4FFF6D5A4D89` |
| Semantic Scholar | 1 | HTTP 429, `HTTP_RATE_LIMITED` | — | `SR-29CC86AE87264FF1` |

Three distinct canonical candidate IDs were registered. These are connectivity-test candidates, not screened relevant papers. There was no live cross-provider duplicate in this tiny sample; cross-provider duplicate behavior was tested with synthetic shared-DOI records. No saturation or topic-coverage conclusion is supported.

The run's `LIVE_RESULTS.json` links each provider to its budget ledger. Actual counts above come from those receipts, not fabricated zero-result rows. SearchRun provenance/raw SHA checks returned no issues; all five ledgers' count/sequence/raw checks passed. Failed HTTP responses retain safe status/error codes, not untrusted bodies that could echo credentials. Successful raw response bytes and PubMed's original JSON/XML are retained privately.

The smoke helper initially injected per-provider transports, so its original SearchRun `http_attempts` defaults were not bound to those helper ledgers; **use `LIVE_RESULTS.json` and its explicit receipt links for this run's counts**. Subsequent implementation links an in-project RecordedTransport into SearchRun automatically. That linkage was not presented as a second live run. Original smoke data remains preserved rather than retroactively claiming a new execution. The latest derived `LITERATURE_COVERAGE_REPORT_V3.json` marks unbound legacy HTTP counts unknown; the six real requests are evidenced by the original explicit receipts.

Artifacts are in the separate local engineering directory named `v11-provider-access-20261022`, not the software repository. No raw metadata responses, private configuration or local absolute paths are committed here. The script `scripts/live_provider_smoke.py` is opt-in and refuses an existing/formal project directory.

## Batch 3: ingestion, planning and coverage

PubMed, Europe PMC and Semantic Scholar adapters reuse SearchRun, raw-store replay, native IDs, DOI normalization, conservative Registry matching and conflict retention. The screening reader can resolve their stored abstracts without inventing text. Phase 3 validation now applies the existing provenance checks to these providers too; no scientific Gate was removed.

Offline tests exercise malformed/empty/missing data, missing DOI/abstract, PubMed ID mismatch and XML entities, metadata subrequest budget exhaustion, paging boundaries, filters, shared-DOI deduplication, replay and abstract locators. Source-plan tests cover health, education and archaeology starting recommendations, explicit inclusions/exclusions, recent search observations versus quota/stale reports, and unexecuted-query coverage accounting.

The generated public-health engineering Source Plan used the observed successful providers as “Recommended and available”; OpenAlex remained implemented but currently unavailable due to quota. This does not select/approve sources for any real study. Source recommendations are transparent heuristics requiring Codex's academic refinement, not comprehensive subject expertise.

## Test execution record

- Existing scholarly-discovery suite: **21 passed**.
- New provider/access/planning suite: **22 passed** after additions.
- First full regression invocation via `scripts/run_tests.sh`: **406 passed** in 332.765 seconds (included 19 new tests at that point).
- Compilation and registry/procedure validation: passed; **19 phases preserved**.
- Second full regression: **408 passed** in 328.296 seconds, before the final adjacent-XML-date correction.
- Final all-module regression including the XML correction: **409 passed across 20 modules**, no failed modules (existing unittest modules run in four isolated subprocesses).
- Final access/planning focused rerun: **22 passed**, including unknown legacy HTTP accounting rather than inferred zero requests.
- An additional synthetic default-pipeline check verified SearchRun-to-receipt binding, completed-run resume without another mock request, and provenance validation; **zero real network requests**.

Tests use the already-installed pinned PDF dependency. No package installation, historical scientific screening or researcher approval occurred. Offline fixtures are deliberately fictional and are not evidence of successful external access.

An offline inspection of the already-saved real PubMed XML found an adjacent-tag publication-date parsing gap: the original projection correctly left the year unknown rather than guessing. The corrected parser reads explicit Year/MedlineDate fields; the saved PMID `37549278` now parses as 2023. The new regression also checks replay from original XML rather than cached projections. No additional network request or rewrite of the original smoke data occurred.

## Not verified or unfinished

- No real configured-key login/activation was tested: this environment reported no relevant keys. Anonymous OpenAlex and Semantic Scholar did not succeed during this run; no automatic retry or database fallback was used.
- Multi-page live retrieval, real cross-provider duplicate matching and institutional entitlement are not validated by a one-record smoke test. Offline tests cover selected pagination and duplicate cases, not all external behavior.
- Scopus, Web of Science and PsycINFO adapters remain **not implemented**. Their access requirements are catalogued, not connected. No institutional or paid service was accessed.
- OpenAlex Agent-assisted enrollment is officially documented and assessed, but not automated or executed; user email consent and user activation remain mandatory.
- A shared transactional source-plan executor is not implemented. Each run/probe is hard-capped; Codex must allocate the total plan budget across them. Source selection is not a new authenticated scientific approval.
- Provider-only candidate reporting is not automatic relevance screening or scientific completeness judgment. Manual Google Scholar/specialist searches and genuine scientific Gates remain necessary where appropriate.
- Personal libraries and bulk imports remain deferred. Historical V1 writing/PDF limitations remain documented in [known issues](KNOWN_ISSUES.md).

Final static checks: `git diff --check`, compilation, registry validation and 56 local Markdown links passed. Changed text contained no matched personal absolute paths or common credential/private-key patterns; pattern scanning is not a guarantee against every form of sensitive content. Workflow registry and Gate core files are unchanged. All changes remain unstaged and uncommitted.

See [implementation priorities](V1_1_DEVELOPMENT_PLAN.md) and [beginner/access instructions](database-access.md).
