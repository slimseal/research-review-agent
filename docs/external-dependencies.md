# External Dependencies and Honest Failure States

The installed local control-plane runtime works offline after package installation. A normal PEP 517 installation may need to obtain the declared `setuptools` build backend when it is not cached. The following research operations are not guaranteed by installation and were not simulated as successful.

| Operation | Dependency | Required reporting when unavailable |
|---|---|---|
| OpenAlex metadata discovery | Packaged adapter plus network. Anonymous first-page access is supported; cursor paging beyond page one requires `OPENALEX_API_KEY`. | `REQUIRES_API_KEY`, `NETWORK_UNAVAILABLE`, `HTTP_RATE_LIMITED`, `QUOTA_EXHAUSTED`, `TIMEOUT`, or provider error |
| Crossref metadata discovery/DOI resolution | Packaged adapter plus network. Public access needs no signup; `CROSSREF_MAILTO` is recommended and `CROSSREF_PLUS_API_TOKEN` is optional for subscribers. | `NETWORK_UNAVAILABLE`, `HTTP_RATE_LIMITED`, `ACCESS_FORBIDDEN`, `TIMEOUT`, identifier or provider error |
| PubMed | Packaged ESearch + EFetch adapter; anonymous low-rate access, optional `NCBI_API_KEY`; two HTTP sends per nonempty page | `rate_limited`, authentication/entitlement errors or network failure |
| Europe PMC | Packaged public REST core metadata search, no key | Network/rate/provider failure |
| Semantic Scholar | Packaged relevance-search adapter; optional `SEMANTIC_SCHOLAR_API_KEY`; shared anonymous pool may be throttled | `rate_limited`, key/entitlement or network failure |
| ERIC / arXiv / OpenAIRE Graph v3 | Packaged no-key metadata adapters, live-verified in Batch 2; native queries, conservative paging and request pacing | HTTP/network failures; unknown fields/oversize responses rejected; preprints and multi-ID research products need identity/type review |
| CORE | Official access conditions assessed; detailed contract not verified, no adapter | `not_implemented`; documentation 403 is not a tested metadata-search failure |
| Institutional / other scholarly databases | Missing adapter and separately verified API entitlement; manual supplementation remains explicit | `ADAPTER_UNAVAILABLE`, per-source failures, exact unexecuted query plan |
| High-volume or policy-limited API use | Service-specific API key, credit budget, contact identity and provider-compliant request plan | `REQUIRES_API_KEY` or `QUOTA_EXHAUSTED` |
| Forward/backward citation coverage | Packaged Crossref backward, OpenAlex forward, OpenCitations backward/forward; stable seed identity, approved bounded plan and provider coverage. OC token optional. | Coverage/missing-reference limits; external failures; `REQUEST_LIMIT` / `CANDIDATE_LIMIT` are local caps, not saturation |
| Full-text acquisition | Packaged public publisher-page adapter or local import; recorded authorization; optional `[pdf]` integrity parser | `ACCESS_NOT_AUTHORIZED`, `ACCESS_FORBIDDEN`, `PARSER_UNAVAILABLE`, `FULLTEXT_NOT_FOUND`, unsafe URL or download error |
| Page parsing / SourceAnchors | Optional pinned `pypdf`, readable unencrypted PDF, exact checksum | `PDF_CORRUPT`, `PDF_ENCRYPTED`, `ocr_or_manual_required`, `parsing_incomplete`, `stale` |
| Full-text evidence extraction | A compatible reader plus complete, readable, identity-matched source | `ADAPTER_UNAVAILABLE`, `FULL_TEXT_REQUIRED`, or `not_reliably_extractable` |
| Human protocol/QC decisions | Named reviewer | Phase remains incomplete |

Do not convert one source's success into a claim of complete database coverage. Do not convert a landing page, snippet, or abstract into a completed full-text read.

Run `rragent capabilities` for feature boundaries and `rragent provider-status` for credential-presence booleans and `not_verified` status. Explicit `provider-status --probe` consumes a confirmed request budget and checks only its selected endpoint. Secret values are never reported. Global Skills installed on one developer's machine are neither bundled dependencies nor part of the normal execution path and must not be assumed on a fresh clone.

See [V1.1 access tiers and verified endpoints](database-access.md) and [live/offline results](V1_1_VALIDATION.md). A quota-check 401 does not determine anonymous search access. No free-key enrollment or institutional data access has been executed.

The earlier V1 provider contract and policy review is based on current official documentation: OpenAlex authentication, paging, search, filters and error handling; Crossref REST access/authentication, versioned endpoints, pagination and responsible-use guidance. Provider policies can change, so recheck them before a production or high-volume run.

