"""Additive contracts; scientific judgments are supplied explicitly, never inferred by a parser."""
from ..reading.contracts import require, nonempty

VERSION = "1.0.0"
PHASE = {"theme": 9, "theory": 9, "method": 9, "controversy": 9, "boundary": 10,
         "claim": 11, "link": 11, "gap": 12}
MAPS = ("theme", "theory", "method", "controversy", "boundary", "claim", "gap")
RELATIONS = {"supports", "contradicts", "qualifies", "context", "uncertain"}
DIRECTNESS = {"direct_source", "indirect", "secondary_citation"}
CLAIM_TYPES = {"empirical_association", "causal", "interpretive", "theoretical", "methodological",
               "historical", "archaeological", "conditional", "coverage_assessment"}
GAP_TYPES = {"inconsistency", "methodological_limitation", "conceptual_disagreement", "context_population_limitation",
             "temporal_limitation", "source_limitation", "mechanism_uncertainty"}
CHECKS = ("causality", "prediction", "mechanism", "generalization", "historical_inference", "secondary_source",
          "null_results", "contradictions", "uncertainty", "independence", "consensus", "novelty")
ACTIONS = {"approve", "reject", "revise", "uncertain", "defer", "reopen", "request_reading", "request_discovery"}
TEXT_FIELDS = {
    "theme": ("label", "definition", "coverage", "interpretation", "comparability"),
    "theory": ("name", "propositions", "mechanisms", "competing_explanations", "conceptual_limits", "context"),
    "method": ("design", "data_source_type", "case_selection", "analytic_method", "measurement_interpretation",
               "identification_applicability", "limitations", "relevance_to_disagreement"),
    "controversy": ("context_differences", "method_differences", "unresolved_questions", "possible_explanations"),
    "boundary": ("dimension", "context", "nature_direction", "strength", "alternative_explanations"),
    "claim": ("proposition", "scope", "strength", "methodological_limits", "allowed_wording", "prohibited_overclaim"),
    "link": ("claim_id", "evidence_id", "strength", "rationale"),
    "gap": ("established", "unresolved", "methodological_justification", "proposed_research_question", "confidence",
            "search_limitations", "coverage_basis", "derivation", "unresolved_contradictions"),
    "assessment": ("map_kind", "rationale"),
}


