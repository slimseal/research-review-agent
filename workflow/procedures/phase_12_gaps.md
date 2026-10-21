# Phase 12 — Gap Analysis

## Executable contract (Round 2H)

Formal Phase 12 requires Gate 3. Use `synthesis-submit --kind gap` with earlier claim record_refs, evidence_ids, gap_type, established, unresolved, methodological_justification, proposed_research_question, confidence, search_limitations, coverage_basis, derivation and unresolved_contradictions. Gaps pin claim revisions, normalized link judgments and recorded search provenance.

This implementation permits only scope=reviewed_corpus and basis_kind=evidence_disagreement/documented_design_limit/conceptual_analysis. Begin derivation with “Within the reviewed and retrieved corpus”. Quotas, a small corpus or missing downloads alone are not substantive gaps. Field-wide novelty claims are unsupported by this implementation; revisit discovery and coverage before any stronger conclusion.

Separate a candidate research question from a validated field gap. If no gap is defensible, submit a justified none_warranted assessment; if information is insufficient, use deferred and stop. Do not invent a gap merely to fill the artifact.

Semantic assessment and actual human review are separate. Run `synthesis-completion --phase 12` and normal `advance` only when ready. Claim/link/evidence revisions stale dependent gaps and invalidate downstream readiness. Do not start Phase 13–17 work in Round 2H.

## Objective and rationale

Identify defensible research gaps only after the claim map exists, distinguishing absence of evidence from disagreement, methodological weakness, inaccessible material and review-search limits.

## Required inputs

- Completed claim map and Gate 3 pass.
- Synthesis maps, boundary conditions, search log and screening trail.

## Research operations

1. Identify unresolved claims, contradictions, unrepresented contexts, weak methods or source-base limitations.
2. Classify each proposed gap: empirical, interpretive, theoretical, methodological, temporal, geographic, material, documentary or review-coverage.
3. Test whether the apparent gap could be caused by search design, access, language, preservation or eligibility choices.
4. Link the gap to claims, evidence, search coverage and boundaries.
5. State what future evidence would reduce the uncertainty without prescribing a favored conclusion.

## Expected artifacts

- `07_synthesis/GAP_MAP.md`

## Evidence and provenance requirements

Every gap has an auditable basis. Field-wide absence claims require search coverage adequate to that scope and must remain cautiously worded.

## Academic judgment points

Judge significance separately from novelty, distinguish productive disagreement from missing work, and recognize domain-specific preservation or publication bias.

## Uncertainty and failure handling

Downgrade unsupported absence claims to review-limited observations. Reopen search planning through a recorded decision if a material coverage flaw is discovered.

## Prohibited actions

Do not fabricate novelty, label every inconsistency a gap, or present the review's access limitations as a property of the research field.

## Completion requirements

Each retained gap is typed, scoped, evidence-linked, coverage-aware and reviewed for overclaiming.

