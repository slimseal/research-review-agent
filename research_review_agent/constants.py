from __future__ import annotations

from .registry import registry_phase_artifacts, registry_phase_names

PHASES = registry_phase_names()

PROJECT_DIRECTORIES = [
    "00_protocol",
    "01_search",
    "02_discovery",
    "02_discovery/search_runs",
    "02_discovery/raw/openalex",
    "02_discovery/raw/crossref",
    "03_library/papers",
    "04_screening",
    "05_reading_notes",
    "06_evidence",
    "07_synthesis",
    "08_argument",
    "09_writing",
    "10_audit",
    ".review/backups",
]

COMMON_CSV_FIELDS = {
    "keyword_matrix": [
        "concept_id", "label", "core_term", "synonyms", "scope_note", "source"
    ],
    "search_log": [
        "search_id", "database", "query", "filters", "searched_at", "result_count",
        "status", "failure_reason", "example_data"
    ],
    "discovery": [
        "paper_id", "title", "authors", "year", "journal", "doi", "paper_type",
        "theme", "why_relevant", "discovery_source", "source_identifier", "abstract_basis",
        "example_data", "extension_json"
    ],
    "paper_registry": [
        "paper_id", "title", "authors", "year", "journal", "doi", "url", "pdf_path",
        "paper_type", "retrieval_source", "retrieval_date", "fulltext_available", "license",
        "sha256", "example_data", "extension_json"
    ],
    "screening": [
        "paper_id", "stage", "criteria_version", "decision", "exclusion_reason",
        "decision_basis", "evidence_available", "reviewer", "timestamp", "review_role",
        "priority", "example_data", "extension_json"
    ],
    "claim": [
        "claim_id", "claim", "supporting_evidence", "contradictory_evidence",
        "evidence_type", "evidence_strength", "boundary_conditions", "allowed_wording",
        "prohibited_overclaim", "confidence", "verdict", "example_data", "extension_json"
    ],
}

LEGACY_EVIDENCE_FIELDS = [
        "evidence_id", "paper_id", "research_question", "theme", "subtheme",
        "study_context", "population", "sample_size", "study_design", "method",
        "predictor_or_exposure", "outcome", "finding", "effect_direction", "effect_size",
        "uncertainty", "mediator", "moderator", "authors_interpretation",
        "alternative_explanation", "limitations", "supports_claim", "contradicts_claim",
        "evidence_strength", "evidence_locator", "source_basis", "example_data",
        "extension_json"
]

UNIVERSAL_EVIDENCE_FIELDS = [
    "evidence_id", "paper_id", "research_question", "source_basis", "research_context",
    "evidence_type", "research_types", "finding_argument_proposition", "evidence_locator",
    "limitations_uncertainty", "verification_status", "example_data", "extension_json",
]

CSV_FIELDS_V1 = {**COMMON_CSV_FIELDS, "evidence": LEGACY_EVIDENCE_FIELDS}
CSV_FIELDS_V2 = {**COMMON_CSV_FIELDS, "evidence": UNIVERSAL_EVIDENCE_FIELDS}

# Current writers use v2. Validators select v1 or v2 from each project's
# protocol schema_version so existing workspaces remain readable.
CSV_FIELDS = CSV_FIELDS_V2


def csv_fields_for_version(schema_version: str) -> dict[str, list[str]]:
    return CSV_FIELDS_V1 if str(schema_version).startswith("1.") else CSV_FIELDS_V2

INITIAL_CSV_FILES = {
    "01_search/KEYWORD_MATRIX.csv": "keyword_matrix",
    "01_search/SEARCH_LOG.csv": "search_log",
    "02_discovery/SEED_PAPERS.csv": "discovery",
    "02_discovery/DISCOVERY_MASTER.csv": "discovery",
    "02_discovery/BACKWARD_CITATIONS.csv": "discovery",
    "02_discovery/FORWARD_CITATIONS.csv": "discovery",
    "02_discovery/RELATED_PAPERS.csv": "discovery",
    "03_library/PAPER_REGISTRY.csv": "paper_registry",
    "04_screening/SCREENING_MASTER.csv": "screening",
    "04_screening/EXCLUSION_LOG.csv": "screening",
    "06_evidence/EVIDENCE_MATRIX.csv": "evidence",
    "08_argument/CLAIM_MAP.csv": "claim",
}

PHASE_ARTIFACTS = registry_phase_artifacts()

ALLOWED_PHASE_STATUSES = {"pending", "in_progress", "blocked", "completed"}
SCREENING_STAGES = {"title", "abstract", "full_text"}
SCREENING_DECISIONS = {"include", "exclude", "uncertain"}
SOURCE_BASES = {"full_text", "supplement", "abstract_only", "metadata_only"}
EVIDENCE_STRENGTHS = {"strong", "moderate", "weak", "insufficient", "not_assessed"}
VERIFICATION_STATUSES = {"unverified", "verified", "partially_verified", "contradicted", "not_auditable"}
RESEARCH_TYPES = {
    "quantitative_empirical",
    "qualitative_empirical",
    "historical_documentary",
    "theoretical_conceptual",
    "archaeological_material",
}

