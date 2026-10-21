"""Screening v1 is additive; legacy evidence schemas and identities are unchanged."""
STAGES = ("title", "abstract", "fulltext_eligibility")
DECISIONS = {"include", "exclude", "uncertain", "defer"}
ROLES = {"include_core", "include_context", "include_theory", "include_method"}
REASONS = {"potentially_relevant", "criteria_met", "criterion_not_met", "insufficient_information",
           "missing_abstract", "fulltext_unavailable", "extraction_insufficient", "wrong_document_version",
           "identity_unresolved", "related_version", "awaiting_authorized_import", "human_reopened"}
FIELDS = ["decision_id", "project_id", "paper_id", "protocol_version", "screening_criteria_version",
          "candidate_set_version", "screening_stage", "source_basis", "decision", "review_role",
          "reason_codes", "explanation", "reviewer_type", "reviewer_id", "review_timestamp",
          "document_id", "uncertainty_flags", "approval_status", "superseded_decision_id",
          "packet_id", "criteria_ids", "source_facts", "previous_stage_id", "review_note"]

ARTIFACTS = {
    "04_screening/SCREENING_MASTER.csv": {"owner_phase": 6, "schema": "ScreeningDecision/v1 current per paper-stage", "depends_on": ["decision_history", "candidate_scope"]},
    "04_screening/EXCLUSION_LOG.csv": {"owner_phase": 6, "schema": "ScreeningDecision/v1 historical exclusions, including superseded proposals", "depends_on": ["decision_history"]},
    "04_screening/FULLTEXT_ELIGIBILITY_LOG.csv": {"owner_phase": 6, "schema": "ScreeningDecision/v1 historical fulltext_eligibility records", "depends_on": ["decision_history", "DocumentVersion", "packets"]},
    "04_screening/SCREENING_DECISION_HISTORY.jsonl": {"owner_phase": 6, "schema": "ScreeningDecision/v1 append-history projection", "depends_on": ["workflow_event_journal"]},
    "04_screening/SCREENING_CRITERIA_VERSION.json": {"owner_phase": 6, "schema": "CriteriaVersions/v1 rules, corpus snapshots, declared human approvals", "depends_on": ["Protocol", "PaperRegistry", "workflow_event_journal"]},
    "04_screening/SCREENING_COVERAGE_REPORT.md": {"owner_phase": 6, "schema": "Coverage/v1 counts with provisional/final separation", "depends_on": ["current_decisions", "criteria", "PaperRegistry", "upstream_candidates", "DocumentVersion"]},
    "03_library/ACQUISITION_STATUS.csv": {"owner_phase": 5, "schema": "AcquisitionStatus/v1 one row per paper-document or missing-document placeholder", "depends_on": ["PaperRegistry", "DocumentVersion", "AcquisitionAttempt", "ACQUISITION_REVIEW", "screening_history"]},
    "04_screening/GATE1_VALIDATION_REPORT.json": {"owner_phase": 6, "schema": "Gate1/v1 pass/fail/blocked/warn, allowed, errors, blockers, warnings, eligible_paper_ids", "depends_on": ["current_upstream_approvals", "Protocol", "criteria", "candidate_scope", "decisions", "documents", "artifact_hashes"]},
}


def validate_decision(value):
    if set(FIELDS) - set(value):
        raise ValueError("SCREENING_FIELDS_REQUIRED")
    if value["screening_stage"] not in STAGES or value["decision"] not in DECISIONS:
        raise ValueError("INVALID_STAGE_OR_DECISION")
    for key in ("reason_codes", "uncertainty_flags", "criteria_ids", "source_facts"):
        if not isinstance(value[key], list):
            raise ValueError("INVALID_LIST:" + key)
    for key in ("reason_codes", "uncertainty_flags", "criteria_ids"):
        if not all(isinstance(v, str) and v.strip() for v in value[key]):
            raise ValueError("INVALID_STRING_LIST:" + key)
    if any(not isinstance(f, dict) or not isinstance(f.get("quote"), str) or not isinstance(f.get("location"), str) for f in value["source_facts"]):
        raise ValueError("INVALID_SOURCE_FACT")
    if not value["reason_codes"] or set(value["reason_codes"]) - REASONS:
        raise ValueError("UNKNOWN_REASON_CODE")
    for key in ("decision_id", "project_id", "paper_id", "protocol_version", "explanation", "reviewer_id", "review_timestamp"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError("REQUIRED_TEXT:" + key)
    if value["reviewer_type"] not in {"model", "human_declared"} or value["approval_status"] not in {"proposed", "approved", "reopened"}:
        raise ValueError("INVALID_REVIEW_STATUS")
    if value["approval_status"] == "approved" and value["reviewer_type"] != "human_declared":
        raise ValueError("MODEL_CANNOT_APPROVE")
