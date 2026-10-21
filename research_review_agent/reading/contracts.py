"""Additive reading/evidence v1 contracts over the existing universal Schema v2."""
VERSION = "1.0.0"
CONTENT_FIELDS = (
    "bibliographic_identity", "research_problem", "questions_hypotheses", "framework",
    "research_context", "population_cases_corpus_sites_materials", "research_design",
    "data_sources", "methods", "operational_definitions", "empirical_findings",
    "quantitative_results", "qualitative_interpretations", "historical_propositions",
    "archaeological_interpretations", "mechanisms", "boundary_conditions", "null_negative",
    "contradictory_mixed", "author_interpretations", "author_limitations",
    "methodological_concerns", "contribution", "can_support", "cannot_support",
)
MISSING = {"not_reported", "not_applicable", "not_reliably_extractable", "unavailable"}
READING_STATUSES = {"in_progress", "partial", "completed", "blocked"}
EXTRACTION_STATUSES = {"supported", "uncertain", "incomplete", "unsupported"}
BOUNDARIES = ("source_reports", "author_interpretation", "codex_inference", "uncertainty", "cannot_support")
OUTCOMES = {"positive", "negative", "null", "mixed", "contradictory", "conditional", "argument", "interpretation", "uncertain"}
EXTRA_FIELDS = ["reading_note_id", "document_id", "document_sha256", "source_anchor_ids",
                "extraction_run_id", "extraction_status", "review_status", "revision_id",
                "support_boundaries", "result_kind", "citation_basis", "source_scope"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_note(value):
    require(value.get("reading_status") in READING_STATUSES, "INVALID_READING_STATUS")
    require(isinstance(value.get("unresolved_material"), list), "UNRESOLVED_MATERIAL_REQUIRED")
    coverage = value.get("source_coverage", {})
    require(isinstance(coverage.get("pages_read"), list) and isinstance(coverage.get("sections"), list)
            and bool(coverage["sections"]), "EXPLICIT_READING_COVERAGE_REQUIRED")
    require(isinstance(coverage.get("visual_pages"), list) and nonempty(coverage.get("layout_assessment")), "LAYOUT_ASSESSMENT_REQUIRED")
    for section in coverage["sections"]:
        require(nonempty(section.get("name")) and section.get("status") in {"read", *MISSING}
                and nonempty(section.get("basis")), "SECTION_INSPECTION_OR_ABSENCE_REQUIRED")
    content = value.get("content", {})
    require(set(content) == set(CONTENT_FIELDS), "READING_CONTENT_FIELDS_REQUIRED")
    for key, item in content.items():
        require(isinstance(item, dict) and item.get("status") in {"present", *MISSING}, "INVALID_CONTENT_STATUS:" + key)
        if item["status"] == "present":
            require(nonempty(item.get("text")), "CONTENT_TEXT_REQUIRED:" + key)
            require(item.get("epistemic_role") in {"source_report", "author_interpretation", "codex_inference"}, "EPISTEMIC_ROLE_REQUIRED")
            require(isinstance(item.get("source_anchor_ids"), list), "ANCHOR_LIST_REQUIRED")
            require(bool(item["source_anchor_ids"]) or nonempty(item.get("grounding_unavailable_reason")), "CONTENT_GROUNDING_REQUIRED:" + key)
        else:
            require(nonempty(item.get("reason")), "MISSING_VALUE_REASON_REQUIRED:" + key)


def validate_item(value):
    for key in ("paper_id", "reading_note_id", "research_question", "research_context", "evidence_type",
                "finding_argument_proposition", "limitations_uncertainty", "extraction_run_id"):
        require(nonempty(value.get(key)), "EVIDENCE_FIELD_REQUIRED:" + key)
    require(value.get("source_basis") == "full_text", "FULL_TEXT_REQUIRED: abstract/metadata cannot support detailed extraction")
    require(value.get("extraction_status") in EXTRACTION_STATUSES, "INVALID_EXTRACTION_STATUS")
    require(value.get("result_kind") in OUTCOMES, "RESULT_KIND_REQUIRED")
    require(value.get("citation_basis") in {"primary_in_this_source", "secondary_report"}, "CITATION_BASIS_REQUIRED")
    require(value.get("source_scope") in {"body_text", "table", "figure", "equation", "supplement"}, "SOURCE_SCOPE_REQUIRED")
    require(isinstance(value.get("example_data"), bool), "EXAMPLE_BOOLEAN_REQUIRED")
    require(isinstance(value.get("source_anchor_ids"), list), "ANCHOR_LIST_REQUIRED")
    require(bool(value["source_anchor_ids"]) or (value["extraction_status"] != "supported"
            and nonempty(value.get("grounding_unavailable_reason"))), "EXACT_SOURCE_ANCHOR_REQUIRED")
    require(isinstance(value.get("support_boundaries"), dict)
            and all(nonempty(value["support_boundaries"].get(k)) for k in BOUNDARIES), "SUPPORT_BOUNDARIES_REQUIRED")
    require(isinstance(value.get("research_types"), list) and bool(value["research_types"])
            and all(isinstance(x, str) for x in value["research_types"]), "ROW_RESEARCH_TYPES_REQUIRED")
    require(isinstance(value.get("extension_json"), dict), "EXTENSION_OBJECT_REQUIRED")
    require(value.get("inference_class") in {"descriptive", "associational", "causal", "interpretive", "conceptual"}, "INFERENCE_CLASS_REQUIRED")
    if value["inference_class"] == "causal":
        require(nonempty(value.get("causal_identification_basis")), "CAUSAL_IDENTIFICATION_REQUIRED")
    if value["citation_basis"] == "secondary_report":
        require(nonempty(value.get("secondary_source_reference")), "SECONDARY_REPORT_REFERENCE_REQUIRED")


def schema():
    return {"contract_version": VERSION, "note_content_fields": list(CONTENT_FIELDS),
            "reading_statuses": sorted(READING_STATUSES), "missing_statuses": sorted(MISSING),
            "evidence_additional_fields": EXTRA_FIELDS, "support_boundaries": list(BOUNDARIES),
            "result_kinds": sorted(OUTCOMES), "extraction_statuses": sorted(EXTRACTION_STATUSES),
            "authority": "workflow event journal; projections are not approval tokens",
            "verification": "structural source resolution != semantic correctness != human review"}
