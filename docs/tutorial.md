# Technical tutorial: question to reproducible metadata discovery

**New users:** follow [Beginner Quick Start](beginner-quick-start.md) and let Codex
operate the commands below. You need not learn the phase numbers or APIs first.
Choose [Standard or Comprehensive](search-modes.md) as a planning preference, not
a CLI flag. Database configuration is in [its separate guide](database-access.md);
Scholar instructions are [here](google-scholar-supplement.md), and common errors
are [here](troubleshooting.md). For a fixed V1.1 source snapshot, use the
[Experimental pre-release](https://github.com/slimseal/research-review-agent/releases/tag/v1.1-experimental).

After genuinely reviewed evidence and synthesis, continue with [Writing, tracing, bibliography and independent audit](writing-tooling.md) for Phase 13–18. This extends the same controller; it never supplies missing upstream approvals.

For Gate-1-eligible full text, continue with [Scientific reading and evidence extraction](reading-tooling.md). This extends the same workflow, not a separate runtime. Model interpretation and human scientific approval remain separate.

For Phase 6, continue with [the three-level screening tutorial](screening-tooling.md), after genuine Phase 4 stopping approval and Phase 5 disposition review. Do not use a development pilot as proof of completed upstream research.

Round 2E adds a [citation tooling tutorial](citation-tooling.md): approved seed plans, bounded backward/forward expansion, immutable provenance, recovery, coverage reports and mandatory human stopping review. It does not perform screening or scientific interpretation.

Round 2D document acquisition, local import, parsing and anchors have a separate [document-tooling tutorial](document-tooling.md). They do not bypass Phase 4, Protocol approval or Gate 1.

Steps 1–4 can work offline. Step 5 performs a real provider request and must be run only after human Protocol approval, reviewed search planning and explicit confirmation of the selected databases, budget and access scope. Sources are recommended from the question and then confirmed, not silently executed. Copy the [start-review prompt](../prompts/start-review.md) or use [connect-database](../prompts/connect-database.md) to assess another database without assuming an adapter exists.

## 1. Create an isolated project

Open the repository in Codex and supply your Research Question and necessary scope. You do not need to know database names or configure keys. The Agent recommends complementary sources and produces a short Literature Source Plan. Explicit source choices/exclusions override the recommendation.

For example: “My question is how novice teachers develop classroom authority. Recommend complementary low-configuration sources and education-specific manual supplements. Draft the Protocol and ask once for source/query/budget confirmation before searching.” Use the [start-review prompt](../prompts/start-review.md). See [database access](database-access.md) for the three access tiers, setup and actual endpoint checks.

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

> Follow AGENTS.md and the workflow registry for `reviews/tutorial-review`. Complete only the Phase 0 research operations. Recommend appropriate complementary sources if I have not named them; respect any explicit choices/exclusions. Prepare a short Literature Source Plan and keep source/query/budget confirmation in human_decisions.pending. Derive a method-appropriate scope, subquestions, concept definitions, proposed search strategies, eligibility criteria and research-type evidence fields from my question. Save a substantive draft, leave human decisions explicit, do not approve it and do not search.

Record the selected database(s), rationale and coverage limitations in the draft Protocol and `DECISIONS.md`; use the project's versioned Search Strategy for concrete queries and execution limits. Unconfirmed choices remain proposals. Adapter availability does not establish suitability, successful access or permission to search.

Use the existing `search` fields, `search.coverage_plan` text and strategy descriptions, not invented schema fields. Confirm exact queries, request/retry and page/record limits, credentials/access scope and any costs before live work. Preserve approved Protocol bytes and use only supported controlled revisions. Crossref, OpenAlex, PubMed, Europe PMC, Semantic Scholar, ERIC, arXiv and OpenAIRE Graph v3 metadata adapters are implemented. CORE, Scopus, Web of Science, PsycINFO and CNKI are not implemented; entitlement requirements and missing code are separate gaps. Do not silently replace them.

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

The next action should be Phase 1. Approval freezes this protocol version. For later source changes, preserve the approved file and old plans, record the decision in `DECISIONS.md`, and use only supported controller transitions for a versioned strategy revision consistent with that Protocol. If the change requires an approved-Protocol amendment, stop and explain that the current amendment command supports only unapproved Phase 0 questions; do not overwrite or re-sign the approved Protocol to proceed.

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

External searches must use a researcher-selected, configured adapter and log exact queries and failures. If an adapter is unavailable, record that condition and stop the affected path; do not substitute remembered papers or automatically switch databases. Other separately authorized paths may continue. A proposed replacement requires the researcher's decision and an updated plan before execution.

## 5. Run Phase 3 metadata discovery

Execute only the selected, authorized supported operation after its actual prerequisites pass. If selection or authorization is missing, ask; if the requested database is unsupported or inaccessible, report it without switching providers.

Complete and review `SEARCH_CONCEPTS.md`, `KEYWORD_MATRIX.csv` and `SEARCH_STRINGS.md` under Phases 1–2. Obtain explicit confirmation of the selected databases, exact queries, request attempts including retries, page/record limits and free/paid/credential access scope. Record the confirmation in the strategy and decision log; do not treat it as a substitute for any formal human approval. Check current requirements and quotas for the selected service before sending a search.

The command below is a syntax placeholder, not a default provider or budget. Replace `<confirmed-provider>` with `crossref`, `openalex`, `pubmed`, `europepmc`, `semantic_scholar`, `eric`, `arxiv` or `openaire` **only as confirmed in the source plan**. Use the exact provider-specific query and the approved numerical limits from your Phase 2 artifact; providers do not have interchangeable search syntax. Do not execute the placeholders literally or automatically add providers.

```bash
rragent capabilities
rragent provider-status
rragent advance --project reviews/tutorial-review --phase 3 --status in_progress
rragent scholarly-search \
  --project reviews/tutorial-review \
  --provider '<confirmed-provider>' \
  --query '<exact reviewed provider-specific query>' \
  --strategy-version 1.0 \
  --per-page <approved-records-per-page> \
  --max-pages <approved-page-limit> \
  --max-requests <approved-total-http-for-this-run> \
  --max-attempts 1
```

Each nonempty PubMed page uses ESearch plus EFetch: budget two HTTP sends. Other packaged searches use one per page, before explicitly allowed retries. Default retries are disabled and redirects are not followed. Every possible send has a durable receipt under `02_discovery/http/`. An uncertain send stops that ledger. Per-run caps do not automatically enforce the sum across separate probes/runs: the Agent must allocate the confirmed total plan budget. Failed optional providers do not stop other separately budgeted sources.

Inspect `retrieval_status`, `errors`, `coverage_limitations`, `retrieved_count`, `parsed_count`, `duplicate_count`, `ambiguous_identity_count` and `unique_canonical_count`. A failed provider is not an empty successful result. A `complete_with_limit` run completed only the requested page cap, not the provider's entire result set.

Raw JSON is immutable under `02_discovery/raw/`; its paths and checksums appear in `02_discovery/SEARCH_RUNS.jsonl`. Resume a partial run only within the confirmed request budget and authorization, repeating the identical provider/query/filter/strategy arguments with `--resume-run`; obtain confirmation before exceeding the budget. To retest normalization without network access, use `rragent replay-search`.

When Crossref is selected, it can be searched directly with `--provider crossref`. Separately authorized Crossref reconciliation of one known DOI uses `rragent resolve-doi` during Phase 3 or 5; it is not a general bibliography importer or an automatic fallback from OpenAlex. Conflicting fields remain in `METADATA_RESOLUTIONS.jsonl`; they are not silently overwritten.

Stop after inspecting discovery and registry artifacts unless the next registered phase is genuinely ready. Metadata retrieval is not screening, full-text acquisition, evidence extraction or a scientific finding.

## 6. Inspect coverage and the optional manual supplement

After authorized searches, ask Codex to run `literature-coverage` with the saved
Literature Source Plan and a new output filename. Inspect per-provider successful,
failed and unexecuted runs, canonical overlaps, unresolved identities and metadata
gaps. Provider-only candidates have not had scientific relevance evaluated.

Use the [Scholar prompt](../prompts/google-scholar-supplement.md) if useful to the RQ.
Codex drafts 3–5 native queries and calls `scholar-prepare` offline. You search in your
browser and provide actual session/candidate records. Empty records remain
not_performed; performed_as_reported is not a completed search or human approval.
The report leaves completed_scope=not_assessed; completed/incomplete requires an
explicit human scope assessment outside the machine status. Manual candidates remain
not_imported and never become API SearchRuns or Registry counts automatically.

Then follow the unchanged procedures: reviewed Phase 4 stopping/coverage and Phase 5
acquisition dispositions precede Phase 6 Screening. Gate 1 precedes Phase 7 Reading;
reviewed source-grounded extraction precedes later evidence use. Additional lawful
PDF acquisition uses supported Phase 5 reopening and updated review, not direct file edits.

## 7. Resume after interruption

In a new Codex chat, the same `validate`, `next` and `phase-context` sequence reconstructs the workflow position without relying on chat memory. If the state file itself is corrupt:

```bash
rragent recover --project reviews/tutorial-review
rragent status --project reviews/tutorial-review
```

Recovery restores the newest checksummed state snapshot and does not rewrite research artifacts.

## 8. Synthesis after approved reading and extraction

Only after Phase 8 is genuinely complete, follow `phase-context --phase 9` and the [synthesis tutorial](synthesis-tooling.md). Submit explicit comparative judgments and stop for actual human review. Use `synthesis-inspect` for the claim-to-source chain. `synthesis-validate` is structural validation; `synthesis-completion` additionally checks human review and coverage. A provisional lab cannot pass an official Gate. Do not begin outlining or drafting from the demonstration pilots.
