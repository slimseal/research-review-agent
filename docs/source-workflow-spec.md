# Source Workflow Specification

This document is the case-neutral implementation specification extracted from the complete Phase 0-18 source workflow. Topic examples from the source are excluded from this specification and isolated under `examples/`.

## Evidence chain

```text
Final prose claim
  -> claim map
  -> evidence matrix
  -> paper reading note
  -> inspected full-text file
  -> paper registry
  -> DOI or other bibliographic identity
```

Every link is required for substantive claims. Metadata and abstracts may support discovery or screening but do not substitute for full-text Methods and Results.

## Phase map and dependencies

| Phase | Purpose | Required output | Dependency |
|---:|---|---|---|
| 0 | Freeze the review question, scope, definitions, and eligibility rules | Protocol, questions, criteria, domain extension schema | Human approval |
| 1 | Build concept blocks and a synonym matrix | Search concepts, keyword matrix | Approved protocol |
| 2 | Design complementary, protocol-derived search strategies | Search strings | Phase 1 |
| 3 | Establish seed literature and research clusters | Seed and discovery tables, search log | Phase 2; live sources |
| 4 | Expand backward, forward, and related-paper links | Citation expansion tables | Phase 3; citation sources |
| 5 | Acquire lawful full text and register stable identities | Paper registry, PDF library, bibliography | Phases 3-4; access rights |
| 6 | Apply title, abstract, and full-text eligibility decisions | Screening master and exclusion log | Frozen criteria and available evidence |
| 7 | Read eligible full texts with exact locations | One structured note per paper | Gate 1 |
| 8 | Store one concrete result per evidence row | Evidence matrix | Phase 7 |
| 9 | Synthesize themes, theories, methods, and controversies | Four synthesis maps | Gate 2 evidence prerequisite satisfied |
| 10 | Analyze where findings do and do not apply | Boundary-condition map | Phase 9 |
| 11 | Convert evidence patterns into auditable propositions | Claim map | Phases 8-10 |
| 12 | Derive gaps from known, mixed, method-limited, and unresolved evidence | Gap map | Gate 3 |
| 13 | Design the review architecture | Outline | Phase 12 |
| 14 | Constrain every section before drafting | Section briefs | Phase 13 |
| 15 | Draft section by section from approved evidence only | Draft review | Gate 2 and Phase 14 |
| 16 | Reconcile citations, registry, and bibliography | Bibliography audit | Phase 15; may be maintained earlier |
| 17 | Audit every substantive claim | Claim-evidence audit | Phases 11, 15, and 16 |
| 18 | Manually inspect high-risk language and factual details | Signed human QC record | Phase 17 |

## Search design

A single broad query is insufficient. Derive multiple complementary strategies from the approved protocol and source systems. Possible blocks include phenomena, actors or units, context, chronology, source genre, material class, methods, comparisons, mechanisms, and outcomes, but none is universally required. A qualitative, historical, conceptual, or archaeological review must not be forced into an exposure-outcome search template.

Log every exact query, source, filter, timestamp, result count, and failure. Search breadth must be described rather than claimed complete.

## Screening contract

Screen in three stages: title, abstract, and full text. At each stage use only evidence available at that stage. Preserve earlier decisions, select one primary exclusion reason, and retain uncertainty when required information is absent. Full-text screening assigns review roles such as core evidence, context, theory, method, exclude, or uncertain.

## Reading and extraction contract

All source notes record identity, addressed question, source basis, context, finding/argument/proposition, exact source-appropriate location, limitations/uncertainty, verification status, what the source can support, and what it cannot support. Quantitative, qualitative, historical/documentary, theoretical/conceptual, and archaeological/material details belong in composable protocol extensions.

The evidence matrix stores one auditable result, interpretation, argument, or proposition per row, not one source per row. Each record keeps qualifiers, uncertainty, evidence type, exact source-appropriate locator, limitations, verification status, and research-type extension values.

## Synthesis and claims

Synthesis reorganizes the corpus by themes, theories, methods, controversies, and boundary conditions. It must compare how evidence was produced, not only what topic each paper covers. A claim record must retain supporting and contradictory evidence, design strength, boundaries, allowed wording, prohibited overclaiming, and confidence.

A defensible gap moves through four layers:

1. what the evidence supports;
2. what remains inconsistent or uncertain;
3. why existing methods or coverage cannot resolve it;
4. the precise unanswered question.

Novelty language is prohibited unless supported by the documented search.

## Drafting and audit rules

Draft by claim, evidence pattern, comparison, contradiction, explanation, boundary, and implication. Do not draft as a list of paper summaries. Association, prediction, mediation, moderation, and causation must remain distinct.

The final audit checks unsupported claims, citation mismatch, overclaiming, scope inflation, secondary-citation laundering, false consensus, cherry-picking, and fabricated gaps. Human QC rechecks numbers, sample sizes, effect sizes, contexts, dates, identifiers, page locations, quotations, attribution, design labels, mediation/moderation, and causal identification.

## Hard gates

1. Screening before large-scale full-text reading.
2. Evidence matrix before drafting.
3. Claim map before finalizing a research gap.

The kit adds one operational prerequisite required by the user's case-neutral design: an explicitly approved protocol before topic-specific concepts, search strategies, criteria, or extension fields become authoritative.