def validate_record(kind, value):
    require(kind in TEXT_FIELDS, "UNKNOWN_SYNTHESIS_KIND")
    for key in (*TEXT_FIELDS[kind], "research_question", "uncertainty", "generator"):
        require(nonempty(value.get(key)), "SYNTHESIS_FIELD_REQUIRED:" + key)
    for key in ("evidence_ids", "record_refs"):
        require(isinstance(value.get(key), list) and all(nonempty(x) for x in value[key])
                and len(value[key]) == len(set(value[key])), "UNIQUE_REFERENCE_LIST_REQUIRED:" + key)
    require(isinstance(value.get("example_data"), bool), "EXAMPLE_BOOLEAN_REQUIRED")
    if kind != "assessment":
        require(bool(value["evidence_ids"]), "EVIDENCE_REFERENCES_REQUIRED")
    if kind == "assessment":
        require(value["map_kind"] in MAPS, "INVALID_MAP_ASSESSMENT")
        require(value.get("disposition") in {"populated", "none_warranted", "deferred"}, "MAP_DISPOSITION_REQUIRED")
    if kind in {"theme", "theory", "controversy"}:
        for key in ("supporting_evidence_ids", "qualifying_evidence_ids", "contradictory_evidence_ids"):
            require(isinstance(value.get(key), list) and set(value[key]) <= set(value["evidence_ids"]), "EVIDENCE_ROLE_REQUIRED:" + key)
    if kind == "theme":
        comparisons = value.get("comparisons", [])
        require(bool(comparisons), "COMPARATIVE_ANALYSIS_REQUIRED")
        for comparison in comparisons:
            require(nonempty(comparison.get("dimension")) and nonempty(comparison.get("assessment"))
                    and comparison.get("comparability") in {"comparable", "noncomparable", "uncertain"}
                    and bool(comparison.get("evidence_ids")) and set(comparison["evidence_ids"]) <= set(value["evidence_ids"]),
                    "EVIDENCE_LINKED_COMPARISON_REQUIRED")
    if kind == "theory":
        require(value.get("mechanism_status") in {"proposed", "empirically_tested", "mixed", "not_applicable"}, "MECHANISM_STATUS_REQUIRED")
    if kind == "controversy":
        positions = value.get("positions", [])
        require(len(positions) >= 2, "TWO_DOCUMENTED_POSITIONS_REQUIRED")
        for position in positions:
            require(nonempty(position.get("proposition")) and bool(position.get("evidence_ids"))
                    and set(position["evidence_ids"]) <= set(value["evidence_ids"]), "POSITION_SUPPORT_REQUIRED")
    if kind == "boundary":
        require(bool(value["record_refs"]), "BOUNDARY_THEME_REFERENCE_REQUIRED")
        require(value.get("basis_level") in {"explicitly_tested", "cross_study_suggested", "untested_hypothesis"}, "BOUNDARY_LEVEL_REQUIRED")
    if kind == "claim":
        require(value.get("claim_type") in CLAIM_TYPES, "INVALID_CLAIM_TYPE")
        require(value.get("generalization") in {"source_bounded", "beyond_sources"}, "GENERALIZATION_SCOPE_REQUIRED")
        require(isinstance(value.get("evidence_decisions"), dict), "COUNTEREVIDENCE_LEDGER_REQUIRED")
        for decision in value["evidence_decisions"].values():
            require(decision.get("relation") in RELATIONS | {"not_relevant"} and nonempty(decision.get("rationale")), "EVIDENCE_DISPOSITION_REQUIRED")
    if kind == "link":
        require(value.get("relation") in RELATIONS and value.get("directness") in DIRECTNESS, "INVALID_LINK_RELATION_OR_DIRECTNESS")
        require(value["evidence_ids"] == [value["evidence_id"]], "LINK_MUST_BIND_ONE_EVIDENCE")
    if kind == "gap":
        require(value.get("gap_type") in GAP_TYPES, "INVALID_GAP_TYPE")
        require(value.get("scope") == "reviewed_corpus", "FIELD_WIDE_NOVELTY_NOT_ESTABLISHED")
        require(value["derivation"].startswith("Within the reviewed and retrieved corpus"), "CORPUS_BOUNDED_WORDING_REQUIRED")
        require(value.get("basis_kind") in {"evidence_disagreement", "documented_design_limit", "conceptual_analysis"}, "COVERAGE_SHORTFALL_ALONE_IS_NOT_RESEARCH_GAP")
        require(bool(value["record_refs"]), "GAP_CLAIM_REFERENCES_REQUIRED")


def validate_semantics(value):
    require(value.get("outcome") in {"supported", "uncertain", "unsupported"}, "SEMANTIC_OUTCOME_REQUIRED")
    require(nonempty(value.get("reviewer")) and nonempty(value.get("rationale")), "SEMANTIC_REVIEWER_AND_RATIONALE_REQUIRED")
    require(set(value.get("checks", {})) == set(CHECKS), "ALL_SEMANTIC_CHECKS_REQUIRED")
    for check in value["checks"].values():
        require(check.get("status") in {"pass", "fail", "not_applicable", "uncertain"} and nonempty(check.get("reason")), "SEMANTIC_CHECK_REASON_REQUIRED")
    if value["outcome"] == "supported":
        require(all(c["status"] in {"pass", "not_applicable"} for c in value["checks"].values()), "UNRESOLVED_SEMANTIC_CHECKS")
    require(isinstance(value.get("evidence_checks"), dict), "SEMANTIC_EVIDENCE_CHECKS_REQUIRED")


def schema():
    return {"contract_version": VERSION, "record_text_fields": TEXT_FIELDS, "phases": PHASE,
            "relations": sorted(RELATIONS), "directness": sorted(DIRECTNESS), "claim_types": sorted(CLAIM_TYPES),
            "gap_types": sorted(GAP_TYPES), "semantic_checks": CHECKS, "review_actions": sorted(ACTIONS),
            "common_fields": ["research_question", "evidence_ids", "record_refs", "uncertainty", "generator", "example_data"],
            "notice": "Structural checks cannot establish semantic entailment. Model assessments are not human approvals."}
