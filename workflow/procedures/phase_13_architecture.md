# Phase 13 — Review Architecture

## Operational interface (Round 2I)

Run `writing-context` and `writing-schema` after normal Phase 13 entry. Codex explicitly authors an argument-led outline JSON from current reviewed Claims/Gap records, then runs `writing-submit --kind outline --config outline.json`. Each section needs section_id/title/purpose/argument_progression/planned_counterarguments/claim_ids/gap_ids. Record coverage limitations, duplication policy, justified gap connection, review type and target length. No fixed chapters are imposed.

Stop for actual human `writing-review` of the returned ID before completion. `writing-completion --phase 13` distinguishes a stored draft from an approved architecture. A lab remains provisional.

## Objective and rationale

Design an argument-led structure that answers the approved review questions through the validated claim and gap maps rather than summarizing sources one by one.

## Required inputs

- Claim map, gap map, synthesis maps and target-format constraints.

## Research operations

1. Define the review's central answer and logical progression without exceeding allowed claim wording.
2. Assign each planned section a purpose, subquestion, claim IDs and boundary responsibilities.
3. Place controversies and counterevidence where they alter the argument.
4. Plan introduction, methods, synthesis, limitations and conclusion functions appropriate to the product.
5. Check coverage, duplication and dependency among sections.

## Expected artifacts

- `09_writing/LITERATURE_REVIEW_OUTLINE.md`

## Evidence and provenance requirements

Outline sections cite claim and gap IDs. Structural transitions may be reviewer-authored, but substantive propositions must be traceable.

## Academic judgment points

Choose the organizing logic, balance disciplinary conventions, and decide which gaps belong in conclusions versus limitations.

## Uncertainty and failure handling

Present alternative architectures when the evidence supports materially different narratives. Escalate scope expansion rather than silently adding new questions.

## Prohibited actions

Do not organize around example defaults, hide counterevidence in peripheral sections, or introduce unsupported conclusions as headings.

## Completion requirements

The outline covers all approved questions, maps sections to claims and gaps, preserves uncertainty, and has human approval before detailed briefing.

