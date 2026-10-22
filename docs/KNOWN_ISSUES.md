# V1.1 Experimental: known issues and validation scope

This documents retained V1 issues and V1.1 acceptance limits. Final integration
reruns the existing 436 tests without changing implementation/tests or performing
new scientific API requests. See [current acceptance](V1_1_ACCEPTANCE_ZH.md).
Historical results below remain historical, not a scientific approval record.

## V1.1 release-candidate limits

| Area | Current boundary |
|---|---|
| Beginner autonomy | Codex guides setup, protocol drafting and per-provider operations; not a single-command autonomous review. No usability study with novice participants was conducted. |
| Source modes | Standard/Comprehensive are planning guidance, not CLI presets or guarantees of sufficient coverage. |
| Access | Latest OpenAlex search was quota-limited; Semantic Scholar returned 429. Keyed access, institutional entitlement and live multi-page behavior remain unverified in these runs. |
| Total budget | Per-run/probe hard caps exist; no shared transactional source-plan executor. The Agent must account for the total authorized budget. |
| Scholar completion | not_performed works; valid records give performed_as_reported, not completed. completed_scope stays not_assessed. No automatic completed/incomplete state or attested scope-closure interface; this requested acceptance point is **partial**, not passed. |
| Manual handoff | Candidates remain not_imported; no automatic Scholar candidate import, formal provenance crosslink or duplicate resolution. Separate Crossref DOI reconciliation requires authorization and normal phase prerequisites. |
| Identity confidence | Live ERIC/OpenAIRE duplicate was a moderate-confidence title/author/year match. Three OpenAIRE multi-ID aggregates remain unresolved; exact DOI/PMID/PMCID contracts also use offline fixtures, not clean live crosswalk proof. |
| Relevance | Coverage counts are not scientific relevance evaluation; initial live results include out-of-scope candidates. |
| Scientific acceptance | No real multi-paper, all-Gates-approved end-to-end systematic review has been completed. Independent scientific audit is not replaced by tests. |
| Distribution | V1.1 Experimental is a source pre-release under MIT; package version remains 0.1.0.dev0, not PyPI 1.1. Third-party content is not relicensed and no binary assets are supplied. |
| Installation scope | Final normal online installation passed in two fresh isolated environments (macOS / Python 3.13.2), including the PDF extra and installed CLI. The earlier offline backend failure was environmental, not a required offline-install guarantee. Other OS/Python combinations are not verified. See [final gate](V1_1_FINAL_RELEASE_GATE.md). |

| Area | Observed limitation |
|---|---|
| Bibliography | Uncited duplicate-title candidates can block whole-library reconciliation and writing validation. A cited-only bibliography was produced in the single-paper demo, but overall writing validation failed. |
| PDF extraction | Some minus glyphs became NUL/control characters. Exact anchors were registered through existing native interfaces; ambiguous numbers were visually checked or retained as uncertain. No parser fix is included. |
| Source uncertainty | The demo paper's printed main-model depression interval conflicts with its point estimate and surrounding description. It was not silently repaired. Supplementary materials were unavailable. |
| Legacy artifacts | Generic validation can report legacy screening CSV column mismatches. Large journals can make some context/validation operations expensive. |
| Lab labeling | Native draft headings can say “literature review” even when the artifact is a provisional engineering sample. Always retain explicit scope labels. |
| Scientific review | The real demo has no completed independent evidence evaluation, final inclusion decision, independent claim-evidence audit or human final QC. |
| Cross-study inference | The downstream real-source demo uses only one paper. Multi-study synthesis, reliable gaps and field-wide coverage are not established by it. |

## What the historical V1 demonstration established

The isolated real-paper run produced a 10-page reading record, 8 Evidence Items, 4 Claims, 14 claim-evidence links, an outline, a Section Brief and four draft paragraphs. Document, reading and synthesis structural checks passed. All four draft traces resolved to the source. Seven real-source integrity/negative checks were recorded as passing; these are not a scientific accuracy benchmark.

The earlier related-module engineering runs recorded 45 reading, 50 synthesis and 42 writing tests passing (137 total). They use engineering fixtures and do not prove live retrieval or scientific truth. They were **not rerun during publication preparation**, and are not a claim that the entire current repository test suite passed on a clean public clone.

Writing validation reported `DUPLICATE_REFERENCE_TITLE`. A same-context self-audit attempt was rejected with `FRESH_AUDITOR_NOT_WRITER_REQUIRED`. Final completion remained blocked by outstanding reviews, bibliography and provisional-lab restrictions. These failures are part of the result, not hidden exceptions.

## Privacy-filtered examples

Historical draft examples are supplied for inspection and existing fixture checks. Host-specific paths have been replaced with relative paths in the public behavior manifest. Private command transcripts and checksummed event journals are not distributed; they were not rewritten to manufacture a portable research history. These examples cannot be used as recovery archives or proof of genuine human approval.

Original project material uses [MIT](../LICENSE); [third-party rights](third-party-notices.md)
remain separate. Licensing does not establish production readiness, scientific
accuracy, full-text redistribution permission or completed human research review.
