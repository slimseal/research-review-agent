# Google Scholar manual supplementary search

This is an offline planning and user-recording tool, **not a Scholar API or crawler**.
The Agent performs topic-specific academic planning; the CLI validates the input
structure and renders files. The CLI does not independently infer a scientifically
adequate strategy from a sentence. No global Skill is required.

## Status interpretation for V1.1 acceptance

| Requested distinction | Actual implementation |
|---|---|
| Not performed | `not_performed` when there are no valid session records. |
| Work reported / potentially incomplete | `performed_as_reported`; inspect `unperformed_query_ids`, ranges and stop reasons. |
| Completed within agreed scope | **Not machine-determined.** `completed_scope` remains `not_assessed`, even when every query has a record. |
| Invalid record | `invalid_records`; do not count as completed work or successful zero results. |

The CLI has no `completed`/`incomplete` transition or formal manual-scope closure
interface. Record the researcher's actual assessment in a separate versioned note,
without editing report status to claim a machine pass. This is an explicit remaining
acceptance gap, not something repaired during release preparation. Scholar Button
is an optional browser extension, never an Agent connector.

## Beginner entry

Give Codex your RQ, or use [the supplementary-search prompt](../prompts/google-scholar-supplement.md).
The Agent assesses whether Scholar could complement the selected databases, respects
explicit exclusions, and proposes 3–5 short queries with different concepts/synonyms.
It explains why those queries help and what they could miss. These are proposals,
not claims that any papers exist or have been found. Confirm manual scope once before searching.

The generated Chinese checklist explains year filters, Cited by, Related articles,
All versions, lawful access, recording and stopping. Google Scholar Button is
optional; no installation or private browser access is required.

## Agent preparation contract

Create an input JSON outside the repository with these fields:

- `research_question`: the actual RQ, without changing an approved Protocol.
- `suitability`: recommended, optional, or not_recommended.
- `rationale`, `coverage_gaps`: topic-specific judgments, not a generic promise of completeness.
- `year_filter`: approved years, or explicitly pending confirmation. Do not impose a new date restriction.
- `stop_rule`: planned checking limit and access/error stops; a budget stop is not saturation.
- `queries`: 3–5 objects containing unique `id`, `query`, `purpose`, integer `max_results_to_check` (1–1000).

Prefer short keyword combinations and quoted phrases, not a verbatim PubMed/Scopus
expression. Syntax/academic suitability needs Agent review; structural validation
does not establish it. Broad and narrower variants should not presuppose a finding.
Keep prior versions when changing any plan or user record.

```sh
rragent scholar-prepare --plan scholar-plan-input.json \
  --output "$PROJECT/02_discovery/manual/google_scholar"
rragent literature-coverage --project "$PROJECT" \
  --plan "$PROJECT/LITERATURE_SOURCE_PLAN.json" --output coverage-v2.json
```

`scholar-prepare` refuses an existing output directory. It writes `PLAN.json`,
`SEARCH_PLAN.md`, `CHECKLIST_ZH.md`, empty `SESSIONS.json` and header-only `RESULTS.csv`.
It does not touch project state, approvals, Registry, or SearchRun history. A partially
written output after a filesystem error must be preserved/inspected; retry into a new
directory, never infer successful search from file existence.

## Manual records and coverage semantics

The checklist documents every session/result field. Only fill actual reported work;
preserve the user's source note. `record_source` is provenance, **not identity authentication**.
Results may be unverified; missing authors/year require an explanatory note. Record
possible duplicate Paper IDs without merging them. Metadata is not full text or inclusion.

Coverage reads `02_discovery/manual/google_scholar/` independently of API SearchRuns.
No records => `not_performed`; valid sessions => `performed_as_reported`; malformed
records => `invalid_records`. It reports unperformed query IDs, checked observations,
manual candidate observations, pending identity/duplicate checks and coverage gaps.
Even if every query has a session, completion of its planned scope remains
`not_assessed`: a partially checked query is not automatically complete. A plan's
claimed status never proves execution. Manual candidates do not increase automatic
canonical/unique counts, and repeated observations are not independent papers.

Automatic completed/failed/unexecuted searches remain in the existing provider report.
This module tracks ordinary planned-query result checks; additional Cited by or
Related articles branches need a separately bounded human log and are not included
in these counts. No automatic scientific relevance/coverage assessment is supplied.

## DOI and Registry handoff: existing capability and remaining gap

The real `resolve-doi` command can fetch one DOI from Crossref and reconcile it via
the existing Registry. It is a **new authorized network operation**, not importing a
Scholar result, and must meet the current approved Protocol and active Phase 3 or 5
Controller requirements. Example, only after authorization:

```sh
rragent resolve-doi --project "$PROJECT" --doi 'ACTUAL_DOI' \
  --strategy-version 'ACTUAL_STRATEGY_VERSION' --max-requests 1 --max-attempts 1
```

No such call is made by this module. It does not provide manual/bulk candidate import,
automatic Scholar-to-Paper-ID provenance linkage, or automated duplicate resolution.
Keep manual rows `not_imported`; after separate successful DOI registration, preserve
the Crossref SearchRun and any researcher-reviewed cross-reference in a separate
handoff note. Do not edit normalized Registry or fabricate a SearchRun. Candidates
without a resolvable DOI remain in the supplementary list pending supported intake.

## Safety and primary references

Do not store private PDF files, browser cookies, account identifiers, private notes,
or library paths in Git. Manual materials belong to the private project. Do not
automate Scholar pages, bypass CAPTCHA, or promise comprehensive coverage.
No 19-stage Registry or scientific Gate has been changed.

- [Official Scholar search help](https://scholar.google.com/intl/en/scholar/help.html)
- [Google Scholar Button official store listing](https://chromewebstore.google.com/detail/google-scholar-button/ldipcbpaocekfooobnbcddclnhejkcpn)

Documentation checked 2026-10-22; no result pages or Scholar searches were fetched.
