# Phase 11 — Claim Map

## Executable contract (Round 2H)

Use `synthesis-submit --kind claim` during active Phase 11. Provide one proposition, claim_type, scope, strength, methodological_limits, allowed_wording, prohibited_overclaim, generalization, uncertainty and earlier synthesis/boundary record_refs. For every included corpus EvidenceItem, evidence_decisions records supports/contradicts/qualifies/context/uncertain/not_relevant plus a rationale; evidence_ids must exactly match relevant decisions.

Create separate `link` records with claim_id, evidence_id, evidence_ids containing that one ID, relation, directness (direct_source/indirect/secondary_citation), strength and rationale. Many claims may use the same evidence; each relation is a separate judgment. A support link need not be sufficient to establish the entire claim. Preserve counterevidence and acknowledge contextual/measurement differences. No field-wide consensus based on counts.

Run `synthesis-inspect --id ...` to inspect Claim→EvidenceItem→ReadingNote→SourceAnchor→DocumentVersion→Paper identity; link IDs bind the normalized intermediate relationship. Run `synthesis-assess` with explicit evidence-by-evidence reasoning and twelve overclaim checks. Structural IDs and deterministic wording flags do not prove entailment.

Only a real human may approve. Rejecting retires a candidate but preserves its content and review history; deferring remains unresolved. Corrections append a new revision and reset effective approval. Record the claim map assessment. `synthesis-completion --phase 11` must pass before `advance`; Gate 3 additionally requires the completed phase and current upstream artifacts. CSV-only claims cannot pass.

## Objective and rationale

Build an auditable set of review claims whose wording, confidence and scope match the available supporting, contradictory, null and uncertain evidence.

## Required inputs

- Evidence matrix, all synthesis maps and boundary-condition analysis.

## Research operations

1. Formulate one bounded proposition per claim ID.
2. Link supporting and contradictory evidence IDs and identify their evidence types.
3. Assess strength with attention to source quality, directness, consistency and independence.
4. State boundary conditions, permitted wording and a specific prohibited overclaim.
5. Record confidence and an audit-ready verdict without turning uncertainty into false precision.

## Expected artifacts

- `08_argument/CLAIM_MAP.csv`

## Evidence and provenance requirements

All evidence references resolve to validated matrix rows. Claim wording distinguishes association, interpretation, historical inference, material inference and causal identification where relevant.

## Academic judgment points

Determine defensible aggregation across research types, assess directness and independence, and choose wording proportionate to the weakest material uncertainty.

## Uncertainty and failure handling

Use insufficient or not-assessed strength when evidence cannot support a proposition. Split claims that combine incompatible scopes.

## Prohibited actions

Do not omit contradictory or null evidence, infer causality from association, present interpretive convergence as measurement certainty, or cite unresolved paper IDs.

## Completion requirements

Every material synthesis proposition has a valid claim row, traceable evidence, explicit boundaries, calibrated wording and recorded counterevidence.

