# Tutorial: Question to Reproducible Metadata Discovery

After genuinely reviewed evidence and synthesis, continue with [Writing, tracing, bibliography and independent audit](writing-tooling.md) for Phase 13–18. This extends the same controller; it never supplies missing upstream approvals.

For Gate-1-eligible full text, continue with [Scientific reading and evidence extraction](reading-tooling.md). This extends the same workflow, not a separate runtime. Model interpretation and human scientific approval remain separate.

For Phase 6, continue with [the three-level screening tutorial](screening-tooling.md), after genuine Phase 4 stopping approval and Phase 5 disposition review. Do not use a development pilot as proof of completed upstream research.

Round 2E adds a [citation tooling tutorial](citation-tooling.md): approved seed plans, bounded backward/forward expansion, immutable provenance, recovery, coverage reports and mandatory human stopping review. It does not perform screening or scientific interpretation.

Round 2D document acquisition, local import, parsing and anchors have a separate [document-tooling tutorial](document-tooling.md). They do not bypass Phase 4, Protocol approval or Gate 1.

Steps 1–4 work offline. Step 5 performs a real provider request and must be run only after human Protocol approval, reviewed search planning and confirmation of provider access.

## 1. Create an isolated project

```bash
rragent init \
  --question "How is the selected phenomenon understood across its relevant evidence?" \
  --domain "custom" \
  --output reviews/tutorial-review

rragent validate --project reviews/tutorial-review
rragent next --project reviews/tutorial-review
rragent phase-context --project reviews/tutorial-review --phase 0
```

Phase 0 is `in_progress`; later phases are pending. `phase-context` includes the ordinary Phase 0 procedure.

## 2. Develop the draft in Codex

Ask without any `$skill-name`:

> Follow AGENTS.md and the workflow registry for `reviews/tutorial-review`. Complete only the Phase 0 research operations. Derive a method-appropriate scope, subquestions, concept definitions, proposed search strategies, eligibility criteria and research-type evidence fields from my question. Save a substantive draft, leave human decisions explicit, do not approve it and do not search.

Codex should use `rragent update-protocol` to preserve protected identity and approval fields. Check the result:

```bash
rragent protocol-status --project reviews/tutorial-review
rragent validate --project reviews/tutorial-review --require-substantive-protocol
rragent next --project reviews/tutorial-review
```

The expected state is schema-valid, substantively populated, pending human review and not approved.

## 3. Approve Phase 0

Resolve pending human decisions in the draft, review all scope and evidence-field choices, then run:

```bash
rragent approve-protocol --project reviews/tutorial-review --by "Your name"
rragent next --project reviews/tutorial-review
```

The next action should be Phase 1. Approval freezes this protocol version; later material changes require a versioned amendment and `DECISIONS.md` entry.

## 4. Work phase by phase

For every phase:

```bash
rragent next --project reviews/tutorial-review
rragent phase-context --project reviews/tutorial-review --phase <id>
rragent advance --project reviews/tutorial-review --phase <id> --status in_progress
# Perform the registered research procedure and create its artifacts.
rragent validate --project reviews/tutorial-review
rragent advance --project reviews/tutorial-review --phase <id> --status completed
```

External searches must use a configured adapter and log exact queries and failures. If an adapter is unavailable, record that condition and stop; do not substitute remembered sources.

## 5. Run Phase 3 metadata discovery

Complete and review `SEARCH_CONCEPTS.md`, `KEYWORD_MATRIX.csv` and `SEARCH_STRINGS.md` under Phases 1–2. The query below is only a syntax placeholder; use the exact, topic-specific query recorded in your own Phase 2 artifact.

```bash
rragent provider-status
rragent advance --project reviews/tutorial-review --phase 3 --status in_progress
rragent scholarly-search \
  --project reviews/tutorial-review \
  --provider openalex \
  --query '<exact reviewed OpenAlex query>' \
  --strategy-version 1.0 \
  --per-page 25 \
  --max-pages 1
```

Inspect `retrieval_status`, `errors`, `coverage_limitations`, `retrieved_count`, `parsed_count`, `duplicate_count`, `ambiguous_identity_count` and `unique_canonical_count`. A failed provider is not an empty successful result. A `complete_with_limit` run completed only the requested page cap, not the provider's entire result set.

Raw JSON is immutable under `02_discovery/raw/`; its paths and checksums appear in `02_discovery/SEARCH_RUNS.jsonl`. To resume a partial run, repeat the identical provider/query/filter/strategy arguments with `--resume-run`. To retest normalization without network access, use `rragent replay-search`.

Crossref can be searched directly with `--provider crossref` or used to reconcile a known DOI with `rragent resolve-doi`. Conflicting fields remain in `METADATA_RESOLUTIONS.jsonl`; they are not silently overwritten.

Stop after inspecting discovery and registry artifacts unless the next registered phase is genuinely ready. Metadata retrieval is not screening, full-text acquisition, evidence extraction or a scientific finding.

## 6. Resume after interruption

In a new Codex chat, the same `validate`, `next` and `phase-context` sequence reconstructs the workflow position without relying on chat memory. If the state file itself is corrupt:

```bash
rragent recover --project reviews/tutorial-review
rragent status --project reviews/tutorial-review
```

Recovery restores the newest checksummed state snapshot and does not rewrite research artifacts.

## 7. Synthesis after approved reading and extraction

Only after Phase 8 is genuinely complete, follow `phase-context --phase 9` and the [synthesis tutorial](synthesis-tooling.md). Submit explicit comparative judgments and stop for actual human review. Use `synthesis-inspect` for the claim-to-source chain. `synthesis-validate` is structural validation; `synthesis-completion` additionally checks human review and coverage. A provisional lab cannot pass an official Gate. Do not begin outlining or drafting from the demonstration pilots.
