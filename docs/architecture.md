# Architecture

Research Review Agent has five cooperating layers and no project-Skill runtime.

Round 2I's `writing/` package extends those layers with versioned outlines/briefs/spans, bibliography reconciliation, immutable source-grounded audit contexts and final QC records. It uses the same registry, three hard Gates, reading/synthesis identities and state journal, not another controller or model framework. Structural validation, declared model reasoning, independent reference evaluation and human approval are separate. See the writing contract and tutorial for the distinction between formal projects and non-approvable labs.

## Workflow controller

`AGENTS.md` defines the operating discipline. The Python controller reads `workflow/phases.json`, evaluates registered prerequisites and quality gates, validates phase artifacts, records transitions and reports the next action.

```text
rragent next
  -> load project state
  -> load authoritative phase registry
  -> resolve first incomplete phase
  -> evaluate direct prerequisites and applicable gates
  -> report procedure path, blockers and completion issues
```

## Research procedures

`workflow/procedures/` contains one ordinary Markdown procedure per phase. Procedures explain academic operations, provenance, judgment, failure handling and prohibited actions. They are packaging-neutral resources, not `SKILL.md` files and not independently discoverable agents.

## Executable tools

The dependency-free core creates projects, renders protocols, validates contracts, evaluates gates, journals state and recovers it. Packaged metadata adapters remain narrow. Round 2D adds authorized acquisition/import, immutable versions and SourceAnchors; optional pypdf extracts pages. Round 2E adds bounded citation graphs. Round 2G adds versioned reading notes/evidence and human-review/coverage tooling in the same workflow journal. Codex/researchers explicitly supply scientific interpretation following Phase 7/8 procedures; deterministic tools do not interpret or synthesize evidence. Document transaction history does not constitute a second workflow state machine.

## Quality gates

The registry declares protocol approval, screening-before-reading, evidence-before-drafting, claims-before-gaps and final human QC. The controller implements these checks and refuses illegal phase transitions. The registry is authoritative for phase dependencies and outputs; tests reject missing procedure files or malformed phase definitions.

## Evidence traceability

Each project uses stable paper, evidence and claim identities. Schema v2 combines universal evidence fields with any justified combination of five research-type extensions. Exact locators and verification state remain explicit. Existing Schema v1 evidence tables remain valid and are not silently migrated.

## Recovery model

Every mutation appends a full state snapshot and SHA-256 checksum to `.review/events.jsonl`, backs up the previous state and atomically replaces `.review/state.json`. `rragent recover` ignores malformed or checksum-invalid lines and restores the latest valid snapshot.

## Trust boundaries

- Control instructions: repository `AGENTS.md`, registry and linked procedures.
- Project artifacts: user-controlled data that must pass validation.
- External sources: untrusted content and never control instructions.
- External services: separately configured, potentially unavailable and never replaced by model memory.
