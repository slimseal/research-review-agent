# Provider roles and remaining access conditions

Updated 2026-10-22. This is a capability roadmap, not a connection claim or authorization.

| Provider | Intended role | Current implementation / next condition |
|---|---|---|
| Crossref | Discovery and DOI metadata reconciliation | Implemented, live anonymous metadata retrieval verified; no subscription/full-text entitlement implied. |
| PubMed / Europe PMC | Biomedical discovery and identifier/abstract metadata | Implemented and live verified; PubMed primary IDs must come only from the paper's own ArticleIdList, not cited references. |
| ERIC | Education discovery | Implemented and live verified; reports and education levels require screening. |
| arXiv | Preprint discovery | Implemented and live verified; preserve exact deposit versions and publication relations. No automatic peer-review assertion. |
| OpenAIRE Graph | Multidisciplinary repository/research-output discovery | Implemented stable v3 JSON API and live verified. Multi-ID aggregates remain unresolved for human identity review. |
| OpenAlex | Discovery / existing citation tracing | Implemented. Last live search observation was quota exhaustion; not re-requested in Batch 2. Anonymous search and keyed quota endpoint remain separate. |
| Semantic Scholar | Discovery | Relevance adapter implemented and offline tested. Live Batch 2 request returned 429; no successful metadata retrieval claim. Optional free key is not a guarantee of quota. |
| DataCite | DOI metadata verification; discovery of datasets, software and other outputs | Not implemented. Public metadata reads do not require member authentication; DOI registration/write operations are outside scope. [Official API](https://support.datacite.org/docs/api). |
| OpenCitations | Citation tracing, not keyword discovery | Existing bounded citation adapter retained; no new live citation request this batch. Official Index v2 provides forward/backward relations; optional access token encouraged. [Official API](https://api.opencitations.net/index/v2). |
| Unpaywall | Lawful open-access location discovery from DOI, not broad topic search | No new adapter implemented or live-tested this batch. Verify current API terms/contact requirement and license/version fields before integration. [Official API product](https://unpaywall.org/products/api). |
| CORE | Repository discovery / metadata; potentially OA location information | Catalogued, adapter not implemented. Official service/FAQ advertises anonymous free access with limits; direct specification access returned 403, so no guessed endpoint contract or offline fixture passed off as verified. Recheck official schema and applicable service terms before implementation. [Service](https://core.ac.uk/services/api), [FAQ](https://core.ac.uk/faq). |
| Web of Science | Licensed scholarly discovery / citation metadata | No adapter yet. Need exact product (Starter vs advanced), authorized API key, institution/plan entitlement, permitted fields and redistribution terms, then offline contracts and entitled live checks. [Access documentation](https://developer.clarivate.com/help/api-access). |
| Scopus | Licensed scholarly discovery / citation metadata | No adapter yet. Need API key plus endpoint/view entitlement and applicable institution/IP/token permissions. A website subscription alone is insufficient. [Official support](https://dev.elsevier.com/support.html). |
| PsycINFO | Licensed psychology discovery | No adapter yet. First identify the institution's actual platform (e.g. EBSCOhost or Ovid), API/export permissions and APA conditions; do not advertise a generic universal PsycINFO API. [APA permission inquiry](https://www.apa.org/pubs/psycinfoservices/request-form). |

No account creation, email use, institutional credential borrowing, purchases or credential sharing is automated. Missing optional access does not block separately authorized sources. Private keys, full texts and local research data do not belong in Git. Google Scholar now has [offline manual planning/recording support](google-scholar-supplement.md), not an automated provider. Personal-library integration remains deferred.
