# Case-Neutral Research Evidence Schema v2

Decision date: 2026-10-12

## Decision

New projects use `schema_version: 2.0.0`, with a small universal evidence core and zero or more composable research-type extensions. Existing `1.x` projects retain the legacy Evidence Matrix columns and remain readable. The kit performs no automatic migration.

## Compatibility impact assessed before implementation

The original Evidence Matrix treated population, sample size, study design, exposure, outcome, effect size, mediator, and moderator as universal columns. Replacing those headers in an existing project would make its file fail header validation and could change the meaning of stored values.

The implemented compatibility boundary is therefore:

| Protocol version | Evidence header | Validator behavior | Migration |
|---|---|---|---|
| `1.x` | Legacy quantitative-leaning fields | Legacy header and evidence-strength checks | None; data remains unchanged |
| `2.x` | Case-neutral universal core | v2 header, proposition, locator, verification, and extension checks | New projects only |

The validator reads each project's `00_protocol/PROTOCOL.json` and selects the matching contract. A regression test initializes a version 1 project, writes a legacy evidence row, and validates it successfully.

## Universal core

The v2 Evidence Matrix columns are:

1. `evidence_id`
2. `paper_id`
3. `research_question`
4. `source_basis`
5. `research_context`
6. `evidence_type`
7. `research_types`
8. `finding_argument_proposition`
9. `evidence_locator`
10. `limitations_uncertainty`
11. `verification_status`
12. `example_data`
13. `extension_json`

This core can represent an empirical result, qualitative interpretation, historical proposition, conceptual argument, or material-evidence inference without pretending all sources report an exposure and outcome.

Paper identity, screening, and claim interfaces remain stable. `extension_json` is still governed by `00_protocol/DOMAIN_EXTENSION_SCHEMA.json`.

## Composable research-type extensions

The catalog defines five non-exclusive types:

- `quantitative_empirical`
- `qualitative_empirical`
- `historical_documentary`
- `theoretical_conceptual`
- `archaeological_material`

A protocol may select more than one, as demonstrated by the historical/archaeological test. Each evidence row stores a non-empty JSON array in `research_types`. Required extensions are enforced only when their declared types apply to that row, so a documentary-only row in a mixed project does not need archaeological-only fields. Selecting a type does not make every catalog field mandatory.

Quantitative fields—including population, sample size, predictor/exposure, outcome, effect direction, effect size, uncertainty, mediator, and moderator—remain available but are no longer universal.

## Protocol v2 contract

New draft protocols contain:

- neutral scope fields: units of analysis, phenomena/topics, relationships/questions, contexts, geography, time, languages, and source types;
- `research_types` as a list;
- research subquestions;
- explicit concept definitions and concept blocks;
- dynamic `search.strategy_groups` with `status`;
- operational include/exclude criteria;
- typed evidence extensions with research-type applicability;
- resolved and pending human decisions.

The CLI now supports:

- `update-protocol`: merge a reviewed fragment into a draft while protecting project ID, exact RQ, schema version, status, timestamps, and approvals;
- `protocol-status`: report schema validity, substantive population, pending review, and approval separately;
- `validate --require-substantive-protocol`: reject a structurally valid but empty scaffold;
- approval refusal while consequential human decisions remain pending.

## Search and reading behavior

`research-review-protocol` and `research-review-search` derive strategy groups from the approved question, source types, concepts, and research design. Fixed Core/Outcome/Mechanism/Boundary/Method families are not required.

`research-review-reading` and `research-review-evidence` first record the universal core, then load only the selected extension fields. Full-text locators may use page/section/figure/table; documentary and material evidence may additionally use archive, catalogue, or object references.

## Files implementing the decision

- `research_review_agent/constants.py`
- `research_review_agent/project.py`
- `research_review_agent/validation.py`
- `research_review_agent/resources/schema_catalog.json`
- `research_review_agent/cli.py`
- `workflow/procedures/phase_00_protocol.md`
- `workflow/procedures/phase_01_concept_map.md`
- `workflow/procedures/phase_02_search_strings.md`
- `workflow/procedures/phase_07_reading.md`
- `workflow/procedures/phase_08_evidence.md`
- `AGENTS.md`

## Tests

Automated tests cover:

- v2 headers for new projects;
- v1 header and row compatibility;
- quantitative, qualitative, and archaeological extension selection;
- multi-type behavior through the real historical/archaeological Protocol invocation;
- row-level conditional requirements in a composed historical/archaeological extension schema;
- rejection of unknown/missing/wrongly typed extension values;
- rejection of extensions assigned to unselected research types;
- method-specific non-leakage into qualitative and archaeological projects;
- preservation of draft status and pending human review.

## Deferred migration work

No command converts v1 rows to v2. A future migration must:

1. preserve the original files;
2. map each legacy field explicitly;
3. record lossy or ambiguous mappings;
4. create a reviewable migration log;
5. require human confirmation before replacing canonical artifacts.

SourceAnchor/DocumentVersion normalization, richer claim-evidence links, and artifact invalidation remain future work; Schema v2 does not claim those capabilities are complete.

