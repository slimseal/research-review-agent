# V1 Experimental: known issues and validation scope

This is a publication summary, not a new test run or a scientific approval record. Core implementation and tests were not changed for publication preparation.

| Area | Observed limitation |
|---|---|
| Bibliography | Uncited duplicate-title candidates can block whole-library reconciliation and writing validation. A cited-only bibliography was produced in the single-paper demo, but overall writing validation failed. |
| PDF extraction | Some minus glyphs became NUL/control characters. Exact anchors were registered through existing native interfaces; ambiguous numbers were visually checked or retained as uncertain. No parser fix is included. |
| Source uncertainty | The demo paper's printed main-model depression interval conflicts with its point estimate and surrounding description. It was not silently repaired. Supplementary materials were unavailable. |
| Legacy artifacts | Generic validation can report legacy screening CSV column mismatches. Large journals can make some context/validation operations expensive. |
| Lab labeling | Native draft headings can say “literature review” even when the artifact is a provisional engineering sample. Always retain explicit scope labels. |
| Scientific review | The real demo has no completed independent evidence evaluation, final inclusion decision, independent claim-evidence audit or human final QC. |
| Cross-study inference | The downstream real-source demo uses only one paper. Multi-study synthesis, reliable gaps and field-wide coverage are not established by it. |

## What the existing demonstration established

The isolated real-paper run produced a 10-page reading record, 8 Evidence Items, 4 Claims, 14 claim-evidence links, an outline, a Section Brief and four draft paragraphs. Document, reading and synthesis structural checks passed. All four draft traces resolved to the source. Seven real-source integrity/negative checks were recorded as passing; these are not a scientific accuracy benchmark.

The earlier related-module engineering runs recorded 45 reading, 50 synthesis and 42 writing tests passing (137 total). They use engineering fixtures and do not prove live retrieval or scientific truth. They were **not rerun during publication preparation**, and are not a claim that the entire current repository test suite passed on a clean public clone.

Writing validation reported `DUPLICATE_REFERENCE_TITLE`. A same-context self-audit attempt was rejected with `FRESH_AUDITOR_NOT_WRITER_REQUIRED`. Final completion remained blocked by outstanding reviews, bibliography and provisional-lab restrictions. These failures are part of the result, not hidden exceptions.

## Privacy-filtered examples

Historical draft examples are supplied for inspection and existing fixture checks. Host-specific paths have been replaced with relative paths in the public behavior manifest. Private command transcripts and checksummed event journals are not distributed; they were not rewritten to manufacture a portable research history. These examples cannot be used as recovery archives or proof of genuine human approval.

No license has been selected. Before presenting this snapshot as open-source or production-ready, the owner must separately resolve licensing/source rights and the relevant reliability and review requirements. None of those claims is made by this experimental demonstration.
