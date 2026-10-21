# Phase 6 — Literature Screening

## Objective and rationale

Apply the approved eligibility criteria consistently at title, abstract and full-text stages, preserving a reviewable trail for every decision.

## Required inputs

- Approved inclusion and exclusion criteria with a version identifier.
- Paper registry and the best available authorized source basis.

## Research operations

### Executable interaction

1. Inspect `screening-schema`, `acquisition-status`, the approved Protocol and candidate identities. Valid, genuinely reviewed Phase 4 and Phase 5 are mandatory for official work.
2. Prepare criteria config: `rules` with stable `id`, exact approved `text`, `kind` include/exclude, applicable `stages`; optional explicitly bounded `paper_ids`. Declare `candidate_ids` and justify every omitted canonical ID in `scope_exceptions`. Unresolved external references remain in the upstream queue, not invented papers. Optional `role_extensions` require justifications; accepted document versions must be explicit.
3. `screening-criteria --config <json> --reason <reason>` retains the previous versions. Stop for actual human criteria and scope review, then `screening-criteria-approve --by <human> --note <review>`. No automatic approval.
4. `screening-context --paper-id <id> --stage title` returns title/basic metadata only. Propose include/exclude/uncertain/defer with quoted title, applicable criterion IDs, explanation, role only for include, and uncertainty flags. Uninformative titles normally remain uncertain. No DOI is not grounds for exclusion. Respect recorded preprint/published relationships without automatically collapsing them.
5. Save the JSON with `screening-propose --config <json>`. Treat include at title/abstract as permission to consider the next stage, NOT final inclusion. Exclude requires a stated criterion and exact source basis. Do not invent confidence from absent information.
6. For non-excluded current title records obtain `--stage abstract`. Use original provider abstracts/provenance, quote exact text under `source_facts`, and put inference in `explanation`. Missing abstracts permit only uncertain/defer. Do not infer methods or outcomes absent from the abstract.
7. For non-excluded abstract records use `--stage fulltext_eligibility --document-id <id> --pages <explicit pages>`. At most five pages per request; inspect only passages needed to resolve eligibility. Exact identity/title or DOI, observed version and eligibility passages are required for include/exclude. Check version/access, compare the rendered location when needed, and retain extraction/identity uncertainty. A quote's presence does not prove its interpretation; request researcher review. No scientific reading notes or evidence rows.
8. `screening-inspect --decision-id <id>` retrieves original source basis. The researcher may `screening-review --action approve|override|reject|uncertain|defer|reopen --by <human> --note <reason>`, with `--changes <json>` for override. These are declared identities, not authenticated accounts. A model must only propose.
9. Inspect `screening-queue`, `screening-exclusions`, `screening-coverage`, `screening-validate` and `screening-gate`. Resolve/review every required candidate. Scope exclusions are separate from scientific exclusions. Do not infer completeness from stage totals or one full-text row.
10. Only when completion validation permits, use `advance --phase 6 --status completed` and recompute `screening-gate`. Phase 7 accepts only the resulting eligible document versions. Gate reports are snapshots, never approval tokens.

All commands above require `--project <path>`. See `docs/screening-tooling.md` in a checkout. Installed users have this procedure and CLI help; no personal environment files are needed.

1. Screen at the protocol-defined stages without using information unavailable at that stage.
2. Record `include`, `exclude` or `uncertain`, the criteria version, decision basis and reviewer role.
3. Use standardized, single-primary exclusion reasons while retaining explanatory notes when needed.
4. Escalate ambiguous cases and apply adjudication consistently.
5. If criteria change, version the amendment and identify records requiring rescreening.

## Expected artifacts

- `04_screening/SCREENING_MASTER.csv`
- `04_screening/EXCLUSION_LOG.csv`
- `04_screening/SCREENING_DECISION_HISTORY.jsonl`
- `04_screening/SCREENING_CRITERIA_VERSION.json`
- `04_screening/SCREENING_COVERAGE_REPORT.md`
- `04_screening/FULLTEXT_ELIGIBILITY_LOG.csv`
- `03_library/ACQUISITION_STATUS.csv`
- `04_screening/GATE1_VALIDATION_REPORT.json`

## Evidence and provenance requirements

Every decision states whether it relied on title, abstract or full text and who made it. Example rows are rejected unless an explicitly labeled example-mode test is running.

## Academic judgment points

Interpret criteria without post-hoc tailoring, separate topical relevance from eligibility, and recognize when insufficient information warrants uncertainty.

## Uncertainty and failure handling

Keep unresolved items uncertain; do not force a decision. Record unavailable full text and seek human adjudication for consequential cases.

## Prohibited actions

Do not exclude for unstated reasons, backfill decisions from desired findings, or treat unverified example records as eligible evidence.

## Completion requirements

Every candidate in the current human-approved scope has a current final human-declared decision; exclusions reconcile with history. Uncertain/deferred candidates inside that scope block Gate 1. An explicit, bounded, human-approved limited corpus may proceed with warnings while out-of-scope and upstream unresolved records remain visible; this never marks those records scientifically excluded. Protocol/criteria/scope, upstream reviews, source packets, documents and projections must be current and intact.

