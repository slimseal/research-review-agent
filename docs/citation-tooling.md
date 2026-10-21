# Citation tooling — Phase 4

Python core only; no Skills, API SDK, graph database or third-party installer. `rragent provider-status` shows configuration, not successful connectivity. Metadata/citations do not establish relevance, inclusion, full-text inspection or evidence quality.

## Official review

### Strict six-request round (opt-in, `bounded_first_page_v1`)

This policy is separate from the legacy behavior documented below. It cannot be
downgraded after registration or replaced after any run starts. It permits at
most three seeds, Crossref backward plus OpenAlex forward, one hop, one request
per seed/direction, six possible sends total and twenty processed observations
per path (120 total). No automatic retries, redirects, identity queries, paging
or source fallback are allowed. OpenAlex uses `per_page=20,cursor=*`; all seed
DOIs and OpenAlex IDs must already be present in the local canonical registry.

Add this exact object to the ordinary seed config, set `max_requests=6`,
`max_candidates=120`, `expansion_depth_limit=1`, and use the provider plan in
Crossref-backward then OpenAlex-forward order:

```json
{"budget_policy": {
  "policy_id": "bounded_first_page_v1", "http_limit": 6,
  "relations_per_seed_direction": 20,
  "selection_method": "provider_order_first_n_v1",
  "identity_resolution": "local_only", "automatic_retries": 0,
  "automatic_pagination": false, "automatic_fallback": false
}}
```

Supply `expected_protocol_sha256` (canonical JSON digest), and for official
projects also `expected_project_id` and `expected_protocol_file_sha256` (exact
file bytes). `citation-budget-preflight --config <json> --project <path>` checks
the proposed config offline, without registration or approval. After actual
registration, omit `--config` to inspect the registered version and plan hash.
Approval additionally requires `--expected-version <seed_set_version>` and
`--expected-plan-sha256 <plan_sha256>`. Only the real researcher executes
`citation-seed-approve`; labels are declarations, not authenticated identity.

The **precommitted** rule is first twenty positions in the provider-returned
array, not model-ranked relevance. Invalid, duplicate and unresolved positions
consume slots; they are not replaced. Entire Crossref response bytes (including
the full deposited reference array) are retained with SHA-256. Each page records
`provider_row_count`, `selected_count`, `processed_count`, `unprocessed_count`,
`selection_method`, and any unused next cursor. Unprocessed count is raw returned
minus selected count after a completed page; during interruption, additionally
report selected count minus processed count as pending. These counts are neither
unique papers nor complete database coverage. Unknown Crossref identities stay
unresolved; OpenAlex response metadata and already saved local identities need
no extra request. No Screening status is approved.

The strict transport writes immutable reservations under
`.review/citation_http_budget/` before its sole HTTP open. Request URL, parameters,
seed/path, versioned plan hash, selection rule, attempt, time and conservative
budget slot are recorded; credentials are never logged. It saves complete raw
success/error bodies and durable checksum-bound response receipts before parsing.
HTTP errors and interrupted attempts consume budget. A timeout, a partial read,
or a crash without a response receipt is `REQUEST_SEND_UNKNOWN`: **all new sends
are blocked**. There is no automatic refund or “retry anyway” switch. A crash
after the durable receipt can resume offline from that response. Use existing
`citations-recover` for journal/projection repair, then inspect receipts and run
`citation-resume`; recovery never supplies permission to resend an uncertain
request. Do not delete receipts to reset budget. Missing/corrupt receipts and
orphaned versions require manual investigation from preserved snapshots/journal.

Repeated starts reuse the same run; locks and sequence/version/hash checks
prevent competing writes. A saved HTTP failure is replayed, never resent;
unattempted later seeds remain visibly incomplete and require follow-up planning,
not automatic replacement requests. Formal completion checks each seed/direction,
not merely one request per provider, and still requires genuine stopping review.
Filesystem hashes detect corruption/consistency failures, not malicious control
of the machine. The CLI does not authenticate humans or provider scientific truth.

### Legacy/general policy

Complete Phases 0–3 legitimately. Read `AGENTS.md` and run `validate`, `next`, `phase-context --phase 4`. Start Phase 4 with `advance --phase 4 --status in_progress`. Use one writer per project.

```bash
rragent citation-seeds --project reviews/my-review
rragent citation-seed-register --project reviews/my-review --config seed-plan.json --by "Selector"
# STOP: explicit human review required; never run the next line automatically.
rragent citation-seed-approve --project reviews/my-review --by "Human reviewer" --note "Selection and limits approved"
rragent citation-expand --project reviews/my-review --provider crossref --direction backward --round 1
rragent citation-expand --project reviews/my-review --provider opencitations --direction forward --round 1
rragent citation-status --project reviews/my-review
rragent citation-unresolved --project reviews/my-review
rragent citations-validate --project reviews/my-review
rragent citation-report --project reviews/my-review
```

