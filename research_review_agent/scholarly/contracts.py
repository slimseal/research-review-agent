from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0.0"


class SerializableContract:
    """Small JSON-compatible contract base used by persisted adapter records."""

    contract_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchRequest(SerializableContract):
    project_id: str
    protocol_version: str
    search_strategy_version: str
    provider: str
    exact_query: str
    filters: dict[str, str] = field(default_factory=dict)
    per_page: int = 25
    max_pages: int = 1
    cursor: str | None = None
    sort: str | None = None
    mode: str = "workflow"
    max_requests: int | None = None
    max_attempts: int = 1
    contract_version: str = CONTRACT_VERSION


@dataclass
class SearchRun(SerializableContract):
    search_run_id: str
    project_id: str
    protocol_version: str
    search_strategy_version: str
    provider: str
    exact_query: str
    filters: dict[str, str]
    execution_timestamp: str
    retrieval_status: str
    raw_response_path: list[str] = field(default_factory=list)
    raw_response_sha256: list[str] = field(default_factory=list)
    provider_record_ids: list[str] = field(default_factory=list)
    retrieved_count: int = 0
    pagination_cursor: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    error_history: list[dict[str, Any]] = field(default_factory=list)
    coverage_limitations: list[str] = field(default_factory=list)
    parsed_count: int = 0
    duplicate_count: int = 0
    ambiguous_identity_count: int = 0
    unique_canonical_count: int = 0
    rejected_count: int = 0
    pages_completed: int = 0
    completed_at: str | None = None
    replay_of: str | None = None
    request_configuration: dict[str, Any] = field(default_factory=dict)
    http_attempts: int = 0
    http_receipt_path: str | None = None
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class ProviderResponse(SerializableContract):
    search_run_id: str
    provider: str
    page_number: int
    request_url_redacted: str
    request_parameters: dict[str, Any]
    http_status: int
    response_headers: dict[str, str]
    retrieved_at: str
    raw_response_path: str
    raw_response_sha256: str
    record_count: int
    next_cursor: str | None
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class PaperCandidate(SerializableContract):
    provider: str
    provider_record_id: str
    search_run_id: str
    retrieved_at: str
    raw_response_path: str
    raw_record_index: int
    title: str
    authors: list[str]
    publication_year: int | None
    source_title: str | None
    doi: str | None
    landing_page_url: str | None
    work_type: str | None
    version_type: str
    abstract: str | None
    source_ids: dict[str, str] = field(default_factory=dict)
    relations: dict[str, list[str]] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION


@dataclass
class PaperRecord(SerializableContract):
    paper_id: str
    title: str
    authors: list[str]
    publication_year: int | None
    source_title: str | None
    doi: str | None
    landing_page_url: str | None
    work_type: str | None
    version_type: str
    provider_ids: dict[str, list[str]] = field(default_factory=dict)
    search_run_ids: list[str] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    verification_status: str = "single_provider"
    conflict_notes: list[str] = field(default_factory=list)
    related_versions: list[str] = field(default_factory=list)
    first_registered_at: str = ""
    last_seen_at: str = ""
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class MetadataResolution(SerializableContract):
    resolution_id: str
    paper_id: str
    candidate_provider: str
    candidate_provider_record_id: str
    field_decisions: dict[str, dict[str, Any]]
    conflict_fields: list[str]
    verification_status: str
    resolved_at: str
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class IdentityMatch(SerializableContract):
    candidate_provider: str
    candidate_provider_record_id: str
    search_run_id: str
    matched_paper_id: str | None
    method: str
    status: str
    confidence: str
    candidate_fingerprint: str | None
    competing_paper_ids: list[str]
    notes: list[str]
    decided_at: str
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class ProviderFailure(SerializableContract):
    code: str
    provider: str
    message: str
    occurred_at: str
    retryable: bool
    attempt: int
    http_status: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION
