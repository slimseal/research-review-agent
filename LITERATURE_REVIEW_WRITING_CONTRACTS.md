# Literature Review Writing Contracts

Contract version: `writing/1`. Additive `writing_data` in the existing state/event journal; no v1/v2 evidence migration, new database, Skill or model SDK.

| Contract | Inputs and server-derived fields |
|---|---|
| LiteratureReviewOutline | review_type, target_word_count, argument_progression, coverage_limitations, gap_connection, duplication_policy; section_structure with section_id/title/purpose/progression/planned_counterarguments/claim_ids/gap_ids; generated outline_id, project_id, research_question, protocol_version, synthesis_version, claim_map_version, section_purposes, linked_claim_ids, linked_gap_ids, planned_counterarguments, version and pending review_status |
| SectionBrief | section_id, purpose, central_argument, required_claim_ids, supporting_evidence_ids, contradictory_evidence_ids, qualifying_evidence_ids, boundary_conditions, methodological_issues, relevant_theories, planned_citations, unresolved_questions, suggested_argument_progression, cannot_claim; version, dependencies, pending review |
| DraftSpanTrace | draft_id/version, section_id, stable span_id, text, exact_text_hash, Unicode-codepoint text_location, classification, claim_ids, evidence_ids, citation_keys, source_binding, generated_at; source_verification_status=structural_only, semantic_review_status=not_reviewed, audit_status=pending at creation |
| AuditFinding | finding_id, audit_id, draft_version, span_id, exact_text, claim_ids/evidence_ids, finding_type, severity, source_reference, explanation, suggested_correction, remaining_uncertainty, deterministic_check_status, semantic_review_status, human_review_status, resolution_status |
| FinalReviewSignOff | signoff_id, draft_version, audit_report_version, outstanding_findings, declared_reviewer, review_timestamp, decision, justification, approval_status, identity_authenticated=false |

`writing-schema` describes input requirements. All submissions need explicit `example_data`; use false for actual research, true for fictional/adversarial evaluation. A lab remains provisional regardless of that label. Target length is planning metadata, not enforced word-count accuracy.

Stable record IDs and monotonically increasing versions are assigned by the controller. Revisions require `record_id` and `supersedes_version`. Current review state is obtained from review history, not a caller-supplied approval field. Draft trace status fields are creation-time values; effective audit status is derived from the current versioned report, never rewritten in old spans.

See `research_review_agent/writing/contracts.py`, `pipeline.py`, and `tests/test_writing.py`. Identity assertions are not secure authentication. Existing CSV records remain readable but cannot silently become reviewed writing records.
