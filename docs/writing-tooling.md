# Writing and Audit Tutorial

Install the core package using `docs/installation.md`; add the existing pinned `pdf` extra for PDF-backed source validation. No Skill, model SDK or new service is required. Codex/researchers explicitly author academic content. Start every formal operation with `validate`, `next`, and `phase-context`.

```bash
rragent writing-schema
rragent phase-context --project /path/to/review --phase 13
rragent advance --project /path/to/review --phase 13 --status in_progress
rragent writing-context --project /path/to/review
rragent writing-submit --project /path/to/review --kind outline --config outline.json
```

Read the returned blockers. Stop for genuine human outline review; do not self-sign. After review and phase completion, repeat for Phase 14 briefs and Phase 15 drafts. Contracts and source-neutral requirements are in `LITERATURE_REVIEW_WRITING_CONTRACTS.md`. Example plans are evaluation data, not topic defaults.

```bash
rragent writing-context --project /path/to/review --section section-id
rragent writing-submit --project /path/to/review --kind brief --config brief.json
rragent writing-submit --project /path/to/review --kind draft --config section.json
rragent writing-trace --project /path/to/review --id SPAN-returned-id
rragent writing-impact --project /path/to/review --id EV-existing-id
rragent writing-validate --project /path/to/review
```

Each substantive span has text, classification, claim_ids, evidence_ids and citation_keys; inline citation syntax is `[@P0000001]`. Do not paste a free-standing draft into a projection file. Ask Codex to revise through an explicit versioned submission, retaining stable span IDs and supplying supersedes_version.

```bash
# After normal Phase 16 entry:
rragent writing-bibliography --project /path/to/review
# After normal Phase 17 entry, use a distinct auditor context:
rragent writing-audit-context --project /path/to/review --auditor "Reviewer model context" --context-id fresh-audit-id
rragent writing-audit-submit --project /path/to/review --id AUD-returned-id --config source-audit.json
rragent writing-report --project /path/to/review
rragent writing-completion --project /path/to/review --phase 18
```

The following commands are **human-only**, after actual review; never execute them simply to progress an automated task:

```bash
rragent writing-review --project /path/to/review --id OUTLINE-returned-id --action approve --by "Actual reviewer" --rationale "Actual review basis" --human-attestation
rragent writing-qc --project /path/to/review --action approve --by "Actual reviewer" --rationale "Actual final review basis" --human-attestation
```

Natural language routing: “next approved section” → writing-context; “show sources/why flagged” → writing-trace and writing-report; “unsupported claims” → structural errors plus current semantic findings in writing-report; “check paragraph” → versioned spans, fresh audit context and explicit source judgments; “final blockers” → writing-completion. No GUI is implied.

For interruption, preserve unexpected edits and run `writing-recover`. Resume from recorded context/version IDs and journals, not conversational memory. For bounded experiments only: `writing-lab-init --project /new/isolated/lab --source /existing/synthesis-lab`. It copies local sources but no official phase completion and never permits sign-off.
