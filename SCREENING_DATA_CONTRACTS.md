# Screening data contracts — v1 (Round 2F)

Implementation: `research_review_agent/screening/contracts.py` and `pipeline.py`; `rragent screening-schema` exports fields, enums and the artifact ownership/dependency catalog. This is an additive screening contract, independent of Evidence Schema v1/v2. Existing IDs, citation edges and scientific-evidence fields are not migrated.

`ScreeningDecision` has decision/project/paper identity, Protocol version, criteria version, candidate-set version, stage, source basis, decision, separate literature role, reason-code list, explanatory interpretation, reviewer type/ID/time, optional DocumentVersion ID, uncertainty flags, approval state, superseded ID, immutable packet ID, criterion IDs, exact source facts, prior-stage ID and review note. Runtime validation rejects unsupported stages, reasons, roles, missing applicable criteria, invalid quotations and inconsistent bindings. Proposal inputs cannot assign human approval.

Stages: title → abstract → fulltext_eligibility. Decisions: include / exclude / uncertain / defer. Roles: include_core / include_context / include_theory / include_method, plus explicitly justified approved extensions. No population, exposure, effect size or other domain-specific empirical fields are universally required.

Source facts contain a permitted location and exact quote; new full-text include/exclude recommendations require identity, observed version and eligibility purposes. Their packet binds exact PDF SHA, PDF page, parser version and frozen text. These are not independently human-confirmed SourceAnchors or extracted scientific findings. Ambiguous or layout-dependent locations require researcher inspection; no semantic accuracy is certified by substring matching. Historical records without explicit version quotations remain readable but cannot serve as current final decisions; append a corrected proposal instead of editing history.

Criteria versions retain rules, applicability, role/version policy, approved Protocol hash, exact candidate IDs, reasoned scope exceptions, per-record Registry hashes and deterministic candidate-set checksum. Approval records reference the exact criteria object hash. Every version is retained. An unaffected decision may still reference its original criteria version after a new scope approval; applicability/policy equality is checked rather than rewriting its historical version.

Authoritative screening state is `screening_data` in the EXISTING `.review/state.json` / checksummed `.review/events.jsonl`, not a competing Registry or controller. Packets under `04_screening/packets/` are immutable, content-addressed and checksummed. Decision history is append-only in state; generated JSONL/CSV files are recoverable projections. The JSONL includes superseded records, not just current rows. Recovery regenerates it without rewriting prior decisions.

## Artifact catalog

| Artifact | Owner | Representation and invalidation |
|---|---|---|
| SCREENING_MASTER.csv | Phase 6 | Latest decision per candidate/stage; history and scope |
| EXCLUSION_LOG.csv | Phase 6 | All historical/provisional exclusions; use coverage for final counts |
| SCREENING_DECISION_HISTORY.jsonl | Phase 6 | Full append-history projection; workflow journal |
| SCREENING_CRITERIA_VERSION.json | Phase 6 | All criteria versions and declared approvals; Protocol/Registry/scope |
| SCREENING_COVERAGE_REPORT.md | Phase 6 | Counts, provisional/final distinction; current decisions, access and upstream queue |
| FULLTEXT_ELIGIBILITY_LOG.csv | Phase 6 | All fulltext-stage states, including missing text; packets/document hashes |
| ACQUISITION_STATUS.csv | Phase 5, consumed by 6 | Derived paper/document availability rows; Registry, manifest, attempts, access review, eligibility state |
| GATE1_VALIDATION_REPORT.json | Phase 6 | Informational assessment snapshot; always recomputed before progression |

All screening artifacts are in `04_screening/`, except acquisition status in `03_library/`. The Phase 6 registry declares its required projections; acquisition can also be exported in Phase 5 before criteria exist. Missing abstracts, missing PDFs, missing human decisions and unprocessed upstream citations remain distinct.

Legacy screening CSVs remain structurally readable but no longer establish Gate 1 completion. Before the first new export, their bytes are retained under `04_screening/legacy/<sha>-<name>`. They are not silently promoted to approved decisions. Existing Evidence Schema v1/v2, DocumentVersion and SourceAnchor contracts are unchanged. Historical reports describing a one-row gate are superseded by this gate policy.
