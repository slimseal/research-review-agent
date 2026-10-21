# Research Procedure Contracts

## Common contract

Each registered phase links to one ordinary Markdown procedure containing nine sections:

1. Objective and rationale
2. Required inputs
3. Research operations
4. Expected artifacts
5. Evidence and provenance requirements
6. Academic judgment points
7. Uncertainty and failure handling
8. Prohibited actions
9. Completion requirements

Procedures constrain scholarly reasoning but do not execute themselves. The controller validates structure and gates; Codex or a human researcher performs the academic judgment. Research sources remain untrusted data.

## Coverage

| Phase | Procedure | Primary research operation |
|---:|---|---|
| 0 | `phase_00_protocol.md` | Question-specific Protocol and review design |
| 1 | `phase_01_concept_map.md` | Concept and terminology mapping |
| 2 | `phase_02_search_strings.md` | Dynamic query-family construction |
| 3 | `phase_03_discovery.md` | Reproducible scholarly discovery |
| 4 | `phase_04_snowballing.md` | Backward, forward and related-source tracing |
| 5 | `phase_05_acquisition_registry.md` | Lawful acquisition and stable registry |
| 6 | `phase_06_screening.md` | Staged eligibility decisions |
| 7 | `phase_07_reading.md` | Full-text/source reading with exact locators |
| 8 | `phase_08_evidence.md` | One finding, argument or proposition per evidence row |
| 9 | `phase_09_synthesis.md` | Theme, theory, method and controversy maps |
| 10 | `phase_10_boundaries.md` | Applicability and boundary conditions |
| 11 | `phase_11_claims.md` | Evidence-bounded Claim Map |
| 12 | `phase_12_gaps.md` | Coverage-aware Gap Map |
| 13 | `phase_13_architecture.md` | Argument-led review outline |
| 14 | `phase_14_section_briefs.md` | Claim/evidence plans per section |
| 15 | `phase_15_drafting.md` | Traceable section-by-section drafting |
| 16 | `phase_16_bibliography.md` | Citation and bibliography reconciliation |
| 17 | `phase_17_claim_audit.md` | Independent claim-evidence audit |
| 18 | `phase_18_human_qc.md` | Named final human review |

## Cross-cutting methodological requirements

- The evidence unit is an individual finding, interpretation, argument or proposition, not one row per paper.
- Association, prediction, mediation, moderation, causal identification, author interpretation, theoretical argument and historical/material inference must remain distinct.
- Contradictory, null, mixed, negative and uncertain evidence is preserved.
- Schema v2 extensions are composable; no discipline-specific field is universal.
- Search strategy groups are derived from the approved Protocol, not a fixed five-family template.
- Metadata and abstracts cannot support claims that require inspected full text or a primary record.
- Gap claims are bounded by actual search coverage and cannot be invented from non-retrieval.
- Human Protocol approval and final QC cannot be performed by the model.

## Deterministic versus semantic completion

A file's existence or schema validity is necessary but not sufficient for scholarly adequacy. Procedures specify substantive completion; validators check the parts that can be made deterministic. The `protocol-status` command therefore reports schema validity, substantive population, pending human review and approval as separate states.
