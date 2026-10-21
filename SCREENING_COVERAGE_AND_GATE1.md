# Coverage and Gate 1

The old implementation accepted a completed phase flag plus one full-text include/exclude row. Round 2F intentionally removes that insufficient condition, including in example mode. Legacy CSVs do not acquire implied human approval.

Coverage separates all canonical registrations, related versions, the approved candidate scope, explicit scope omissions, upstream unresolved external citations, each cumulative screening stage, provisional included roles/exclusions, final approved roles/exclusions, uncertainty/defer, missing abstracts, missing local full text, human-reviewed records and pending final review. `fulltext_eligibility_screened` includes explicit missing-text assessments; `fulltext_inspected_records` reports records for which actual text was exposed. Stages overlap and are not additive.

Reconciliation identities: candidate count = final records + pending records; all registered = candidates + explicit scope exceptions. A non-excluded intermediate include is not final. Early human-approved exclusions can be final; full-text include needs current valid source evidence and human-declared approval. Reopening an earlier stage makes dependent later-stage records stale. Historical exclusions are not the final exclusion count.

Gate evaluation recomputes approved substantive Protocol, current Protocol hash, real Phase 3/4/5 validity and completion, criteria/scope approval, Registry/candidate snapshot, entire in-scope decision coverage, current source/document/packet hashes, projection checksums and decision-history consistency. Phase 4 is validated even if a manually marked completed state has no citation data. A declared human approval is still not independent authentication.

| Result | Meaning | Reading authorization |
|---|---|---|
| fail | Invalid/stale records, altered source, state/journal or artifact inconsistency | No |
| blocked | Valid incomplete work, missing review, unfinished upstream, unresolved in-scope candidate or isolated lab | No |
| warn | Otherwise complete, approved bounded scope and/or retained unresolved upstream references | Only explicit eligible IDs and versions |
| pass | All required checks satisfied | Only explicit eligible IDs and versions |

The existing workflow controller's boolean gate maps an allowed warn to pass while retaining the detailed assessment and warnings. This is not a bypass: unresolved candidates WITHIN scope still block, and omissions require current human scope approval. No implicit exception for unavailable text, header-only files or “some papers screened” exists. The Gate 1 JSON is an informational snapshot, not a reusable authorization token.

Phase 6 completion uses the same assessment without requiring Phase 6 already be completed. `advance` still performs the transition explicitly. Phase 7 checks the completed state plus the current assessment. Gates 2/3 and all Phase 0–18 sequencing/dependencies are unchanged.

Criteria changes retain old versions and reasons. A changed/added/removed applicable rule or role/version policy stales affected decisions. Scope changes require fresh scope approval; unchanged records can remain current when all their applicability and identity bindings are unchanged. New registry entries or identity changes require renewed candidate scope review. A changed Protocol hash blocks screening; complete Protocol amendment/reapproval orchestration is intentionally not implemented in this round.

Recovery restores the existing event journal and reconstructs projections. It does not invent missing raw sources, PDFs or packets. One writer per research project remains an explicit operational constraint.
