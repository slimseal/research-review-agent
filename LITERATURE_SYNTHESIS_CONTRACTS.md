# Literature Synthesis Contracts — Round 2H

Status: implemented control plane, not scientifically validated autonomous synthesis.

## Authority and compatibility

`research_review_agent/synthesis/{contracts,pipeline,cli}.py` adds `synthesis_data` to the existing workflow journal. No new controller, database, Skill, model SDK or API key. Version 1.0.0 is an additive synthesis contract over Evidence Schema v2. Existing v1/v2 CSV validators remain readable; old claims are not silently promoted. The first managed export archives prior bytes under `07_synthesis/legacy/<sha>.<suffix>`. Reconstructing formal synthesis from a legacy matrix requires reviewed source-linked EvidenceItems, not automatic migration.

The 19 phase IDs, prerequisites and three hard Gate positions are unchanged. Only Phase 9–12 artifact/completion contracts are strengthened.

## SynthesisCorpus

Each corpus records project_id, protocol_version/hash, corpus_id/revision/version/checksum, synthesis_run_id, evidence_matrix_version, eligible_paper_ids, included_evidence_ids, excluded_or_deferred_evidence_ids, every item's disposition/reason, research_question, subquestions, composable research_types, source_verification_levels, coverage_limitations, search_coverage, selection_rationale, search provenance and initial approval_status. Approval is effective only through a separate current review event.

Formal corpus creation requires completed current Phase 8, genuine approved Protocol and upstream eligibility/reading reviews. Provisional mode copies an existing isolated reading lab into a NEW directory, preserving source IDs and dependency hashes but importing no official phase approvals. Included stale evidence is rejected. Provisional supported, uncertain and secondary items remain distinguished. Excluded/deferred evidence remains visible in the selection ledger. Approvals of selection never establish semantic truth.

## Record contract

Common fields: kind-specific stable ID, record_id, revision_id, contract_version, monotonically increasing version, supersedes_revision, created_at, research_question, evidence_ids, record_refs, uncertainty, generator, example_data, derived contributing_paper_ids/research_types and dependency snapshots. `synthesis-schema` exposes required type-specific fields.

Corrections require the latest revision ID and append a new record. New records start pending/not_assessed. Semantic assessments and human-declared review events are separate append histories. No user-supplied approved_by/approved_at is trusted on submit. Review history preserves actor, timestamp, rationale and identity_authenticated=false.

## Artifacts and tracing

Managed views: four map Markdown files, BOUNDARY_CONDITIONS.md, CLAIM_MAP.csv, CLAIM_EVIDENCE_LINKS.csv, GAP_MAP.md and SYNTHESIS_HISTORY.json. Markdown contains readable JSON blocks so no record detail is hidden. The journal is authoritative; the views are not approval tokens. `synthesis-inspect` resolves evidence, reading note, exact anchors, document version and canonical paper identity.

## Invalidation and recovery

Protocol or corpus replacement invalidates all dependent records conservatively. Individual evidence, note, anchor, document or source identity changes invalidate affected record chains. Maps invalidate claims; claims/links invalidate gaps. Search/citation/screening provenance changes block current corpus readiness. Unrelated records retain IDs/history; global corpus reapproval can still be required. No automatic scientific remapping.

A single operation caches repeated read-only source checks; caches never persist across commands. Single-writer use only. After preserving manual edits, `synthesis-recover` restores journal state and regenerates views; it does not recreate missing PDFs or amend an approved Protocol.
