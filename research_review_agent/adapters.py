from __future__ import annotations

from dataclasses import asdict, dataclass


class AdapterUnavailableError(RuntimeError):
    """Raised when a requested external integration is not packaged with the kit."""


@dataclass(frozen=True)
class Capability:
    name: str
    status: str
    provided_by: str
    note: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_CAPABILITIES = (
    Capability("evidence_bounded_writing", "available", "packaged_procedures_and_cli", "Explicit Codex/researcher outlines, briefs and draft spans with current-source validation, versioned reviews and reverse impact. Formal work requires reviewed upstream evidence; PDF-backed validation needs the pdf extra."),
    Capability("independent_claim_audit", "available", "packaged_procedures_and_cli", "Separate structural checks and source-manifest/semantic-audit records; caller executes actual independent reasoning. No automatic entailment, authenticated identity or model self-sign-off."),
    Capability("local_bibliography_reconciliation", "available", "packaged_cli", "Saved registry/BibTeX/citation/document reconciliation and cited-only export. No live metadata verification or CSL/DOCX engine."),
    Capability("evidence_grounded_synthesis", "available", "packaged_procedures_and_cli", "Versioned corpus, four maps, boundaries, claims/links, bounded gaps, semantic assessment records and declared-human review; no automatic entailment, novelty or independent accuracy validation."),
    Capability("source_grounded_reading", "available", "packaged_procedures_and_cli", "Codex/researcher supplies interpretations; CLI validates versioned notes, anchors, evidence, review and coverage. No automatic semantic correctness or independent human validation."),
    Capability("literature_screening", "available", "packaged_procedures_and_cli", "Three evidence stages, provisional proposals, declared-human review, scope/version accounting and Gate 1. No automatic scholarly judgment or authenticated identity."),
    Capability("citation_snowballing", "available_with_network", "packaged_citation_adapters", "Crossref backward, OpenAlex forward, OpenCitations backward/forward. Bounded runs, raw replay, explicit seed/stop review. Related recommendations not implemented."),
    Capability("project_cli", "available", "project", "Initialization, validation, gates, state, and recovery are self-contained."),
    Capability("protocol_drafting", "available", "registered_procedure_and_cli", "The Phase 0 procedure guides research design; the CLI persists and validates drafts."),
    Capability("scholarly_discovery", "available_with_network", "packaged_openalex_and_crossref_adapters", "OpenAlex and Crossref metadata adapters are bundled; live results still require network and provider policy compliance."),
    Capability("paper_acquisition", "available_with_optional_parser", "packaged_document_tools", "Authorized local import and public publisher PDF links; install the pdf extra for integrity validation. No subscription access."),
    Capability("bibliography_enrichment", "available_with_network", "packaged_crossref_adapter", "Crossref DOI resolution and metadata reconciliation are bundled; this does not acquire or verify full text."),
    Capability("full_text_pdf_reading", "external_tool_required", "external_or_codex_tool", "Requires an accessible PDF reader/tool and lawful local full text."),
    Capability("pdf_page_parsing", "available_with_optional_parser", "packaged_document_tools", "Install the pdf extra. Text extraction is not scientific reading; no OCR or robust table interpretation."),
)


def capability_report() -> list[dict[str, str]]:
    from .documents.parser import parser_version
    from .documents.contracts import DocumentError
    records = [capability.to_dict() for capability in _CAPABILITIES]
    for record in records:
        if record["status"] == "available_with_optional_parser":
            try:
                record["parser_version"] = parser_version()
                record["status"] = "available"
            except DocumentError:
                record["status"] = "optional_dependency_missing"
    return records


def require_adapter(name: str) -> None:
    capability = next((Capability(**{k: v for k, v in item.items() if k != "parser_version"}) for item in capability_report() if item["name"] == name), None)
    if capability is None:
        raise AdapterUnavailableError(f"UNKNOWN_ADAPTER: {name}")
    if capability.status not in {"available", "available_with_network"}:
        raise AdapterUnavailableError(
            f"ADAPTER_UNAVAILABLE: {name}; status={capability.status}; {capability.note}"
        )
