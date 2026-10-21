"""Portable, case-neutral writing/audit contracts (additive; no legacy migration)."""
from ..reading.contracts import require, nonempty

VERSION = "writing/1"
PHASE = {"outline": 13, "brief": 14, "draft": 15}
ACTIONS = {"approve", "reject", "revise", "defer", "reopen", "request_source_verification", "request_reading", "request_discovery"}
CHECKS = ("unsupported_claim", "citation_mismatch", "overclaim", "scope_inflation", "citation_laundering",
          "false_consensus", "cherry_picking", "fake_research_gap", "causal_upgrade", "numerical_accuracy",
          "mechanism_testing", "historical_inference", "source_access", "source_currency")
FIELDS = {
    "outline": ("review_type", "argument_progression", "coverage_limitations", "gap_connection", "duplication_policy"),
    "brief": ("section_id", "purpose", "central_argument", "boundary_conditions", "methodological_issues",
              "relevant_theories", "suggested_argument_progression", "cannot_claim"),
    "draft": ("section_id", "writer", "writer_context_id"),
}


def validate(kind, value):
    require(kind in FIELDS and isinstance(value, dict), "INVALID_WRITING_KIND")
    require(all(nonempty(value.get(k)) for k in FIELDS[kind]), "INCOMPLETE_" + kind.upper())
    require(isinstance(value.get("example_data"), bool), "EXPLICIT_EXAMPLE_LABEL_REQUIRED")
    forbidden = {"approved", "audit_status", "semantic_review_status", "human_review_status", "authenticated"}
    require(not (forbidden & set(value)), "CALLER_CANNOT_SET_REVIEW_STATUS")
    if kind == "outline":
        require(isinstance(value.get("target_word_count"), int) and value["target_word_count"] > 0, "TARGET_WORD_COUNT_REQUIRED")
        sections = value.get("section_structure")
        require(isinstance(sections, list) and sections, "OUTLINE_SECTIONS_REQUIRED")
        ids = []
        for section in sections:
            require(all(nonempty(section.get(k)) for k in ("section_id", "title", "purpose", "argument_progression", "planned_counterarguments")), "INCOMPLETE_SECTION")
            ids.append(section["section_id"])
            for key in ("claim_ids", "gap_ids"):
                require(isinstance(section.get(key), list), "SECTION_REFERENCES_REQUIRED")
            require(section["claim_ids"], "SECTION_CLAIMS_REQUIRED")
        require(len(ids) == len(set(ids)), "DUPLICATE_SECTION_ID")
    if kind == "brief":
        for key in ("required_claim_ids", "supporting_evidence_ids", "contradictory_evidence_ids", "qualifying_evidence_ids", "planned_citations", "unresolved_questions"):
            require(isinstance(value.get(key), list), "BRIEF_LIST_REQUIRED:" + key)
        require(value["required_claim_ids"], "BRIEF_CLAIMS_REQUIRED")
    if kind == "draft":
        require(isinstance(value.get("spans"), list) and value["spans"], "DRAFT_SPANS_REQUIRED")
        for span in value["spans"]:
            require(nonempty(span.get("text")), "SPAN_TEXT_REQUIRED")
            require(span.get("classification") in {"substantive", "transition", "unresolved"}, "SPAN_CLASSIFICATION_REQUIRED")
            for key in ("claim_ids", "evidence_ids", "citation_keys"):
                require(isinstance(span.get(key), list), "SPAN_REFERENCES_REQUIRED:" + key)
            if span["classification"] == "substantive":
                require(span["claim_ids"] and span["evidence_ids"] and span["citation_keys"], "UNTRACED_SUBSTANTIVE_SPAN")
            else:
                require(nonempty(span.get("justification")), "NON_SUBSTANTIVE_JUSTIFICATION_REQUIRED")
            if span["classification"] == "transition":
                require(not any(span[k] for k in ("claim_ids", "evidence_ids", "citation_keys")), "TRANSITION_CANNOT_HIDE_CITED_CLAIM")


def schema():
    return {"contract_version": VERSION, "kinds": FIELDS, "audit_checks": CHECKS, "human_actions": sorted(ACTIONS),
            "contracts": ["LiteratureReviewOutline", "SectionBrief", "DraftSpanTrace", "AuditFinding", "FinalReviewSignOff"],
            "notice": "Model submissions are drafts. Declared identities are not authenticated. Structural linkage is not entailment."}
