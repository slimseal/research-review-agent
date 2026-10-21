from __future__ import annotations

from dataclasses import asdict, dataclass, field
from types import UnionType
from typing import get_args, get_origin, get_type_hints

CONTRACT_VERSION = "1.0.0"
VERSION_KINDS = {"version_of_record", "accepted_manuscript", "preprint", "supplementary", "unknown"}
ANCHOR_STATUSES = {"machine_located", "human_confirmed", "ambiguous", "unresolved", "stale"}


class DocumentError(ValueError):
    def __init__(self, code: str, message: str, http_status: int | None = None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.http_status = code, message, http_status

    def to_dict(self):
        return {"code": self.code, "message": self.message, "http_status": self.http_status}


@dataclass
class Contract:
    def to_dict(self):
        return {"contract_version": CONTRACT_VERSION, **asdict(self)}


@dataclass
class DocumentVersion(Contract):
    document_id: str
    paper_id: str | None
    document_type: str
    version_kind: str
    source_url: str | None
    acquisition_method: str
    provider: str
    acquired_at: str
    access_basis: str
    license_status: str
    license_url: str | None
    redistribution_permission: str
    local_path: str
    sha256: str
    file_size: int
    mime_type: str
    pdf_page_count: int
    parsing_status: str = "not_parsed"
    parser_version: str | None = None
    verification_status: str = "integrity_checked_identity_not_independently_verified"
    identity_status: str = "registered_paper"
    related_document_ids: list[str] = field(default_factory=list)
    attempt_ids: list[str] = field(default_factory=list)
    parse_refs: list[dict] = field(default_factory=list)


@dataclass
class AcquisitionAttempt(Contract):
    attempt_id: str
    paper_id: str | None
    provider: str
    candidate_url: str | None
    timestamp: str
    http_status: int | None = None
    result_status: str = "started"
    failure_code: str | None = None
    access_decision: str = "unassessed"
    downloaded_bytes: int | None = None
    checksum: str | None = None
    warnings: list[str] = field(default_factory=list)
    authorization: dict = field(default_factory=dict)
    final_url: str | None = None
    redirects: list[str] = field(default_factory=list)
    document_id: str | None = None
    message: str | None = None


@dataclass
class ParsedDocument(Contract):
    document_id: str
    document_sha256: str
    parser_name: str
    parser_version: str
    parsed_at: str
    page_count: int
    pages: list[dict]
    status: str
    reading_order_confidence: str = "unverified"
    sections: list[dict] = field(default_factory=list)
    figure_table_indicators: list[dict] = field(default_factory=list)
    processing_limitations: list[str] = field(default_factory=lambda: [
        "No OCR, table-cell extraction, equation interpretation or scientific reading.",
        "Reading order and visitor coordinates require visual review, including multi-column pages.",
        "Printed page numbers and semantic paragraph boundaries are not inferred.",
    ])


@dataclass
class SourceAnchor(Contract):
    anchor_id: str
    paper_id: str | None
    document_id: str
    document_sha256: str
    parser_version: str
    parse_path: str
    parse_sha256: str
    locator_type: str
    pdf_page: int | None
    quote_fingerprint: str
    verification_status: str
    text_span: dict | None = None
    printed_page: str | None = None
    section: str | None = None
    paragraph_or_block: str | None = None
    figure_table_identifier: str | None = None
    coordinate_reference: dict | None = None
    matches: list[dict] = field(default_factory=list)
    confirmation: dict | None = None


CONTRACTS = {c.__name__: c for c in (DocumentVersion, AcquisitionAttempt, ParsedDocument, SourceAnchor)}


def _type_schema(annotation):
    origin = get_origin(annotation)
    if origin is UnionType:
        return {"anyOf": [_type_schema(a) for a in get_args(annotation)]}
    if origin is list:
        return {"type": "array", "items": _type_schema(get_args(annotation)[0])}
    return {"type": {str: "string", int: "integer", bool: "boolean", dict: "object", list: "array", type(None): "null"}.get(annotation, "object")}


def document_schema():
    definitions = {}
    for name, contract in CONTRACTS.items():
        properties = {key: _type_schema(value) for key, value in get_type_hints(contract).items()}
        properties["contract_version"] = {"const": CONTRACT_VERSION}
        definitions[name] = {"type": "object", "required": list(properties), "properties": properties}
    definitions["DocumentVersion"]["properties"]["version_kind"] = {"enum": sorted(VERSION_KINDS)}
    definitions["DocumentVersion"]["properties"]["license_status"] = {"enum": ["unknown", "open_license_asserted", "restricted"]}
    definitions["DocumentVersion"]["properties"]["redistribution_permission"] = {"enum": ["unknown", "not_permitted", "permitted_with_conditions"]}
    definitions["SourceAnchor"]["properties"]["verification_status"] = {"enum": sorted(ANCHOR_STATUSES)}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": definitions}


def validate_contract(name: str, value: dict) -> None:
    def matches(schema, item):
        if "anyOf" in schema:
            return any(matches(s, item) for s in schema["anyOf"])
        if "enum" in schema:
            return item in schema["enum"]
        if "const" in schema:
            return item == schema["const"]
        expected = schema["type"]
        classes = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list, "null": type(None)}
        if not isinstance(item, classes[expected]) or (expected == "integer" and isinstance(item, bool)):
            return False
        return expected != "array" or "items" not in schema or all(matches(schema["items"], entry) for entry in item)
    definition = document_schema()["$defs"][name]
    if any(key not in value or not matches(schema, value[key]) for key, schema in definition["properties"].items()):
        raise DocumentError("INVALID_DOCUMENT_CONTRACT", f"{name} is missing required fields or has invalid field types/statuses.")
