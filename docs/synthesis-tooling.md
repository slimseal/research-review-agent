# Synthesis Tooling Tutorial

Install the core package and, for PDF-backed trace checks, its existing `pdf` extra. No Skill or model API is required. Academic analysis is explicitly supplied by Codex/researchers.

## Official workflow

Start with `validate`, `next` and `phase-context`. Formal Phase 9 needs approved Protocol and completed, current Phase 8. Do not substitute any demonstration lab.

```bash
rragent synthesis-schema
rragent phase-context --project /path/to/review --phase 9
rragent advance --project /path/to/review --phase 9 --status in_progress
rragent synthesis-context --project /path/to/review
rragent synthesis-corpus --project /path/to/review --config selection.json
```

Selection JSON contains evidence_decisions (one include/exclude/defer + reason per EvidenceItem), coverage_limitations, search_coverage and selection_rationale. The CLI returns the versioned corpus ID. Stop for actual human selection review; do not self-sign.

Use `synthesis-submit --kind theme --config theme.json` (and theory/method/controversy). Read `synthesis-schema` for mandatory fields. All records need research_question, evidence_ids, record_refs, uncertainty, generator and example_data. Derive content from the active Protocol and inspected evidence; demonstration plan files are not default research content.

For each map, submit an assessment covering all current map record IDs and all included evidence IDs, a populated/none_warranted/deferred disposition and a reason. Retain genuine emptiness; deferred work blocks completion.

```bash
rragent synthesis-inspect --project /path/to/review --id THEME-returned-id
rragent synthesis-assess --project /path/to/review --id THEME-returned-id --config semantic-review.json
rragent synthesis-completion --project /path/to/review --phase 9
```

Semantic JSON needs outcome=supported/uncertain/unsupported, reviewer, rationale, all twelve checks with status/reason, and evidence_checks with a rationale per referenced ID. This records actual reasoning; it does not execute a model.

Only the real human reviewer should run:

```bash
rragent synthesis-review --project /path/to/review --id THEME-returned-id --action approve --by "Actual reviewer" --rationale "Actual review basis"
```

Repeat review for the corpus and all relevant records/assessments. Then normal advance controls the phase. Phase 10 adds boundary records; Phase 11 adds claims and separate normalized links; Phase 12 adds bounded gap candidates after Gate 3. A rejected candidate stays visible; an unreviewed, uncertain or deferred retained record cannot pass.

## Correction and trace

Submit a revision with the same record_id and supersedes_revision equal to the current revision_id, or use human `--action revise --changes changes.json`. IDs persist, content/history appends, approval resets. Rework stale dependencies in phase order. `synthesis-inspect` shows full source trace and prior reviews.

```bash
rragent synthesis-validate --project /path/to/review
rragent synthesis-completion --project /path/to/review --phase 11
# Preserve unexpected file edits first:
rragent synthesis-recover --project /path/to/review
```

A structurally valid result is not semantic correctness, human approval or phase completion.

## Isolated demonstration

```bash
python scripts/run_synthesis_pilot.py --project /new/separate/fictional-pilot \
  --fixture examples/round2h-synthesis/fictional-corpus.json \
  --plan examples/round2h-synthesis/fictional-plan.json
```

All data and findings in that fixture are fictional. For an already available isolated reading lab, use `synthesis-lab-init --project /new/lab --source /existing/reading-lab`. Copies preserve source bindings; original files and approval states remain unchanged. Every lab remains provisional and refuses official completion. Real-source examples are source-bound demonstrations, not reusable default claims.
