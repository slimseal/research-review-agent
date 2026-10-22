# V1.1 database access and beginner experience

Policy review: **2026-10-22**. This is development work, not a released V1.1 or a claim of universal availability. See [validation](V1_1_VALIDATION.md) for actual connection results.

## Product contract

The beginner supplies an RQ and necessary scope. Codex recommends complementary databases with reasons, honors explicit inclusions/exclusions, and produces a short **Literature Source Plan**. Do not require database expertise or several keys up front.

The plan has five groups: Recommended and available; Available after free setup; Requires institutional access; Manual supplementary search; Not implemented or not verified. A planned no-key route is not a live-verified route. Initially use `not_verified`, then update with endpoint observations. Probe reports are dated and credential-scoped; planning accepts only search observations from the last 24 hours, never quota observations as search proof. This freshness window is not a guarantee of future availability.

One confirmation covers the exact source/query/filter plan, permitted credential modes, total and per-source HTTP budgets, retries, pages and record limits, including setup verification and metadata subrequests. Do not repeatedly ask about ordinary technical calls within this plan. Do ask before new sources, broader scope, purchases or account enrollment. Protocol approval and subsequent scientific reviews remain separate; no Gate is bypassed.

## Three access tiers and official evidence

| Tier | Endpoint / implemented capability | Setup and limitation |
|---|---|---|
| A | Crossref `/v1/works` metadata search | Public, no signup. Optional contact email/premium credentials are not prerequisites. [Official REST guide](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) |
| A/B | PubMed E-utilities `esearch.fcgi` + `efetch.fcgi` | No key required at the documented low rate; optional NCBI key raises permitted throughput. This adapter conservatively paces requests. Each nonempty page takes **two** requests; no full-text fetch. [NCBI usage rules](https://www.ncbi.nlm.nih.gov/books/NBK25497/), [utilities](https://www.nlm.nih.gov/dataguide/eutilities/utilities.html) |
| A | Europe PMC REST `/search`, `resultType=core` | Public metadata/abstracts and cursor pagination; no signup/key in this route. Life-science scope and substantial PubMed overlap. [Official REST guide](https://europepmc.org/RestfulWebService) |
| A/B | OpenAlex `/works` first cursor page | Anonymous basic search supported; further cursor pages and `/rate-limit` require a key in this implementation. A quota 401 says nothing about anonymous search. [Official authentication guide](https://help.openalex.org/api/authentication/) |
| A/B | Semantic Scholar `/graph/v1/paper/search` | Public relevance search, optional key; shared anonymous access can be throttled. Only the relevance endpoint is implemented, not bulk/dataset/snippet search. It has a 1000-result window; no hidden fallback. [Official API specification](https://api.semanticscholar.org/api-docs/), [access policy](https://webflow.semanticscholar.org/product/api) |
| A | ERIC `https://api.ies.ed.gov/eric/` | Education metadata; native `search`, `start`, `rows`, `format=json`. Ten-record anonymous requests were verified in Batch 2. Keep education reports and provider peer-review assertions distinct from eligibility. [Official API examples](https://eric.ed.gov/pdf/Using_ERIC_API_for_Research_Topics.pdf) |
| A | arXiv `https://export.arxiv.org/api/query` | Atom metadata, native fielded Boolean query, offset paging, at least 3.05-second per-request client delay in recorded transport. Deposit/version IDs retained; publication DOI is a relation, not silently the preprint's identity. [Official manual](https://info.arxiv.org/help/api/user-manual.html) |
| A | OpenAIRE `https://api.openaire.eu/graph/v3/research-products` | Current stable JSON Graph endpoint, not retired XML Search; v4 is beta and not used here. `search`, selected native filters, `page`, `pageSize`, `sortBy`. Preserve heterogeneous output/instance types. [Official v3 overview](https://graph.openaire.eu/docs/apis/graph-api/overview/), [research products](https://graph.openaire.eu/docs/apis/graph-api/research-products/) |

CORE is catalogued but **not implemented**: the official public service page advertises anonymous free API access subject to terms/rate limits, while direct API reference retrieval returned 403 during this batch. Do not infer its current schema, paid/free entitlement, or working search access from third-party wrappers. [Official service/access page](https://core.ac.uk/services/api). See [provider roadmap](provider-roadmap.md).

| Tier | Institutional source | Setup and limitation |
|---|---|---|
| C | Scopus / Web of Science advanced APIs | **No adapter implemented.** API credentials and applicable entitlement must both be verified. Owning a key or a website subscription is insufficient. Web of Science Starter is a distinct product, also not implemented here. [Elsevier access](https://dev.elsevier.com/support.html), [Clarivate access](https://developer.clarivate.com/help/api-access) |
| C | PsycINFO | **No adapter implemented.** Institutional/licensed access and project-specific data permission require separate review. [APA data access requests](https://www.apa.org/pubs/psycinfoservices/request-form) |

Neither a free endpoint nor a returned PDF URL grants redistribution or full-text access. Google Scholar and unavailable subject databases remain manual supplements; do not scrape or treat a manual-export option as an implemented importer.

Use [Standard/Comprehensive planning guidance](search-modes.md), the separate
[Scholar manual tutorial](google-scholar-supplement.md) and [common errors](troubleshooting.md).
The dated observations above were not rechecked against live endpoints during final
integration; saved evidence is not a guarantee of current service availability.

## Status is scoped to an operation

| Status | Meaning |
|---|---|
| `available` | This authorized endpoint request succeeded; not a guarantee for other endpoints or future requests. |
| `key_missing` | A required key is absent for this operation; anonymous alternatives may remain available. |
| `key_invalid` | The request rejected the supplied authentication, or a known key is awaiting activation; retain the reason. |
| `insufficient_entitlement` | Access was forbidden; key presence does not establish the right to use that endpoint. |
| `quota_exhausted` | An explicit budget/credit-exhaustion response, distinct from transient throttling. |
| `rate_limited` | Request rate/shared-service restriction; do not relabel it as missing key or zero results. |
| `temporarily_unavailable` | Endpoint/network/malformed-response failure requiring inspection; not permission to retry blindly. |
| `not_implemented` | No packaged operation; no connection claim or automatic substitute. |
| `not_verified` | No sufficiently recent live check; offline configuration is not a successful connection. |

`requires_institutional_access` is a separate access requirement, not a claim that an institutional adapter exists or that subscription rights have been checked. Unknown access remains unknown. A failed request is `failed`/`partial` in SearchRun; a skipped query is `not_executed`, with no inferred result count.

## Actual commands

Offline inspection and draft planning:

```bash
rragent capabilities
rragent provider-status
rragent source-plan --question "YOUR RESEARCH QUESTION" --domain "YOUR FIELD" \
  --output LITERATURE_SOURCE_PLAN.json
```

The output must be a new private file. `source-plan` is a transparent heuristic, not expert domain coverage analysis; Codex refines recommendations and manual supplements. Optional `--include`/`--exclude` can repeat. `--access-report` accepts a saved endpoint probe result or a `results` array. Source choices remain unapproved; the CLI does not sign a plan.

Only after confirming the probe as part of the budget:

```bash
rragent provider-status --provider pubmed --probe --anonymous \
  --receipt-dir private-probes/pubmed-check-1 --max-requests 2
```

This is a real `biodiversity` one-record connectivity query plus metadata fetch, not the review's scientific search. It consumes budget and is not an approved-protocol result. Without `--anonymous`, only that provider's configured credential is used. Configured keys are read from environment variables, never command arguments. The program does not load `.env` files automatically.

After actual Phase 0–2 approvals/completion and active Phase 3, run each confirmed query through `scholarly-search`, specifying provider, reviewed query, strategy version, `--per-page`, `--max-pages`, `--max-requests` and `--max-attempts`. Default attempts are one, and redirects are disabled. PubMed/Europe PMC filtering belongs in the reviewed native query; unsupported filter/sort arguments are rejected. No implicit translation or hidden DOI lookup occurs.

HTTP receipts are reserved before possible sends and retained under `02_discovery/http/`. Successful response bytes have SHA-256; errors retain safe status/code, not potentially credential-echoing bodies. PubMed's replay envelope contains the original ESearch JSON and EFetch XML. Unknown send state consumes the slot and blocks that ledger, including after restart. Inspect it rather than deleting a lock/receipt or issuing a replacement run. A receipt count is a conservative possible-send count when network completion is unknown.

**Scope of budget enforcement:** the CLI enforces each run/probe ledger. It does not yet execute or enforce a shared all-provider source-plan budget transactionally. Codex must allocate per-run caps whose sum, including probes and DOI lookups, stays within the single confirmed total. Creating a new run is not renewed permission. Optional sources have independent caps so one failed provider does not block the others.

Read-only coverage accounting:

```bash
rragent literature-coverage --project reviews/my-review \
  --plan private-plans/LITERATURE_SOURCE_PLAN.json \
  --output LITERATURE_COVERAGE_REPORT.json
```

The report retains queries, failures, skipped paths, canonical overlaps and provider-only candidate IDs. “Unique” does not mean relevant or eligible. Codex must assess the unique candidates against genuine screening evidence and discuss missed known papers, language/design/time coverage and manual specialist gaps. Total records are never saturation proof.

Batch 2 adds pairwise overlap IDs, raw and canonical counts, provider-only counts, abstract/identifier missingness, HTTP budgets/stops and explicit `relevance=not_evaluated`. Replay runs do not inflate live-search counts. `latest_normalization` and its totals distinguish current parser outcomes from immutable original-run counters. Missingness uses registered source observations and separately identifies unknown legacy abstract availability; unresolved/rejected rows are not silently included in that denominator. PMID/PMCID absence is not a defect in disciplines where those identifiers do not apply.

Exact namespaced PMID/PMCID matching complements DOI and conservative title/first-author/year matching. Conflicting identities stay unresolved. Multiple primary DOI/PMID values in an OpenAIRE aggregate cannot be merged just because one PMCID matches. Complete native identifiers, instance/version information and raw pointers are retained. Shared metadata identity does not prove independent cohorts, peer review or eligibility.

Failed 429 receipts preserve safe rate-limit headers, including valid Retry-After values when actually supplied. If an authorized retry would require waiting longer than 60 seconds, the transport pauses with the failure instead of retrying early. No retries are enabled by default. Semantic Scholar supplied no Retry-After in the Batch 2 response; no retry or inferred reset time was used.

## Free setup only when needed

- `OPENALEX_API_KEY`, `NCBI_API_KEY` and `SEMANTIC_SCHOLAR_API_KEY` are provider-specific and optional until the selected operation requires them. Keep credentials local; use a private environment/secret manager. Never paste them into public issues, reports or shell command arguments.
- After the user configures a key, the Agent runs the already-authorized bounded `provider-status --probe` check. There is no background credential watcher; without the planned verification permission it asks before a network call. No paid credit purchase occurs.
- OpenAlex officially supports `POST /api-keys` with a user-provided email, then activation by the mailbox owner. **This kit has assessed but not implemented or executed enrollment.** Separate express consent is required before sending an address. An existing account uses its settings; pending activation is not a valid working key. Do not infer an address, use placeholders, read email, click activation, or resend automatically. This task did not register an account.
- Institutional integrations remain deferred, not falsely labeled “implemented but untested.” Their implementation needs endpoint/response contracts and offline tests, and their live validation needs genuinely authorized service access. Other public searches can proceed meanwhile.

## Deliberate boundaries

All 19 phases, No-Skills architecture, approved Protocol protection and scientific Gates remain unchanged. No personal-library integration, Zotero or bulk RIS/BibTeX ingestion was added. Single-PDF acquisition/import remains governed by Phase 5. No old review project is used for these engineering tests.
