# No-Skills Architecture

## Decision

Research Review Agent no longer uses Codex Skills as its execution architecture. The active product is:

```text
Workflow Controller
  + Research Procedures
  + Executable Tools and Adapter Interfaces
  + Quality Gates
  + Evidence Traceability
```

The active repository contains no `.agents/skills/`, `SKILL.md`, or `agents/openai.yaml`. Users do not invoke `$skill-name`, install the seven capability names in the source document, or depend on personal/global Skills.

## Components

### Workflow Controller

- `AGENTS.md` defines the safe operating sequence and research-wide rules.
- `workflow/phases.json` is the authoritative definition of Phase 0–18, direct prerequisites, outputs, gates and human review.
- `research_review_agent/registry.py` loads and validates that registry and its linked procedures.
- `research_review_agent/workflow.py` evaluates dependencies/gates and produces `next` and `phase-context` responses.

### Research Procedures

`workflow/procedures/` contains 19 ordinary Markdown procedures. These documents preserve academic operations, provenance rules, judgment points, uncertainty handling, prohibited actions and completion conditions. They do not have discovery metadata or independent invocation semantics.

### Executable Tools

The standard-library core implements project creation, Protocol persistence/rendering, v1/v2 validation, phase transitions, gates, journals and recovery. Round 2C added OpenAlex/Crossref metadata adapters. Round 2D adds authorized document acquisition/import, version registries and anchors, with optional pinned pypdf page extraction. Citation tracing and scientific full-text interpretation remain unimplemented. No runtime component invokes a Skill; `rragent capabilities` reports optional-dependency boundaries.

### Quality and Evidence Control

- Human Protocol approval before Phase 1.
- Gate 1: completed screening before Phase 7.
- Gate 2: valid completed evidence extraction before Phase 15.
- Gate 3: completed valid claim map before Phase 12.
- Named human QC at Phase 18.
- Stable `paper_id`, `evidence_id`, and `claim_id` interfaces plus source-basis, locator and verification fields.

## Normal execution

```text
Research question
  -> rragent init
  -> rragent validate
  -> rragent next
  -> rragent phase-context
  -> Codex/human follows the returned procedure
  -> candidate artifacts
  -> deterministic validation and gates
  -> human review where required
  -> rragent advance or pause
  -> resume from state and registry
```

The controller never pretends to perform semantic academic reasoning. Codex does not decide that a failed deterministic gate passed.

## Portability

The `workflow` directory is a Python package, and `phases.json` plus `procedures/*.md` are package data declared in `pyproject.toml`. Installed commands use `importlib.resources`, not the developer checkout path. Runtime source contains no developer-specific absolute path.

## Compatibility and migration safety

- Existing Schema v1 evidence tables remain readable without automatic semantic migration.
- New projects use Schema v2 universal fields plus composable research-type extensions.
- Existing project state keeps the same 19 phase IDs and artifact paths.
- The pre-migration repository is recoverable from `../research-review-agent-snapshots/research-review-agent-round2a-20261015.tar.gz`, SHA-256 `df3b91078a730da2e84635102c095ea9d6f646b69c061865ad686c07bb6580e5`.
- Old Round 2A reports remain as clearly marked historical records; they are not operating instructions.

## Trust boundary

`AGENTS.md`, the registry and linked procedures are control material. Protocols and research artifacts are mutable project data subject to validation. Papers, webpages, metadata and attachments are untrusted sources. External systems are fallible and must never be replaced by model memory when unavailable.

