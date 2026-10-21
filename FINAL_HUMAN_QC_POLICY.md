# Final Human QC Policy

Only an actual human reviewer may execute `writing-review` or `writing-qc --human-attestation`. Codex must stop for that action. The flag and `--by` are recorded declarations, not authenticated identity. The product is a local workflow controller, not a secure approval/authorization service.

Supported actions: approve, reject, revise, defer, reopen, request_source_verification, request_reading, request_discovery. Every action appends history. Approving outline/brief binds the exact revision; drafts cannot be approved through that shortcut. Final QC names the complete draft version and current audit-report version. Matching declared writer/reviewer identities are rejected. Labs reject all human-approval operations.

Final approval requires current reviewed upstream evidence/claims/gaps, current approved outline/briefs, complete traceable draft, valid current bibliography reconciliation, a complete independent-context model audit with no blocking or unresolved outcomes, and the explicit current human decision. Missing inputs and an old `Status: complete` Markdown string cannot pass.

Correction procedure: record the decision and its reason; reopen the affected phase with the normal controller; revise the actual source/claim/brief/draft; regenerate only affected work where practical; reconcile and re-audit current versions; ask the human again. No fabricated reviewer, automatic sign-off, silent waiver of blocking findings or deletion of earlier decisions.

Fictional end-to-end tests contain conspicuously named FICTIONAL reviewer assertions solely to exercise code paths. They do not evidence a real review or authorize real-source approval. No independent human semantic validation was performed during this engineering round.
