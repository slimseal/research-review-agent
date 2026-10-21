# Reading and extraction review policy

Codex proposes; genuine humans review. A CLI --by string is an unauthenticated declaration, never proof of identity. The agent must not self-sign. All real Round 2G outputs are pending; positive approval tests use conspicuously fictional identities only.

Commands: reading-review and evidence-review, each with --id, --action, --by, --comment, optional --changes JSON and --project.

| Action | Effect |
|---|---|
| accept | Records declared-human acceptance of a current anchored artifact; unsupported evidence cannot be accepted. |
| reject | Retains the rejected proposal and its history. It is not silently removed or a paper exclusion. |
| correct | Appends corrected text/locator/content; preserves stable ID; resets to pending, requiring later acceptance. |
| uncertain / incomplete | Records unresolved review state; prevents completion. |
| reread | Requests return to source inspection; prevents completion. |
| comment | Appends methodological comment, retaining current review state and conservative downstream invalidation. |

Revisions are append-only in the existing event journal. Revisions never rewrite a prior decision. Protected IDs/review authority cannot be supplied through correction fields. For a changed locator, use a real registered SourceAnchor and update the note first if the anchor was not part of the reading record. Reopen the appropriate phase through the controller; do not edit state flags.

This conservative first implementation requires every note and supported extraction to receive acceptance, plus a named per-paper extraction-completeness declaration. Rejected/uncertain/incomplete items require correction or rereading before completion; no automated omission/adjudication shortcut is provided.

reading-queue shows records needing review or revalidation; reading-inspect/evidence-inspect retrieve the exact source basis. A note may document a complete read while still awaiting scientific approval. No independent scientific accuracy score, double-review process or authenticated reviewer service is implemented.
