# V1.1 Experimental — draft release notes

**Prepared, not published.** No commit, merge, tag, GitHub Release or visibility change
was made during integration. The remote main revision remains the original V1 snapshot.
Package metadata remains `0.1.0.dev0`; “V1.1” is a product milestone label, not a PyPI version.

## Scope

- Eight implemented metadata adapters: Crossref, OpenAlex, PubMed, Europe PMC,
  Semantic Scholar, ERIC, arXiv and OpenAIRE JSON Graph v3. Implementation does not mean live availability.
- Endpoint-specific configuration/status, bounded possible-send receipts, provider-native
  queries, raw-response provenance, identity reconciliation and multi-source coverage.
- Beginner RQ-first source recommendations and Standard/Comprehensive planning guidance.
- Offline Google Scholar manual plans, Chinese checklist, separate session/candidate
  records and coverage accounting. Scholar Button is not an Agent connector.
- Existing No-Skills architecture, 19-phase workflow and scientific Gates retained.

## Evidence of operation

Saved 2026-10-22 anonymous retrieval succeeded for Crossref, PubMed, Europe PMC,
ERIC, arXiv and OpenAIRE. Latest OpenAlex request exhausted quota; Semantic Scholar
returned 429. Institutional adapters remain unimplemented.

Saved main integration: 51 observations, 47 canonical candidates, one duplicate
observation, three unresolved identities. Separate arXiv sample: ten preprints.
Provider overlap does not establish relevance, peer review or independent cohorts.
No new scholarly request was made for final integration.

Final existing regression suite: **436 passed in 348.123 seconds**; 19-phase validation passed.
Saved raw-response SHA/provenance and coverage checks passed. A clean source-only copy
ran initialization, phase context, status/planning and Scholar preparation without network.
An earlier offline/no-build-isolation attempt failed for a missing local backend.
The subsequent **final installation gate passed**: two new isolated virtual
environments installed the full candidate source with normal online build isolation,
one editable core installation and one regular wheel-backed installation with
`pypdf==6.20.1`. Nine CLI checks passed in each, outside the source directory, and
dependency consistency passed. No original development packages were inherited.
This is macOS / Python 3.13.2 evidence, not a cross-platform or offline-install guarantee.
See [final gate](V1_1_FINAL_RELEASE_GATE.md) and [integration acceptance](V1_1_ACCEPTANCE_ZH.md).

## Important limitations

- Comprehensive is not guaranteed comprehensive retrieval or systematic-review sufficiency.
- Per-run caps exist; a shared transactional all-provider budget executor does not.
- Keyed access, institutional access and live multipage behavior are not validated here.
- Scholar `performed_as_reported` is not `completed`; automatic completed/incomplete
  scope closure is not implemented. Manual candidates remain not_imported, separate
  from Registry. Crossref DOI reconciliation is a separately authorized operation.
- Scientific relevance, inclusion, full-text interpretation, evidence and final conclusions
  require real review. This is not an academically validated end-to-end systematic-review tool.
- Historical bibliography, PDF glyph/table and review limitations remain; see [Known Issues](KNOWN_ISSUES.md).
- No open-source license has been selected. Public visibility is not a license grant.

## Distribution boundary

Candidate source/docs/tests and curated V1 examples only. Do not attach private
research directories, raw API archives, PDFs, approval identities, credentials,
virtual environments, caches, snapshots or test logs. This is a source snapshot
candidate; locally built wheels were used for installation checks, not offered as
published binary assets. Owner confirmation is required
before any commit, merge, tag, Release or visibility decision.
