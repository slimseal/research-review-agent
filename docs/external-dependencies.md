# External Dependencies and Honest Failure States

The installed local control-plane runtime works offline after package installation. A normal PEP 517 installation may need to obtain the declared `setuptools` build backend when it is not cached. The following research operations are not guaranteed by installation and were not simulated as successful.

| Operation | Dependency | Required reporting when unavailable |
|---|---|---|
| OpenAlex metadata discovery | Packaged adapter plus network. Anonymous first-page access is supported; cursor paging beyond page one requires `OPENALEX_API_KEY`. | `REQUIRES_API_KEY`, `NETWORK_UNAVAILABLE`, `HTTP_RATE_LIMITED`, `QUOTA_EXHAUSTED`, `TIMEOUT`, or provider error |
| Crossref metadata discovery/DOI resolution | Packaged adapter plus network. Public access needs no signup; `CROSSREF_MAILTO` is recommended and `CROSSREF_PLUS_API_TOKEN` is optional for subscribers. | `NETWORK_UNAVAILABLE`, `HTTP_RATE_LIMITED`, `ACCESS_FORBIDDEN`, `TIMEOUT`, identifier or provider error |
| Other scholarly databases | A future reviewed adapter or explicit manual export | `ADAPTER_UNAVAILABLE`, per-source failures, exact unexecuted query plan |
| High-volume or policy-limited API use | Service-specific API key, credit budget, contact identity and provider-compliant request plan | `REQUIRES_API_KEY` or `QUOTA_EXHAUSTED` |
| Forward/backward citation coverage | Packaged Crossref backward, OpenAlex forward, OpenCitations backward/forward; stable seed identity, approved bounded plan and provider coverage. OC token optional. | Coverage/missing-reference limits; external failures; `REQUEST_LIMIT` / `CANDIDATE_LIMIT` are local caps, not saturation |
| Full-text acquisition | Packaged public publisher-page adapter or local import; recorded authorization; optional `[pdf]` integrity parser | `ACCESS_NOT_AUTHORIZED`, `ACCESS_FORBIDDEN`, `PARSER_UNAVAILABLE`, `FULLTEXT_NOT_FOUND`, unsafe URL or download error |
| Page parsing / SourceAnchors | Optional pinned `pypdf`, readable unencrypted PDF, exact checksum | `PDF_CORRUPT`, `PDF_ENCRYPTED`, `ocr_or_manual_required`, `parsing_incomplete`, `stale` |
| Full-text evidence extraction | A compatible reader plus complete, readable, identity-matched source | `ADAPTER_UNAVAILABLE`, `FULL_TEXT_REQUIRED`, or `not_reliably_extractable` |
| Human protocol/QC decisions | Named reviewer | Phase remains incomplete |

Do not convert one source's success into a claim of complete database coverage. Do not convert a landing page, snippet, or abstract into a completed full-text read.

Run `rragent capabilities` for feature boundaries and `rragent provider-status` for credential-presence booleans. Secret values are never reported. Global Skills installed on one developer's machine are neither bundled dependencies nor part of the normal execution path and must not be assumed on a fresh clone.

The provider contract and policy review for this release is based on current official documentation: OpenAlex authentication, paging, search, filters and error handling; Crossref REST access/authentication, versioned endpoints, pagination and responsible-use guidance. Provider policies can change, so recheck them before a production or high-volume run.

