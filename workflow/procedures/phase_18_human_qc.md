# Phase 18 — Human Quality Control

## Operational interface (Round 2I)

Use `writing-completion --phase 18` and `writing-report`. Only an actual human may execute `writing-qc --action approve --by NAME --rationale BASIS --human-attestation`; Codex must not self-sign. Declared identity is not authentication. Approve/reject/revise/defer/reopen/request_source_verification/request_reading/request_discovery append history.

Final completion requires current traceable draft, valid current bibliography, complete independent-context audit with no blocking or uncertain outcomes, current upstream/outline/brief reviews and current human sign-off. Non-blocking limitations may be documented; blocking findings cannot be waived. A Markdown `Status: complete` string is not approval. Labs cannot sign off. Use ordinary `advance` and `writing-recover`, never journal edits.

## Objective and rationale

Provide the final, explicitly human decision on methodological fidelity, evidence traceability, uncertainty, writing quality and readiness, while preserving unresolved limitations.

## Required inputs

- All protocol, search, discovery, screening, reading, evidence, synthesis, argument, writing and audit artifacts.
- Completed claim-evidence and bibliography audits.

## Research operations

1. Review protocol fidelity and all recorded deviations or decisions.
2. Verify that hard gates passed and state history is recoverable.
3. Sample or fully inspect claim-to-evidence chains proportional to risk.
4. Review balance, uncertainty, case neutrality, citation integrity and unresolved failures.
5. Record corrections, residual limitations, reviewer identity, date and approval or non-approval.

## Expected artifacts

- `10_audit/HUMAN_QC.md`

## Evidence and provenance requirements

The record names the human reviewer, identifies reviewed artifact versions and lists unresolved limitations. Approval must be attributable to a human action.

## Academic judgment points

Evaluate whether remaining limitations are acceptable for the intended use and whether disciplinary or ethical review is adequate.

## Uncertainty and failure handling

Withhold approval when material evidence, audit or scope issues remain. Reopen the necessary phase through recorded state transitions and decisions.

## Prohibited actions

The agent must not self-sign, fabricate a reviewer, erase failed gates or describe non-approval as completion.

## Completion requirements

A named human records a dated approval decision, material corrections are resolved or explicitly accepted, and the final state and event journal validate.

