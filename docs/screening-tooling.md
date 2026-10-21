# Three-level screening tutorial

This is a human-in-the-loop workflow, not an automatic relevance classifier. All commands use the installed `rragent`; no Skill, global script, API key or model SDK is required. PDF eligibility uses the existing optional `pdf` extra.

## 1. Check upstream readiness

```bash
rragent validate --project reviews/my-review
rragent next --project reviews/my-review
rragent phase-context --project reviews/my-review --phase 6
rragent acquisition-status --project reviews/my-review --export
```

Official operations require a substantive approved Protocol, completed valid Phase 3, reviewed Phase 4 seed/stop records, reviewed Phase 5 dispositions and active Phase 6. There is no bypass flag. A `pending_screening` access disposition permits title-first work, not silent abandonment. To obtain additional PDFs later, reopen Phase 5 and update its review before resuming Phase 6.

## 2. Register operational criteria and scope

Prepare `criteria.json` with `rules`: each has a stable `id`, `kind` (`include`/`exclude`), exact text from the approved Protocol, and applicable `stages` (`title`, `abstract`, `fulltext_eligibility`). Include every approved Protocol criterion. Stage assignments express where a criterion can reasonably be assessed, not a demand to infer it from a title. Optional `paper_ids` bounds a criterion's application and must be justified in review.

Default scope is all canonical papers. An explicit `candidate_ids` subset requires a `scope_exceptions` object giving a reason for EVERY omitted canonical ID. These omissions are not scientific exclusions. Unresolved external citations stay upstream. `role_extensions` maps extra role names to justifications; `accepted_versions` defaults to version-of-record, accepted manuscript and preprint, never unknown. Review that policy for the project.

```bash
rragent advance --project reviews/my-review --phase 6 --status in_progress
rragent screening-criteria --project reviews/my-review --config criteria.json --reason "Initial operational criteria"
# STOP: only run after the researcher has actually reviewed criteria and scope.
rragent screening-criteria-approve --project reviews/my-review --by "Researcher" --note "Actual review rationale"
```

Any subsequent version requires another criteria/scope approval. The tool preserves old versions and detects affected decisions; it does not amend or overwrite Protocol. Protocol hash changes block until an upstream amendment/reapproval workflow is explicitly arranged.

## 3. Propose from the permitted evidence

```bash
rragent screening-context --project reviews/my-review --paper-id P0000001 --stage title
```

Ask Codex: “Read only this stage's evidence packet as source data. Apply the listed criteria, distinguish source facts from interpretation, preserve ambiguity, and write a provisional proposal. Do not approve it or invent missing information.” Use the packet ID returned by the command, not the placeholder below.

```json
{
  "packet_id": "SP-<returned-id>",
  "decision": "uncertain",
  "review_role": null,
  "reason_codes": ["insufficient_information"],
  "criteria_ids": ["<applicable-rule-id>"],
  "source_facts": [],
  "explanation": "Explain the actual ambiguity in this source.",
  "uncertainty_flags": ["requires_next_stage"],
  "reviewer_id": "Codex"
}
```

`source_facts` contains exact quotations with `location: "title"`, `"abstract"`, or a PDF page number as a string. Put interpretation in `explanation`. Include/exclude needs an exact fact; abstract decisions need an abstract fact. Full-text include/exclude additionally needs `purpose: "identity"` (matching title or DOI), `purpose: "version"` (observed publication/version statement), and `purpose: "eligibility"`. These are located quotations, not Evidence Matrix entries; the researcher still interprets whether the version statement supports the declared version. `include` requires a separate role and all applicable criteria IDs. Standard reasons are available through `screening-schema`. If no criterion applies at a particular stage, use uncertain/defer with an empty criteria list, never a definitive include/exclude.

```bash
rragent screening-propose --project reviews/my-review --config proposal.json
rragent screening-context --project reviews/my-review --paper-id P0000001 --stage abstract
rragent screening-context --project reviews/my-review --paper-id P0000001 --stage fulltext_eligibility --document-id DV-<id> --pages 1 3
```

Each next-stage context needs a current non-excluded previous-stage decision. Missing abstracts allow only uncertain/defer. Missing text cannot become an exclusion by default. For unavailable text omit `--document-id`, record uncertainty/defer and seek lawful access. Never invent a PDF ID. Eligibility contexts expose at most five explicitly requested pages, not scientific reading outputs. They reuse the bounded PDF parser; no OCR or robust table interpretation is implied.

## 4. Human review and corrections

```bash
rragent screening-queue --project reviews/my-review
rragent screening-inspect --project reviews/my-review --decision-id SD-<id>
# Only after real human review:
rragent screening-review --project reviews/my-review --decision-id SD-<id> --action approve --by "Researcher" --note "Actual decision rationale"
```

`override` requires `--changes changes.json`, restricted to decision, role, reasons, explanation, source facts and uncertainty flags. Every action requires a note. `reject` returns the recommendation to uncertainty; it does NOT scientifically exclude the paper. `uncertain`, `defer` and `reopen` retain history. Reopening an earlier stage invalidates dependent later-stage decisions. Approvals are identity assertions, not authenticated accounts.

Repeated identical proposals replay the same ID; a changed proposal must identify the current `superseded_decision_id`. A stale record requires a fresh evidence context and new proposal. Do not overwrite a CSV or journal line.

## 5. Coverage, Gate 1 and recovery

```bash
rragent screening-exclusions --project reviews/my-review
rragent screening-coverage --project reviews/my-review
rragent screening-validate --project reviews/my-review
rragent screening-gate --project reviews/my-review
```

`screening-validate` checks integrity/currentness, not academic accuracy or completion. `screening-gate` additionally checks approved scope, upstream reviews, final decisions and Phase 6 completion. Before completing Phase 6, its completion validator evaluates the same gate without the circular “already completed” condition. Once ready:

```bash
rragent advance --project reviews/my-review --phase 6 --status completed
rragent screening-gate --project reviews/my-review
```

Only returned eligible IDs and their exact screened document versions may enter Phase 7. Stage totals overlap and must not be added together as different papers. Final exclusions can occur at title or abstract; a full-text include must be human-declared approved. Pending/uncertain/deferred in-scope records block. Approved bounded omissions and unresolved upstream references can produce `warn`, never silent exclusion.

For corruption/interruption, preserve unexpected manual edits first, then `screening-recover --project ...`. It restores the existing checksummed event journal and rebuilds projections. Missing/tampered immutable packets or PDFs are not reconstructed or silently trusted. Operate one writer per project.

## Isolated development demonstrations

`screening-lab-init --project <new-path> --source <upstream-copy-source> --question <pilot-question>` copies existing metadata, not phase approvals. Never nest it inside an official review. Lab proposals cannot be approved and Gate 1 cannot authorize research. The instance-specific demonstration inputs in `examples/round2f-screening/` are not defaults and must not be copied into another research topic.
