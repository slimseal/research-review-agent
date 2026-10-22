# V1.1 Batch 2 — open databases and real multi-source integration

Date: 2026-10-22. Branch: `codex/v1.1-database-access`. No commit/push, no production-review execution. Existing uncommitted Batch 1 work was retained; a recoverable checkout snapshot was created before edits.

## Implemented

- ERIC education JSON search, arXiv Atom search and **OpenAIRE stable JSON Graph v3** search. Native query syntax, bounded pagination, normalized metadata, raw response replay, provider status, SearchRun and Registry integration.
- Exact namespaced PMID/PMCID matching supplements DOI and conservative metadata fingerprints. All origin pointers and native identifiers/manifestation relations are retained. Ambiguous primary identifiers are unresolved rather than silently merged.
- arXiv deposit/version identity stays separate from a related journal DOI; preprints are not assumed peer reviewed. OpenAIRE publications/data/software/other outputs and their instances remain distinguishable.
- Coverage includes raw counts, unique candidates, source-only candidates, pairwise overlap, metadata missingness, failures/skips, budgets and stopping reasons. Relevance is `not_evaluated`. Offline replay is not counted as new live retrieval.
- Safe Retry-After/rate-limit evidence is persisted. A required wait longer than 60 seconds pauses an optional retry rather than shortening the provider's wait. Default/live-test retries remain disabled.

## Live test design and exact scope

New isolated engineering corpora only; no Protocol approvals, human identities or phase completion were simulated. Raw artifacts remain outside Git under directories named:

- `v11-batch2-multisource-20261022`: original live results, request manifest, receipts and raw bytes.
- `v11-batch2-validated-20261022`: first offline PubMed identity correction, no new HTTP.
- `v11-batch2-crosswalk-20261022`: one additional, pre-recorded OpenAIRE identity query; original aggregate interpretation is retained but superseded below.
- **`v11-batch2-final-20261022`**: final source-preserving offline replay after all identity checks. Use this directory's canonical Registry and coverage, not superseded intermediate identity projections.

Main RQ: *How is physical activity associated with academic performance in school-aged children?*

| Provider | Actual query strategy | HTTP requests | Raw observations | Final registered candidates from source | Source-only candidates |
|---|---|---:|---:|---:|---:|
| Crossref | Bibliographic terms: physical activity, academic performance, school children | 1 | 10 | 10 | 10 |
| PubMed | Fielded Title/Abstract Boolean query for activity, performance, children/school | 2 (ESearch + EFetch) | 10 | 10 | 10 |
| Europe PMC | Equivalent concepts in native TITLE_ABS syntax | 1 | 10 | 10 | 10 |
| ERIC | Physical activity AND academic performance/academic achievement | 1 | 10 | 10 | 9 |
| OpenAIRE | Phrase/Boolean search; second query uses a known PubMed title + DOI `pid` filter | 2 | 11 | 8 | 7 |
| Semantic Scholar | Relevance-search terms for the same main question | 1 | **Failed, not successful zero results** | 0 stored | 0 stored |

Main corpus: **51 raw observations = 47 canonical candidates + 1 duplicate observation + 3 unresolved identity observations**. The source candidate counts overlap and must not be summed as unique papers. Of 47 canonical candidates, 46 are source-only and one is found in both ERIC and OpenAIRE.

Separate computing/education RQ: *How do knowledge-tracing models represent student learning?* arXiv `ti:"knowledge tracing"` returned **10 records / 10 preprint candidates** in one request. These are not mixed into the main RQ corpus.

**Nine actual scholarly-test HTTP requests total**, including PubMed's metadata subrequest and the second OpenAIRE query. ERIC/arXiv each used one request, OpenAIRE two; every page requested at most ten records. No keys, paid credits, retries, redirects, subsequent pages, DOI-resolution requests or PDFs. Official documentation consultation is separate from these recorded scholarly test requests.

Semantic Scholar returned HTTP 429 (`HTTP_RATE_LIMITED`); no Retry-After/rate-limit headers were supplied in that response. It was paused immediately, and arXiv still ran successfully afterward. OpenAlex received no new request; its previous quota-exhaustion observation remains historical, not a new search result. CORE was not searched or implemented because the official detailed API reference could not be inspected (403); no unverified connection is advertised.

