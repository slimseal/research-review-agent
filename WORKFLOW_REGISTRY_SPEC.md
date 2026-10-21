# Workflow Registry Specification

## Location and authority

`workflow/phases.json` is the authoritative definition of Phase 0–18. Python constants for phase names and required artifacts are derived from it. The registry is packaged with the distribution and loaded through `importlib.resources`.

Top-level fields:

- `registry_version`: registry contract version.
- `workflow_name`: human-readable name.
- `phase_count`: must equal 19.
- `quality_gates`: declared gate identifiers and meanings.
- `phases`: ordered records with IDs exactly 0 through 18.

## Phase record

Every phase must contain:

| Field | Contract |
|---|---|
| `phase_id` | Integer matching its 0–18 position |
| `phase_name` | Unique human-readable name |
| `purpose` | Topic-neutral methodological purpose |
| `prerequisites` | Direct earlier phase IDs required for legal entry |
| `required_inputs` | Inputs that must exist or be supplied |
| `allowed_inputs` | Additional permitted bases |
| `expected_outputs` | Canonical phase artifacts used by validation |
| `research_procedure` | Packaged relative path under `workflow/` |
| `validation_rules` | Named deterministic or review rules |
| `completion_conditions` | Conditions for completion, not merely file presence |
| `applicable_quality_gates` | Declared gates that apply to entry/progression |
| `human_review_requirements` | Decisions the model cannot self-authorize |
| `next_phase` | Next sequential ID, or `null` for Phase 18 |

## Validation rules

`validate_registry_data` rejects a missing top-level structure, phase-count mismatch, nonsequential IDs, missing keys, duplicate names, invalid or forward prerequisites, incorrect `next_phase`, non-list collection fields, unknown gate references and missing procedure resources.

`scripts/validate_workflow.py` validates both the registry and all 19 linked procedure files. `validate_project` also surfaces registry errors so corrupted control resources cannot be ignored during normal operation.

## Dependency and gate semantics

The controller checks the direct `prerequisites` for the target phase. It also evaluates only the hard gates listed for that phase. Phase 18's human signature is a completion condition and cannot be pre-satisfied by the model.

Gate implementation remains deterministic:

- `protocol_approval`: approved Protocol required for Phase 1 onward.
- `gate_1_screening_before_reading`: completed Phase 6 and valid nonempty screening before Phase 7 and downstream work.
- `gate_2_evidence_before_drafting`: completed Phase 8 and valid nonempty Evidence Matrix before Phase 15 and downstream drafting/audit.
- `gate_3_claims_before_gaps`: completed Phase 11 and valid nonempty Claim Map before Phase 12 and downstream gap/writing work.
- `final_human_qc`: named human record validated at Phase 18 completion.

`rragent next` reports the first incomplete phase and blockers. `rragent phase-context` returns the phase record, state, gate results, completion issues and full ordinary procedure as JSON.

## Change control

A Registry revision must keep Phase 0–18 semantics and artifact compatibility unless a separately reviewed migration is provided. Never reorder IDs or silently change the meaning of existing project state. Additive validation can be introduced only with regression tests and documented compatibility impact.

