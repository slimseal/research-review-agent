# Phase 0 — Review Protocol

## Objective and rationale

Convert the user's research question into a case-neutral protocol that makes scope, review questions, concepts, search plans, eligibility rules, evidence fields and unresolved decisions explicit before discovery begins. A protocol constrains later choices; it does not predict findings.

## Required inputs

- The user's exact research question and any stated domain, population, place, period or source constraints.
- Any explicit methodological preferences or intended review product.
- The current schema catalog and universal evidence model.

## Research operations

1. Identify the question's epistemic form: quantitative, qualitative, historical/documentary, theoretical/conceptual, archaeological/material, or a justified combination.
2. Draft scope boundaries and answerable subquestions without forcing PICO, exposure–outcome or another single framework.
3. Define ambiguous concepts operationally and list meanings deliberately excluded.
4. Derive search concept blocks and proposed query approaches from those concepts.
5. Draft inclusion and exclusion criteria that can be applied consistently.
6. Select composable research-type extensions and propose additional domain fields only when necessary.
7. Record uncertainties that require a human decision. Save a draft with `approval.status` still unapproved.

## Expected artifacts

- `00_protocol/PROTOCOL.json`
- `00_protocol/REVIEW_PROTOCOL.md`
- `00_protocol/RESEARCH_QUESTIONS.md`
- `00_protocol/INCLUSION_EXCLUSION.md`
- `00_protocol/DOMAIN_EXTENSION_SCHEMA.json`

## Evidence and provenance requirements

Retain the original question verbatim, distinguish user constraints from agent proposals, and record the basis for every added scope boundary. No literature-search result is implied at this phase.

## Academic judgment points

Choose a question decomposition suited to the research type; decide whether extensions should be combined; surface contested terminology and feasibility trade-offs for review.

## Uncertainty and failure handling

Leave consequential choices in the human-decision list. If the question is too ambiguous for a defensible protocol, keep Phase 0 in progress and request the smallest necessary clarification.

## Prohibited actions

Do not invent sources or findings, reuse example concepts, claim a search was performed, impose a fixed query-family template, or approve the protocol on the user's behalf.

## Completion requirements

All required artifacts must pass schema and substantive checks, human-decision items must be resolved or explicitly accepted as limitations, and a named human must run the approval action.

