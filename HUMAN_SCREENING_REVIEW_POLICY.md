# Human screening review policy

Models produce `reviewer_type=model`, `approval_status=proposed`. Passing fields named human/approved to proposal import does not grant approval. Official criteria and scope must be explicitly approved before screening operations. No developer or pilot script may self-sign research approvals.

The researcher inspects `screening-inspect --decision-id ...`: this returns the ORIGINAL packet, exact quotations, interpretation, uncertainties and current stale status. `screening-review` then appends an approved/reopened decision with `reviewer_type=human_declared`, the declared reviewer and timestamp, rationale, and `superseded_decision_id`. It never edits the earlier row.

Supported actions:

- approve: retain the assessed decision and evidence after actual review;
- override: change only permitted judgment fields, with explicit rationale and valid evidence;
- reject: return the proposal to uncertainty, not scientific exclusion;
- uncertain/defer: retain unresolved cases visibly;
- reopen: make a prior decision unresolved and invalidate dependent later stages.

Stale/older superseded decisions cannot be approved. Create a current context and replacement proposal; or explicitly reopen before reassessment. Changed proposals must identify the latest superseded record. Exact repeated imports replay the same decision ID rather than multiplying counts.

`--by` is an assertion, not account authentication, a digital signature, ethics review or proof that a researcher actually inspected the evidence. `identity_authenticated=false` is explicit. This local MVP cannot defend against someone rewriting both the entire journal and its checksums. Do not claim authenticated review or regulatory-grade audit assurance.

An isolated screening lab rejects criteria and decision approval commands. Its real metadata and PDF inspections remain provisional. Automated tests use clearly labeled FICTIONAL approval fixtures in temporary official-format projects; those demonstrate control flow only. Round 2F's real pilot has zero genuine human approvals.

No dual-independent-reviewer or blinded adjudication workflow is implemented. If required by the approved Protocol, that remains an external/manual policy obligation and a limitation before production review use.
