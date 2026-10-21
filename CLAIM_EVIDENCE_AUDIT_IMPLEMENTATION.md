# Independent Claim–Evidence Audit

## Layer A: deterministic

`writing-validate` checks outline/brief/draft consistency, all span references, normalized links, citation/source identity, document and anchor checksums, current dependencies, required reviews and section coverage. It returns `semantic_verification=false`. Coverage alone does not establish that contrary evidence is fairly represented.

## Layer B: explicit source-grounded reasoning

`writing-audit-context --auditor NAME --context-id ID` creates an immutable context with exact draft version, every span, canonical EvidenceItems/reading notes, full parsed source pages, document identities, source anchors, bibliography identity and a checksummed source manifest. It does not include a writer's defense as an authoritative answer. Inspect sources directly, including contrary and qualifying items.

Execute the audit in a context separate from the writer where feasible. Different declared actor/context IDs are required. The CLI does not start an LLM, authenticate actors or prove a context was actually fresh; actual execution must be separately documented.

Each span review needs outcome supported/unsupported/uncertain/unable_to_verify; source_references with exact evidence/document/anchor IDs; and reasons for all 14 checks. The eight major checks are unsupported_claim, citation_mismatch, overclaim, scope_inflation, citation_laundering, false_consensus, cherry_picking and fake_research_gap. Additional checks are causal_upgrade, numerical_accuracy, mechanism_testing, historical_inference, source_access and source_currency. Each check is pass/fail/uncertain/not_applicable. Failed/uncertain checks need severity and suggested correction. Supporting outcomes cannot coexist with failed/uncertain checks.

`writing-audit-submit` records these judgments. All relevant claim evidence, including counterevidence, needs exact source references. Partial submissions stay incomplete; use a new cumulative submission to finish them. Current audit reports must cover **every span, including transitions**. Findings preserve exact text, IDs, locators, uncertainty and correction recommendations. Later reports retain prior findings and explicit reassessment/supersession history; this is not human adjudication.

Statuses remain separate: structural validation; model semantic audit; independent reference evaluation (not performed unless actually supplied outside this implementation); human approval. No keyword classifier or citation-presence rule claims semantic accuracy.

Final QC rejects unsupported, uncertain, unable-to-verify, stale or blocking findings. Revise via the correct phase, then create a new source-bound audit context. Automatic tests of injected judgments verify record handling and blockers, **not model detection accuracy**.
