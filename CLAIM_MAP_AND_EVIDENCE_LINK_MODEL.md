# Claims and Normalized Evidence Links — Round 2H

## Claim

One stable claim_id represents one bounded proposition. Types include empirical_association, causal, interpretive, theoretical, methodological, historical, archaeological, conditional and coverage_assessment. Other fields include scope, research_question, evidence IDs/decisions, strength, methodological_limits, allowed_wording, prohibited_overclaim, uncertainty, semantic/human review and version/provenance.

Every included corpus item receives a relation or a reasoned not_relevant disposition. This makes omissions inspectable, but a falsely written irrelevance rationale still requires semantic detection. Corrections append revisions. Rejected candidates are explicitly retired, remain visible in history/CSV, and cannot support new claims or gaps. Defer/reopen/request-reading/request-discovery remain blocking, not implicit exclusion.

## ClaimEvidenceLink

One stable link_id binds exactly one claim_id and one evidence_id. Relations: supports, contradicts, qualifies, context, uncertain. Directness: direct_source, indirect, secondary_citation. Each link has strength, rationale, source_basis, verification_status, reviewer/generator, timestamp, version and source anchors. Effective human review remains separate from generated metadata.

Many-to-many relationships are permitted. Duplicate pairs must revise the existing link rather than inflate support counts. Each relationship must match the claim's evidence-disposition ledger. A supports link does not imply sufficient overall support. A source can support a narrow claim and contradict a broader one.

CSV exports preserve legacy claim columns and add structured fields; normalized links have their own file. Canonical records live in journaled history, not hand-edited CSV.

## Trace and semantic controls

Claim → normalized link → EvidenceItem → ReadingNote → SourceAnchor → DocumentVersion/SHA → Paper identity. `synthesis-inspect` returns resolved source metadata and history. Exact location is not semantic support.

Structured checks block declared causal upgrades from non-causal items, generalization beyond sources, one-paper “consensus”, consensus with unresolved disagreement, uncertain items used as verified support, secondary-as-primary claims, unsubstantiated tested mechanisms/boundaries and novelty flags. These are limited guards, not an entailment classifier.

A separate semantic record must address causality, prediction, mechanism, generalization, historical inference, secondary source status, null results, contradictions, uncertainty, independence, consensus and novelty, plus reasoning for every referenced EvidenceItem. Unsupported/uncertain assessments cannot be human-approved as supported. A newly revised assessment revokes effective prior approval until reviewed again. Declared reviewers are not authenticated.

The fictional pilot retains an unsupported all-context benefit candidate alongside defensible bounded claims. Its valid IDs do not make its proposition acceptable. No scientific accuracy percentage is reported.
