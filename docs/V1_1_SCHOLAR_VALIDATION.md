# V1.1 Google Scholar manual supplement — validation

Date: 2026-10-22. Branch: `codex/v1.1-database-access`. No commit or push.

## Implemented in this batch

- Offline `scholar-prepare`: validates and renders Agent/researcher-authored 3–5 queries,
  suitability/rationale, gaps, year settings and bounded stopping scope.
- Chinese beginner checklist, empty session log and candidate CSV. No demo papers
  are inserted into user materials. Re-running against an existing output refuses overwrite.
- `source-plan` distinguishes `google_scholar` from automatic providers, respects
  explicit choices/exclusions, and proposes manual work with assessment still required.
- `literature-coverage` reads manual records separately from SearchRuns/Registry;
  not_performed, performed_as_reported and invalid_records are distinct. Counts are
  observations, not unique or included studies; planned scope completion is not inferred.
- [Usage/field semantics](google-scholar-supplement.md) and
  [beginner prompt](../prompts/google-scholar-supplement.md), linked from AGENTS.md.

## Actual isolated beginner exercise

RQ: How do novice teachers describe developing classroom authority during their first year of teaching?

Executed init, scholar-prepare, source-plan, literature-coverage and status against a
new isolated planning project. Four queries cover direct authority terms, broader
classroom-management vocabulary, first-year interviews and identity terminology.
Their purposes and possible scope drift are explicit; they do not assert findings.

Outputs: PLAN.json, SEARCH_PLAN.md, CHECKLIST_ZH.md, empty SESSIONS.json,
header-only RESULTS.csv, LITERATURE_SOURCE_PLAN.json and LITERATURE_COVERAGE_REPORT.json.
All four queries remain **not_performed**; zero manual candidate observations;
no SearchRun, registry insertion, PDF access or scientific approval. Project remains
Phase 0 in_progress / Phase 1–18 pending. Exercise artifacts live outside this repository.

This proves preparation/report generation, not Scholar connectivity or retrieval quality.
Only official help documentation was browsed; no Scholar result page or citation API
was accessed. No browser extension was installed.

## Compatibility and safety checks

- 12 new isolated tests passed: offline CLI/rendering, no overwrite, plan validation,
  source exclusions, unperformed status, zero-results distinction, malformed logs,
  provenance/scope, repeated sessions/cumulative caps, unsupported import/approval
  claims, candidate uncertainty and separation from automatic counts.
- Read-only rerun of reporting on saved real Batch 2 metadata: API provider details,
  overlaps, normalization totals, **51 observations / 47 canonical Paper IDs** unchanged.
  Scholar adds not_performed only. File hashes before/after are identical; no new API request.
- New exercise reporting also preserves every project file hash.
- Full regression: `PATH="$PWD/.venv/bin:$PATH" bash scripts/run_tests.sh` passed:
  **436 tests in 316.398 seconds** (424 existing + 12 new). Workflow Registry and all
  19 procedure checks passed. These offline regression tests are not live Scholar retrieval.
- New local documentation links checked; git diff --check passed. New source/docs/tests
  contain no local absolute paths or obvious token/private-key patterns. This is a bounded
  content check, not a claim of comprehensive secret detection.
- Compared with a pre-edit recoverable archive: existing files changed this round are
  only AGENTS.md, cli.py and scholarly/source_plan.py. Other Batch 1–2 code and tests,
  workflow/phases.json, procedures and scientific Gate implementations remain unchanged.
  New manual module/docs/prompt/tests are additive. No old research project was modified.

## Explicit limits

- No Scholar provider, crawler, bulk API, automatic result retrieval or CAPTCHA bypass.
- Queries are authored by Codex/researcher; CLI validation is structural, not academic judgment.
- User-reported session provenance is not authenticated identity or independent review.
- Citation/related branches require separate bounded human logs; not included in ordinary
  query counts. Ranking changes and unchecked positions remain coverage limitations.
- Manual candidates remain not_imported. Existing resolve-doi can perform separately
  authorized Crossref registration in active Phase 3 or 5; it is not Scholar import and
  was not called. Automatic manual-to-Registry linkage/deduplication remains unsupported.
- No complete literature coverage, relevance rate, full-text access or Gate approval is claimed.
- README/release consolidation is deferred to the next user-authorized round.
