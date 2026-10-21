from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

VERSION = "1.0.0"
SUPPORTED = {"crossref": {"backward"}, "openalex": {"forward"}, "opencitations": {"backward", "forward"}}
COVERAGE = "Provider-reported relationships only; missing links do not establish absence. No exhaustive coverage or evidence-quality claim."


@dataclass
class SeedSet:
    seed_set_id: str
    seed_set_version: int
    protocol_version: str
    protocol_sha256: str
    selected_paper_ids: list[str]
    selection_reason: dict[str, str]
    selected_by: str
    selection_timestamp: str
    approval_status: str
    expansion_depth_limit: int
    provider_plan: list[dict[str, str]]
    max_requests: int
    max_candidates: int
    identity_snapshot: dict[str, Any]
    approval: dict[str, str] = field(default_factory=dict)
    contract_version: str = VERSION


@dataclass
class CitationExpansionRun:
    expansion_run_id: str
    project_id: str
    protocol_version: str
    seed_set_version: int
    expansion_round: int
    direction: str
    provider: str
    query_parameters: dict[str, Any]
    execution_timestamp: str
    status: str = "in_progress"
    raw_response_reference: list[str] = field(default_factory=list)
    raw_response_sha256: list[str] = field(default_factory=list)
    pagination_cursor: str | None = None
    discovered_count: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    duplicate_count: int = 0
    unique_new_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    coverage_limitations: list[str] = field(default_factory=lambda: [COVERAGE])
    contract_version: str = VERSION


@dataclass
class ExpansionCandidate:
    candidate_id: str
    expansion_run_id: str
    source_seed: str
    citation_direction: str
    expansion_round: int
    provider_identifiers: dict[str, Any]
    bibliographic_metadata: dict[str, Any]
    identity_resolution_status: str
    duplicate_status: str
    paper_id: str | None
    raw_reference: Any
    raw_response_pointer: dict[str, Any]
    relevance_status: str = "not_assessed"
    screening_status: str = "not_screened"
    contract_version: str = VERSION


@dataclass
class CitationEdge:
    citation_edge_id: str
    citing_identity: str
    cited_identity: str
    seed_paper_id: str
    direction_relative_to_seed: str
    expansion_round: int
    source_provider: str
    provider_record_id: str
    raw_response_pointer: dict[str, Any]
    retrieval_timestamp: str
    relation_status: str
    identity_verification_status: str
    verification_basis: str
    provenance: list[dict[str, Any]] = field(default_factory=list)
    contract_version: str = VERSION


def record(value):
    return asdict(value)