## What real identity checks established

1. ERIC `EJ1495517` and OpenAIRE `doi_________::f85ed360a89eab6e84df92e068e5700b` matched the title, first author and year of *The Impact of Time and Energy Expenditure in Physical Activity on Academic Performance: A Mixed-Methods Study*. Both origins remain under `P0000031`. This is a **moderate-confidence metadata match**, not independently verified full-text identity or eligibility. The ERIC abstract describes university students, illustrating why retrieved hits are not automatically within the school-aged RQ.
2. PubMed PMID `27182986` has primary DOI `10.1249/mss.0000000000000901` and PMCID `PMC4874515`. Direct XML inspection exposed that descendant-wide ArticleId parsing could overwrite a paper's DOI/PMCID with identifiers of cited references. The parser now reads only the paper's own identity container; tests cover a conflicting reference list. Existing research projects were not rewritten.
3. The targeted OpenAIRE response for that DOI also includes DOI `10.1249/mss.0000000000000966` and PMIDs `27182986`/`27182987`. It is an aggregate, not a safely resolved single-paper duplicate. It is retained **unresolved**, despite the shared PMCID. Two other initial OpenAIRE objects also contain multiple distinct DOIs and remain unresolved.
4. Exact DOI, PMID and PMCID matching, conflicting identifiers, legacy loading and provenance retention are covered by offline contracts. **This live run does not prove a clean PMID-only or DOI-only cross-provider merge**; the actual clean overlap used metadata, while the targeted crosswalk correctly exposed ambiguity. Do not substitute synthetic tests for this distinction.

## Coverage limitations and missing metadata

- All ten Crossref source observations lack abstracts; one PubMed observation lacks an abstract. Metadata completeness denominators exclude the three unresolved OpenAIRE aggregates and distinguish source IDs from canonical DOI filled by another source.
- ERIC's default response does not consistently include DOI or journal/source metadata; missing fields remain absent. Provider-only candidates are not “relevant unique studies.”
- First-page ordering differs across databases. PubMed and Europe PMC returned no matching canonical paper in these tiny initial samples; that does not imply their databases are disjoint.
- Broad education queries include higher-education or non-target samples. Preprints, reviews and heterogeneous research outputs need actual screening. No inclusion/quality/relevance decisions were made.
- No saturation, systematic-review adequacy, literature completeness, or independent-cohort claim is supported. Language/design/date gaps and specialist institutional coverage still require planned research judgment.

## Validation and boundaries

Final artifacts contain per-run receipts and SHA-256 raw provenance. All final main/arXiv discovery-provenance checks returned no issues. Raw PubMed JSON/XML and arXiv Atom bytes remain available; replay parses original XML, not cached derived fields. `latest_normalization` identifies current processing while original SearchRun counters/history remain unchanged.

Focused offline tests cover native syntax/paging, raw replay, malformed/over-limit responses, typed outputs, preprint/version separation, DOI/PMID/PMCID conflict handling, aggregate ambiguity, PubMed reference-ID isolation, throttle evidence and pause behavior, coverage/replay accounting, and explicit source preferences. **Final `bash scripts/run_tests.sh`: 424 tests passed in 381.389 seconds**, including 15 new Batch 2 tests and the existing 409. Compile and 19-phase Workflow validation also passed. These synthetic regressions are separate from the nine real scholarly-test HTTP requests above.

Local Markdown links and `git diff --check` passed. The changed-file scan found no personal absolute paths, credential patterns or files above 1 MB; no raw responses or PDFs were added to Git. Both HEAD and local main remained at the original V1 commit, with all work uncommitted on the feature branch. No core scientific Gate or workflow-registry changes were made.

The 19-phase registry, Gates 1–3, independent-evaluation gate, No-Skills architecture, and old review-project artifacts were not changed. Existing instructions/CLI remain responsible for formal human research approvals. No new Google Scholar, personal-library, institutional-access or full-text module was developed. [Remaining provider roles/access conditions](provider-roadmap.md).