Seed configuration (IDs below are **placeholders**, not papers):

```json
{
  "selected_paper_ids": ["REPLACE_WITH_REGISTERED_ID"],
  "selection_reason": {"REPLACE_WITH_REGISTERED_ID": "Explain relevance to the approved Protocol, not just citation count"},
  "provider_plan": [
    {"provider": "crossref", "direction": "backward"},
    {"provider": "opencitations", "direction": "forward"}
  ],
  "expansion_depth_limit": 1,
  "max_requests": 30,
  "max_candidates": 100
}
```

Crossref requires DOI; OpenCitations adapter currently accepts DOI (its service supports additional PIDs); OpenAlex forward accepts registered work IDs or performs a recorded DOI→work-ID lookup. `OPENALEX_API_KEY` is needed for continuation beyond its first cursor page. `OPENCITATIONS_ACCESS_TOKEN` is optional; no account is created. Crossref inherits optional `CROSSREF_MAILTO` / `CROSSREF_PLUS_API_TOKEN`. No secrets are exported. Request limits count failed calls, identity lookups and metadata resolution. One HTTP attempt per reservation; no automatic provider fallback or quota retry.

Limits are shared by all runs with the same round number, including replacement seed versions; changing a seed set does not reset a spent budget. Later rounds are explicit: register/review any new seeds, raise the planned depth if appropriate, and request the next round. There is no recursive expansion or automatic seed promotion. A new seed version makes previous runs historically stale, not deleted. Protocol content changes also stale results even if its version string was not changed.

## Failure, resume and replay

```bash
rragent citation-resume --project reviews/my-review --run-id CE-...
rragent citation-replay --project reviews/my-review --run-id CE-...
rragent citations-recover --project reviews/my-review
```

Resume a recoverable failure only after its cause is addressed. Request/candidate caps are terminal for that round; inspect retained raw rows rather than silently increasing a limit. Replay is **read-only** source/direction verification, not re-registration or a fresh search. Recovery restores the existing checksummed workflow journal and regenerates citation exports; it does not recover deleted raw bytes. Provider failures retain earlier pages, current seed, record offset and cursor. Malformed successful response bodies are preserved too. HTTP failure details retain status/error/allowed headers, not error-page bodies.

`discovered_count` is the number of processed candidate observations, not total provider results. Raw page `provider_row_count` and `next_record` expose unprocessed rows. `resolved_count` counts observations with canonical IDs; `unique_new_count` counts distinct IDs absent at run start; duplicates include earlier observations and existing papers. An unresolved external endpoint is not a registered paper. A graph relation can be provider-reported while its bibliographic endpoint remains unresolved.

## Human stopping review

Inspect unresolved references, raw unprocessed rows, every provider/seed path, preprint/version ambiguities, source limitations, and omitted directions. Document accepted limitations. Do not equate `complete_empty` with absence of references, or a failed provider with saturation.

Only after a real human decision:

```bash
rragent citation-review --project reviews/my-review --by "Human reviewer" \
  --note "Reviewed seed paths and stopping evidence" \
  --limitations "Describe actual accepted failures, unresolved identities, omitted paths and coverage bias" \
  --stop-reason human_stop
rragent citation-report --project reviews/my-review --completion
rragent advance --project reviews/my-review --phase 4 --status completed
```

Other stop reasons: `low_yield_suggested`, `quota_exhausted`, `coverage_missing`, `user_limit`, `planned_paths_executed`. Review binds the current seed/run/graph checksum; later changes invalidate it. The CLI records human assertions; it cannot authenticate a person's identity. An agent must not self-sign official approval. Failed/limited paths can be accepted with explicit named review; missing unattempted plan paths cannot.

## Isolated infrastructure pilots

`citation-lab-init --project <new-directory>` creates a lab outside official reviews. `citation-lab-doi --project <lab> --doi <real-doi>` uses the existing recorded Crossref resolver. Register a plan and use `citation-seed-approve --pilot-selection` only for an explicitly authorized pilot. This status is **not human approval**; labs cannot approve or complete Phase 4. Synthetic data belongs in tests; real pilots remain outside the repository. Do not publish raw provider data without checking applicable terms.

## Boundaries

Related recommendations are not implemented and the original `RELATED_PAPERS.csv` is retained. No related edges are generated. Non-DOI unstructured references are preserved literally, with deposited author/title/year fields where supplied; no model-memory or fuzzy-web matching. Manual resolution tooling for these references is future work. Legacy CSV identities are reserved and flagged for reconciliation, not silently migrated. Graph nodes with unresolved external identities are not automatically collapsed into later resolved nodes; historical uncertainty remains explicit.
