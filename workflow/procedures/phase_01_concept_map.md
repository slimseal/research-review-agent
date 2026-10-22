# Phase 1 — Search Concept Map

## Objective and rationale

Translate the approved protocol into a structured, domain-sensitive vocabulary map that supports reproducible searching while preserving the question's actual meanings.

## Required inputs

- Approved `00_protocol/PROTOCOL.json` and research subquestions.
- Protocol concept definitions, scope limits and selected research types.

## Research operations

Honor the researcher's recorded database choice and the approved Protocol. Build concepts without defaulting to another provider. Any live vocabulary lookup requires its own authorized scope; proposed synonyms must not be reported as verified database indexing terms.

1. Derive concept blocks from each subquestion and their logical relationships.
2. Add synonyms, spelling variants, historical terms, discipline-specific labels and controlled vocabulary where justified.
3. Separate homonyms and excluded senses with scope notes.
4. Trace every term to a protocol concept, user-supplied vocabulary or documented vocabulary source.
5. Identify concepts that should not be combined in every query.

## Expected artifacts

- `01_search/SEARCH_CONCEPTS.md`
- `01_search/KEYWORD_MATRIX.csv`

## Evidence and provenance requirements

Each keyword row states its source or derivation. Vocabulary suggestions are proposals, not evidence of field usage unless verified against a recorded source.

## Academic judgment points

Judge conceptual equivalence, time-sensitive terminology, interdisciplinary differences and the likely recall cost of overly narrow terms.

## Uncertainty and failure handling

Mark disputed or unverified synonyms. Escalate scope-changing concepts for protocol amendment rather than silently expanding the question.

## Prohibited actions

Do not import demonstration keywords, treat related concepts as exact synonyms, or silently exclude a protocol subquestion.

## Completion requirements

Every subquestion has mapped concepts, ambiguity notes and provenance; the files contain no unexplained or example-derived defaults.

