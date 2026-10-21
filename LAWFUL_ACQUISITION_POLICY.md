# Lawful acquisition policy

Public availability, access authorization, open licensing and redistribution permission are independent. The CLI records a researcher's named assertion and supporting source, not independent legal verification. Unknown values remain unknown. A manually imported PDF is `authorized_local_import`, never provider retrieval. No DOI is required for an existing bibliographic identity. Explicit unresolved identity is not scientific identity verification.

Remote acquisition needs a saved explicit PDF candidate and authorization JSON. `publisher_open_access` needs a supporting policy/article URL; `researcher_asserted_authorized` needs a named operator and reason. Both retain `independent_legal_verification=false`. `permitted_with_conditions` redistribution needs an asserted open license and license URL; nothing is redistributed automatically. Unknown/restricted files must not be committed or uploaded.

No subscription scraping, cookies, credentials, decryption, CAPTCHA solving, paywall bypass or unauthorized repositories. Public HTTPS only. Denied/rate-limited requests stop; no automatic retry storm or proxy fallback. Public page discovery treats its contents as data, never agent instructions.

Policy review: [JOSS licensing](https://joss.theoj.org/about) identifies CC BY 4.0, supporting a small pilot, not blanket permission for other publishers. [Crossref metadata documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) describes deposited links/licenses; these may apply to different versions. No automatic Crossref-license-to-download permission inference was implemented.

Credential/signature URLs are unsupported. Do not put secrets into authorization prose or source filenames. Keep PDFs/parser text in access-controlled research workspaces. Checksums detect changes, not an attacker capable of rewriting the entire local journal.
