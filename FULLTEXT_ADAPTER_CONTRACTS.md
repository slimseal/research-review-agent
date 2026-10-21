# Full-text adapter contracts v1

Design before implementation: a `FullTextProvider` returns candidates, not acquired papers or evidence. The MVP `PublisherPageProvider` reads a researcher-supplied public publisher page and extracts explicit `citation_pdf_url` metadata or PDF links. It never constructs guessed PDF URLs. Candidate classification distinguishes `pdf_link`, `landing_page`, and `metadata_only`. Link presence never establishes authorization.

Candidates retain provider, landing page, candidate URL, source response checksum, retrieval timestamp, content-type hint, and unassessed rights. Acquisition requires a separate recorded researcher assertion (`publisher_open_access` with supporting policy URL, or `researcher_asserted_authorized`). The assertion is not independent legal verification. Unknown license and redistribution stay unknown. No keys, cookies, logins or subscription fetching are supported.

Transport contract: HTTPS only, port 443, public DNS addresses only, TLS hostname verification with a pinned validated destination address, bounded response/redirect count/time/bytes, no environment proxy or credentials. Redirects receive the same validation. Errors carry stable codes and actionable non-secret messages. Signed/token URLs are deliberately unsupported. No bypass of access denial or rate limits.

MVP excludes Unpaywall, PMC, arXiv APIs and automatic rights interpretation of Crossref/OpenAlex links. Existing scholarly adapters remain unchanged. Official publisher reference checked 2026-10-15: [JOSS licensing](https://joss.theoj.org/about). Publisher HTML links are a best-effort document-discovery interface, not a guaranteed API. Sites without explicit links report landing-page-only.
