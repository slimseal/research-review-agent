# Phase 4 — Citation Snowballing

## Objective and rationale

Extend discovery through backward references, forward citations and related-source relationships while keeping the expansion path auditable.

## Required inputs

- Seed and master discovery tables.
- Identified seed records with sufficient metadata.
- Approved, substantively populated Protocol; completed valid Phase 3; active Phase 4 for mutations.

## Packaged execution

Citation expansion requires a separately confirmed seed/provider/direction plan and request budget. Choosing a Phase 3 metadata-search database does not authorize another citation provider. Use only confirmed operations; never substitute another source automatically.

**Current no-expansion gap:** the V1 registrar requires nonempty canonical seeds and a nonempty supported provider plan. Completion expects attempts for each planned path and current human stopping review. There is no implemented reviewed “not requested” completion route. If the researcher declines citation expansion, keep that decision, explain the block and stop this formal path; do not invent failed attempts, add dummy seeds, force an expansion or hand-edit completion flags. The 19-phase structure and Gates are unchanged.

Follow `docs/citation-tooling.md` in a checkout. Installed clients use this procedure and CLI `--help`.

1. Run `citation-seeds --project <path>`. Select registered identities with a reason for each. Legacy/manual CSV rows require explicit canonical reconciliation first; they are never silently replaced.
2. Write a seed config with `selected_paper_ids`, per-ID `selection_reason`, `provider_plan` objects (`provider`, `direction`), `expansion_depth_limit`, `max_requests`, and `max_candidates`. All limits apply across runs in the same numbered round, including replaced seed sets. No automatic seed promotion.
3. Run `citation-seed-register --project <path> --config <json> --by <selector>`. Stop for human seed/plan review. Only after explicit approval use `citation-seed-approve --project <path> --by <human> --note <review>`.
4. Run `citation-expand --project <path> --provider <provider> --direction <direction> --round 1` for each approved path. Crossref supports backward; OpenAlex forward; OpenCitations backward/forward. No automatic service fallback. Related recommendations are optional and currently not implemented.
5. Inspect `citation-status`, `citation-unresolved`, `citations-validate`; use `citation-resume --run-id <id>` for recoverable partial runs, `citation-replay --run-id <id>` for read-only raw/direction verification, and `citations-recover` for journal recovery and artifact regeneration.
6. Run `citation-report`. Review round yield, unresolved sources, unprocessed raw records, failures, exclusions from the provider plan and disciplinary/language/network coverage. Do not label quota/limits/missing coverage as saturation.
7. Stop for human review. Only an actual human decision authorizes `citation-review --by <human> --note <review> --limitations <accepted limitations> --stop-reason <reason>`. This pins a checksum of the seed, runs, candidates and graph; any subsequent mutation requires new review.
8. Run `citation-report --completion`, then `advance --phase 4 --status completed` only if validation passes. The tool never completes Phase 4 automatically. Phase 5/6 and Gate 1 remain unchanged.

Infrastructure pilots must use `citation-lab-init` in a new independent directory. `citation-lab-doi` verifies seed metadata using the existing Crossref pipeline. `citation-seed-approve --pilot-selection` records only a user-authorized pilot selection, not human research approval; lab Phase 4 completion is prohibited.

For an explicitly authorized strict six-request round, use `budget_policy.policy_id=bounded_first_page_v1` and `citation-budget-preflight` before registration or execution. The strict policy requires exact Protocol/project bindings, local seed identities, Crossref backward/OpenAlex forward, one hop, first twenty returned positions per seed/direction, and no extra lookup/retry/page/redirect. Seed approval must include the expected version and plan hash. Durable possible-send reservations include uncertain attempts; `REQUEST_SEND_UNKNOWN` blocks new sends and cannot be waived by resume. See the strict-policy section in `docs/citation-tooling.md`. These transport constraints do not change the nineteen phases, original Gates or human stopping review.

## Research operations

1. Select seeds using a documented relevance rationale.
2. Trace backward references, forward citations and related items only through configured data sources or inspected reference lists.
3. Record the seed, relationship type, source system and returned identifier for every candidate.
4. Deduplicate against the master set without erasing discovery lineage.
5. Apply a transparent stopping rule and inspect likely citation-network bias.

## Expected artifacts

- `02_discovery/BACKWARD_CITATIONS.csv`
- `02_discovery/FORWARD_CITATIONS.csv`
- `02_discovery/RELATED_PAPERS.csv`
- `02_discovery/SEED_SET.json` and historical `seed_sets/`
- `02_discovery/CITATION_EDGES.csv` and `CITATION_GRAPH.json`
- `02_discovery/CITATION_EXPANSION_LOG.csv`, `citation_runs/` and `EXPANSION_CANDIDATES.json`
- `02_discovery/EXPANSION_ROUND_REPORT.md` and `CITATION_COVERAGE_REPORT.md`
- `02_discovery/CITATION_REVIEW.json` (official reviewed completion only)
- Updated discovery and canonical registry; immutable responses under existing `02_discovery/raw/`.

## Evidence and provenance requirements

Every relationship must identify both the seed and the basis used to assert it. A related-source recommendation is not evidence of citation or relevance.

## Academic judgment points

Choose defensible seeds, recognize canonical-source and recency bias, and judge when saturation or diminishing returns supports stopping.

## Uncertainty and failure handling

Report unavailable citation indexes and incomplete reference lists. Mark ambiguous identities for later resolution.

## Prohibited actions

Do not fabricate citation links, use model memory as a citation index, or equate citation frequency with evidential quality.

## Completion requirements

All approved tracing paths have auditable results or explicit failures/limits, and a named human accepts the stopping rationale, unresolved references and coverage limitations. Empty/missing reference data cannot establish no references. Hash-valid artifact exports and source rows are required. Historical stale runs remain visible. A successful request or a synthetic test cannot substitute for human review.

