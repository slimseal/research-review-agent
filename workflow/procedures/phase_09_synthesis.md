# Phase 9 — Initial Synthesis

## Executable contract (Round 2H)

Run `synthesis-context` and `synthesis-schema`. Official operation requires completed current Phase 8; do not treat provisional AI extractions as approved. During active Phase 9, submit `synthesis-corpus --config selection.json` with an include/exclude/defer reason for every EvidenceItem, coverage limitations, search coverage and selection rationale. Obtain actual human corpus review before completion.

Use `synthesis-submit --kind theme|theory|method|controversy --config record.json`. Common fields: research_question, evidence_ids, record_refs, uncertainty, generator, example_data. The schema command lists kind-specific fields. Theme comparisons explicitly bind dimensions, evidence IDs, comparability and interpretation. Paper counts are derived from unique source identities, not evidence-row counts. Do not assert independent studies solely because paper IDs differ: cohorts or source bases may overlap.

Submit one `assessment` per map: map_kind, all current record_refs, all included evidence_ids, disposition (populated/none_warranted/deferred) and rationale. Empty theory/controversy maps are legitimate when justified; deferred maps cannot complete. Theme and method maps must contain retained propositions.

Use `synthesis-assess` only after actually checking each referenced item and all twelve semantic concerns. Only a real human may run `synthesis-review`. Complete with `synthesis-completion --phase 9`, then the normal `advance` command. State and history live in the existing journal; Markdown is a projection, not an approval token.

## Objective and rationale

Organize extracted evidence into multiple defensible views before constructing claims, so convergence, divergence and methodological structure remain visible.

## Required inputs

- Validated evidence matrix.
- Approved review questions and research-type design.

## Research operations

1. Build thematic groupings from evidence content rather than preselected example categories.
2. Map theories or conceptual lenses only when sources or the protocol warrant them.
3. Compare methods, source bases and research types to reveal comparability limits.
4. Map controversies, contradictory findings, null results and interpretive disagreements.
5. Link each synthesis element back to evidence IDs and record sparse or unstable groupings.

## Expected artifacts

- `07_synthesis/THEME_MAP.md`
- `07_synthesis/THEORY_MAP.md`
- `07_synthesis/METHOD_MAP.md`
- `07_synthesis/CONTROVERSY_MAP.md`

## Evidence and provenance requirements

Every grouping cites its constituent evidence IDs. Reviewer-created labels are identified as analytic constructs rather than source terminology.

## Academic judgment points

Assess meaningful similarity across heterogeneous evidence, select alternative synthesis frames and avoid majority-counting where evidence quality or commensurability differs.

## Uncertainty and failure handling

Mark provisional clusters and sources that resist categorization. Preserve multiple plausible interpretations for human review.

## Prohibited actions

Do not suppress contradictions, count multiple records from one study as independent corroboration, or infer consensus from citation volume.

## Completion requirements

All review questions and material evidence are represented across the maps, contradictions remain visible, and analytic choices are auditable.

