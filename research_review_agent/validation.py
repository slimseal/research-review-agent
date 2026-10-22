from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .constants import (
    EVIDENCE_STRENGTHS,
    INITIAL_CSV_FILES,
    PHASE_ARTIFACTS,
    RESEARCH_TYPES,
    SCREENING_DECISIONS,
    SCREENING_STAGES,
    SOURCE_BASES,
    VERIFICATION_STATUSES,
    csv_fields_for_version,
)
from .registry import validate_workflow_registry


@dataclass
class Issue:
    severity: str
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _csv_issues(path: Path, expected: list[str]) -> list[Issue]:
    if not path.exists():
        return [Issue("error", "missing_file", str(path), "Required CSV file is missing.")]
    try:
        headers, _ = _read_csv(path)
    except (OSError, csv.Error) as exc:
        return [Issue("error", "invalid_csv", str(path), str(exc))]
    missing = [field for field in expected if field not in headers]
    return [Issue("error", "missing_columns", str(path), f"Missing columns: {', '.join(missing)}")] if missing else []


def _load_protocol(project_root: Path) -> dict[str, Any]:
    return json.loads((project_root / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))


def _project_csv_fields(project_root: Path) -> dict[str, list[str]]:
    try:
        schema_version = _load_protocol(project_root).get("schema_version", "1.0.0")
    except (OSError, json.JSONDecodeError):
        schema_version = "1.0.0"
    return csv_fields_for_version(schema_version)


def _parse_json_object(raw: str, path: Path, row_number: int, field: str) -> tuple[dict[str, Any] | None, list[Issue]]:
    if not raw.strip():
        return {}, []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [Issue("error", "invalid_json_field", str(path), f"Row {row_number} {field}: {exc.msg}")]
    if not isinstance(value, dict):
        return None, [Issue("error", "invalid_json_field", str(path), f"Row {row_number} {field} must be a JSON object.")]
    return value, []


def _extension_fields(project_root: Path) -> list[dict[str, Any]]:
    path = project_root / "00_protocol/DOMAIN_EXTENSION_SCHEMA.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("fields", [])


def validate_registry(project_root: Path, require_rows: bool = False, allow_example_data: bool = False) -> list[Issue]:
    path = project_root / "03_library/PAPER_REGISTRY.csv"
    issues = _csv_issues(path, _project_csv_fields(project_root)["paper_registry"])
    if issues:
        return issues
    _, rows = _read_csv(path)
    if require_rows and not rows:
        issues.append(Issue("error", "empty_registry", str(path), "Paper registry must contain at least one record."))
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        paper_id = row["paper_id"].strip()
        if not paper_id or paper_id in seen:
            issues.append(Issue("error", "invalid_paper_id", str(path), f"Row {index}: missing or duplicate paper_id."))
        seen.add(paper_id)
        doi = row["doi"].strip()
        if doi and not re.fullmatch(r"10\.\d{4,9}/\S+", doi, flags=re.IGNORECASE):
            issues.append(Issue("error", "invalid_doi", str(path), f"Row {index}: {doi}"))
        if row["fulltext_available"].strip().lower() in {"true", "1", "yes"} and not row["pdf_path"].strip():
            issues.append(Issue("error", "missing_pdf_path", str(path), f"Row {index} claims full text without a path."))
        if row["example_data"].strip().lower() in {"true", "1", "yes"} and not allow_example_data:
            issues.append(Issue("error", "example_data_disallowed", str(path), f"Row {index} is demonstration data."))
    return issues


def validate_discovery_provenance(project_root: Path, require_runs: bool = False) -> list[Issue]:
    path = project_root / "02_discovery/SEARCH_RUNS.jsonl"
    issues: list[Issue] = []
    if not path.exists():
        if require_runs:
            issues.append(Issue("error", "missing_search_runs", str(path), "At least one recorded SearchRun is required."))
        return issues
    required_fields = {
        "search_run_id", "project_id", "protocol_version", "search_strategy_version", "provider",
        "exact_query", "filters", "execution_timestamp", "retrieval_status", "raw_response_path",
        "raw_response_sha256", "provider_record_ids", "retrieved_count", "pagination_cursor",
        "warnings", "errors", "coverage_limitations",
    }
    run_count = 0
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [Issue("error", "invalid_search_run_log", str(path), str(exc))]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        run_count += 1
        try:
            run = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(Issue("error", "invalid_search_run_json", str(path), f"Line {line_number}: {exc.msg}"))
            continue
        missing = required_fields - set(run)
        if missing:
            issues.append(Issue("error", "missing_search_run_fields", str(path), f"Line {line_number}: {sorted(missing)}"))
            continue
        run_id = str(run["search_run_id"])
        if run_id in seen:
            issues.append(Issue("error", "duplicate_search_run_id", str(path), run_id))
        seen.add(run_id)
        raw_paths = run["raw_response_path"]
        hashes = run["raw_response_sha256"]
        if not isinstance(raw_paths, list) or not isinstance(hashes, list) or len(raw_paths) != len(hashes):
            issues.append(Issue("error", "invalid_raw_response_index", str(path), f"Run {run_id} paths/checksums do not align."))
            continue
        for relative, expected in zip(raw_paths, hashes):
            raw_path = (project_root / str(relative)).resolve()
            project_resolved = project_root.resolve()
            if project_resolved not in raw_path.parents:
                issues.append(Issue("error", "unsafe_raw_response_path", str(path), str(relative)))
                continue
            if not raw_path.exists():
                issues.append(Issue("error", "missing_raw_response", str(raw_path), f"Referenced by {run_id}."))
                continue
            actual = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            if actual != expected:
                issues.append(Issue("error", "raw_response_checksum_mismatch", str(raw_path), f"Referenced by {run_id}."))
        if run["retrieval_status"] == "failed" and not run["errors"]:
            issues.append(Issue("error", "failed_run_without_error", str(path), run_id))
        if run["retrieval_status"] in {"complete", "complete_empty", "complete_with_limit", "replayed"} and run["errors"]:
            issues.append(Issue("error", "successful_run_with_errors", str(path), run_id))
        # Old runs without HTTP ledgers remain readable. New ledgers add checks,
        # never replace existing raw-response, Protocol or phase validation.
        receipt_dir = project_root / "02_discovery/http" / run_id
        if run.get("http_receipt_path"):
            receipt_path = (project_root / run["http_receipt_path"]).resolve()
            if project_root.resolve() not in receipt_path.parents:
                issues.append(Issue("error", "discovery_http_integrity", str(path), "Unsafe HTTP receipt path"))
                continue
            receipt_dir = receipt_path.parent
        receipt_file = receipt_dir / "budget.json"
        if receipt_file.exists():
            from .scholarly.request_budget import RecordedTransport
            try:
                receipt = json.loads(receipt_file.read_text())
                transport = RecordedTransport(receipt_dir, max_requests=receipt["max_requests"],
                                              max_attempts=receipt["max_attempts"])
                for error in transport.validate():
                    issues.append(Issue("error", "discovery_http_integrity", str(receipt_file), error))
                if run.get("http_attempts", 0) != transport.used:
                    issues.append(Issue("error", "discovery_http_count", str(receipt_file), run_id))
            except (ValueError, KeyError, OSError, TypeError) as exc:
                issues.append(Issue("error", "discovery_http_integrity", str(receipt_file), str(exc)))
    if require_runs and run_count == 0:
        issues.append(Issue("error", "empty_search_runs", str(path), "At least one recorded SearchRun is required."))
    return issues


def validate_screening(project_root: Path, require_rows: bool = False, allow_example_data: bool = False) -> list[Issue]:
    from .state import load_state
    if load_state(project_root).get("screening_data"):
        from .screening.pipeline import ScreeningPipeline
        pipeline = ScreeningPipeline(project_root)
        result = pipeline.gate(require_completed=False) if require_rows else pipeline.validate()
        messages = result.get("errors", []) + result.get("blockers", [])
        return [Issue("error", "screening_v1_invalid", "04_screening", m) for m in messages]
    path = project_root / "04_screening/SCREENING_MASTER.csv"
    issues = _csv_issues(path, _project_csv_fields(project_root)["screening"])
    if issues:
        return issues
    _, rows = _read_csv(path)
    if require_rows and not rows:
        issues.append(Issue("error", "empty_screening", str(path), "Screening must contain at least one decision."))
    for index, row in enumerate(rows, start=2):
        if row["stage"] not in SCREENING_STAGES:
            issues.append(Issue("error", "invalid_screening_stage", str(path), f"Row {index}: {row['stage']}"))
        if row["decision"] not in SCREENING_DECISIONS:
            issues.append(Issue("error", "invalid_screening_decision", str(path), f"Row {index}: {row['decision']}"))
        if row["decision"] == "exclude" and not row["exclusion_reason"].strip():
            issues.append(Issue("error", "missing_exclusion_reason", str(path), f"Row {index} excludes without a reason."))
        if row["example_data"].strip().lower() in {"true", "1", "yes"} and not allow_example_data:
            issues.append(Issue("error", "example_data_disallowed", str(path), f"Row {index} is demonstration data."))
    if require_rows:
        issues.append(Issue("error", "screening_versioned_review_required", str(path), "Legacy CSV remains readable, but cannot prove scope coverage, provenance or human approval. Reassess with versioned screening; old data is not migrated or overwritten automatically."))
    return issues


def _matches_declared_type(value: Any, declared: str) -> bool:
    if isinstance(value, str) and value in {"not_reported", "not_applicable", "uncertain", "not_reliably_extractable"}:
        return True
    if declared == "string":
        return isinstance(value, str)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "array":
        return isinstance(value, list)
    if declared == "object":
        return isinstance(value, dict)
    return False


def validate_evidence(project_root: Path, require_rows: bool = False, allow_example_data: bool = False) -> list[Issue]:
    path = project_root / "06_evidence/EVIDENCE_MATRIX.csv"
    protocol = _load_protocol(project_root)
    schema_version = protocol.get("schema_version", "1.0.0")
    is_legacy = str(schema_version).startswith("1.")
    issues = _csv_issues(path, _project_csv_fields(project_root)["evidence"])
    if issues:
        return issues
    _, rows = _read_csv(path)
    if require_rows and not rows:
        issues.append(Issue("error", "empty_evidence", str(path), "Evidence matrix must contain at least one evidence row."))
    registry_path = project_root / "03_library/PAPER_REGISTRY.csv"
    registry_ids: set[str] = set()
    if registry_path.exists():
        _, registry_rows = _read_csv(registry_path)
        registry_ids = {row["paper_id"] for row in registry_rows if row.get("paper_id")}
    definitions = _extension_fields(project_root)
    definitions_by_name = {field["name"]: field for field in definitions}
    allowed_extension_names = {field["name"] for field in definitions}
    selected_research_types = set(protocol.get("research_types", []))
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        evidence_id = row["evidence_id"].strip()
        if not evidence_id or evidence_id in seen:
            issues.append(Issue("error", "invalid_evidence_id", str(path), f"Row {index}: missing or duplicate evidence_id."))
        seen.add(evidence_id)
        if row["paper_id"] not in registry_ids:
            issues.append(Issue("error", "unknown_paper_id", str(path), f"Row {index}: {row['paper_id']} is absent from the registry."))
        if row["source_basis"] not in SOURCE_BASES:
            issues.append(Issue("error", "invalid_source_basis", str(path), f"Row {index}: {row['source_basis']}"))
        if is_legacy:
            if row["evidence_strength"] not in EVIDENCE_STRENGTHS:
                issues.append(Issue("error", "invalid_evidence_strength", str(path), f"Row {index}: {row['evidence_strength']}"))
            row_research_types: set[str] = set()
        else:
            if row["verification_status"] not in VERIFICATION_STATUSES:
                issues.append(Issue("error", "invalid_verification_status", str(path), f"Row {index}: {row['verification_status']}"))
            if not row["finding_argument_proposition"].strip():
                issues.append(Issue("error", "missing_evidence_proposition", str(path), f"Row {index} has no finding, argument, or proposition."))
            try:
                parsed_research_types = json.loads(row["research_types"])
                if not isinstance(parsed_research_types, list) or not parsed_research_types or not all(isinstance(item, str) for item in parsed_research_types):
                    raise ValueError
                row_research_types = set(parsed_research_types)
            except (json.JSONDecodeError, ValueError, TypeError):
                row_research_types = set()
                issues.append(Issue("error", "invalid_evidence_research_types", str(path), f"Row {index} research_types must be a non-empty JSON string array."))
            unknown_research_types = row_research_types - RESEARCH_TYPES
            if unknown_research_types:
                issues.append(Issue("error", "unknown_research_type", str(path), f"Row {index}: {sorted(unknown_research_types)}"))
            unselected_research_types = row_research_types - selected_research_types
            if unselected_research_types:
                issues.append(Issue("error", "evidence_research_type_not_selected", str(path), f"Row {index}: {sorted(unselected_research_types)}"))
        is_example = row["example_data"].strip().lower() in {"true", "1", "yes"}
        if is_example and not allow_example_data:
            issues.append(Issue("error", "example_data_disallowed", str(path), f"Row {index} is demonstration data."))
        try:
            locators = json.loads(row["evidence_locator"])
            if row["source_basis"] in {"full_text", "supplement"}:
                if not isinstance(locators, list) or not locators or not all(isinstance(item, dict) for item in locators):
                    raise ValueError
                locator_keys = (
                    "pdf_page", "printed_page", "section", "figure", "table",
                    "archive_reference", "catalogue_reference", "object_reference",
                )
                if not all(any(item.get(key) not in (None, "") for key in locator_keys) for item in locators):
                    raise ValueError
        except (json.JSONDecodeError, ValueError, TypeError):
            issues.append(Issue("error", "invalid_evidence_locator", str(path), f"Row {index} lacks a valid locator array."))
        extension, extension_issues = _parse_json_object(row["extension_json"], path, index, "extension_json")
        issues.extend(extension_issues)
        if extension is not None:
            required_extension_names = {
                field["name"]
                for field in definitions
                if field.get("required")
                and (
                    is_legacy
                    or not field.get("research_types")
                    or row_research_types.intersection(field.get("research_types", []))
                )
            }
            unknown = set(extension) - allowed_extension_names
            missing = required_extension_names - set(extension)
            if unknown:
                issues.append(Issue("error", "unknown_extension_fields", str(path), f"Row {index}: {sorted(unknown)}"))
            if missing:
                issues.append(Issue("error", "missing_extension_fields", str(path), f"Row {index}: {sorted(missing)}"))
            for name, value in extension.items():
                definition = definitions_by_name.get(name)
                if definition and not is_legacy and definition.get("research_types") and not row_research_types.intersection(definition["research_types"]):
                    issues.append(
                        Issue(
                            "error",
                            "extension_not_applicable_to_evidence_type",
                            str(path),
                            f"Row {index}: {name} does not apply to {sorted(row_research_types)}.",
                        )
                    )
                if definition and not _matches_declared_type(value, definition["type"]):
                    issues.append(
                        Issue(
                            "error",
                            "extension_type_mismatch",
                            str(path),
                            f"Row {index}: {name} must be {definition['type']}.",
                        )
                    )
    return issues


def validate_claims(project_root: Path, require_rows: bool = False, allow_example_data: bool = False) -> list[Issue]:
    path = project_root / "08_argument/CLAIM_MAP.csv"
    issues = _csv_issues(path, _project_csv_fields(project_root)["claim"])
    if issues:
        return issues
    _, rows = _read_csv(path)
    if require_rows and not rows:
        issues.append(Issue("error", "empty_claim_map", str(path), "Claim map must contain at least one claim."))
    evidence_path = project_root / "06_evidence/EVIDENCE_MATRIX.csv"
    evidence_ids: set[str] = set()
    if evidence_path.exists():
        _, evidence_rows = _read_csv(evidence_path)
        evidence_ids = {row["evidence_id"] for row in evidence_rows if row.get("evidence_id")}
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        claim_id = row["claim_id"].strip()
        if not claim_id or claim_id in seen:
            issues.append(Issue("error", "invalid_claim_id", str(path), f"Row {index}: missing or duplicate claim_id."))
        seen.add(claim_id)
        refs = [item.strip() for item in re.split(r"[;|,]", row["supporting_evidence"]) if item.strip()]
        if not refs:
            issues.append(Issue("error", "claim_without_support", str(path), f"Row {index} has no supporting evidence IDs."))
        unknown = [item for item in refs if item not in evidence_ids]
        if unknown:
            issues.append(Issue("error", "unknown_evidence_id", str(path), f"Row {index}: {unknown}"))
        contradictory_refs = [item.strip() for item in re.split(r"[;|,]", row["contradictory_evidence"]) if item.strip()]
        unknown_contradictions = [item for item in contradictory_refs if item not in evidence_ids]
        if unknown_contradictions:
            issues.append(Issue("error", "unknown_evidence_id", str(path), f"Row {index} contradictory refs: {unknown_contradictions}"))
        is_example = row["example_data"].strip().lower() in {"true", "1", "yes"}
        if is_example and not allow_example_data:
            issues.append(Issue("error", "example_data_disallowed", str(path), f"Row {index} is demonstration data."))
    return issues


def _has_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"not yet specified", "not specified"}
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    return value is not None


def _substantive_protocol_issues(protocol: dict[str, Any], path: Path) -> list[Issue]:
    issues: list[Issue] = []
    required = {
        "scope": protocol.get("scope"),
        "subquestions": protocol.get("subquestions"),
        "concept_blocks": protocol.get("concept_blocks"),
        "screening.include": protocol.get("screening", {}).get("include"),
        "screening.exclude": protocol.get("screening", {}).get("exclude"),
    }
    if not str(protocol.get("schema_version", "1.0.0")).startswith("1."):
        strategies = protocol.get("search", {}).get("strategy_groups") or protocol.get("search", {}).get("strategy_templates")
        required.update(
            {
                "research_types": protocol.get("research_types"),
                "concept_definitions": protocol.get("concept_definitions"),
                "search.strategy_groups": strategies,
                "evidence_extensions": protocol.get("evidence_extensions"),
                "human_decisions": protocol.get("human_decisions"),
            }
        )
    for name, value in required.items():
        if not _has_content(value):
            issues.append(Issue("error", "protocol_not_substantive", str(path), f"Protocol section is not substantively populated: {name}"))
    return issues


def validate_protocol(project_root: Path, require_approved: bool = False, require_substantive: bool = False) -> list[Issue]:
    if (project_root / '.review/amendment-pending.json').exists():
        return [Issue('error', 'amendment_recovery_required', '.review', 'Run recover before reading an interrupted Protocol amendment.')]
    path = project_root / "00_protocol/PROTOCOL.json"
    if not path.exists():
        return [Issue("error", "missing_protocol", str(path), "Protocol is missing.")]
    try:
        protocol = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Issue("error", "invalid_protocol_json", str(path), exc.msg)]
    issues: list[Issue] = []
    for key in ("project_id", "research_question", "scope", "subquestions", "concept_blocks", "screening", "evidence_extensions"):
        if key not in protocol:
            issues.append(Issue("error", "missing_protocol_field", str(path), key))
    if require_approved and protocol.get("status") != "approved":
        issues.append(Issue("error", "protocol_not_approved", str(path), "Approve the protocol before continuing."))
    schema_version = str(protocol.get("schema_version", "1.0.0"))
    if not schema_version.startswith("1."):
        for key in ("research_types", "concept_definitions", "search", "human_decisions"):
            if key not in protocol:
                issues.append(Issue("error", "missing_protocol_field", str(path), key))
        unknown_types = set(protocol.get("research_types", [])) - RESEARCH_TYPES
        if unknown_types:
            issues.append(Issue("error", "unknown_research_type", str(path), f"Unknown research types: {sorted(unknown_types)}"))
    definitions = protocol.get("evidence_extensions", [])
    selected_types = set(protocol.get("research_types", []))
    names: set[str] = set()
    for index, field in enumerate(definitions):
        missing = {"name", "label", "description", "type", "required"} - set(field)
        if missing:
            issues.append(Issue("error", "invalid_extension_definition", str(path), f"Extension {index} missing: {sorted(missing)}"))
            continue
        if field["name"] in names:
            issues.append(Issue("error", "duplicate_extension_field", str(path), field["name"]))
        names.add(field["name"])
        applicable = set(field.get("research_types", []))
        if applicable - RESEARCH_TYPES:
            issues.append(Issue("error", "unknown_research_type", str(path), f"Extension {field['name']}: {sorted(applicable - RESEARCH_TYPES)}"))
        if applicable and not applicable.issubset(selected_types):
            issues.append(
                Issue(
                    "error",
                    "extension_research_type_not_selected",
                    str(path),
                    f"Extension {field['name']} applies to unselected research types: {sorted(applicable - selected_types)}",
                )
            )
    if require_substantive:
        issues.extend(_substantive_protocol_issues(protocol, path))
    return issues


def protocol_status(project_root: Path) -> dict[str, Any]:
    schema_issues = validate_protocol(project_root)
    substantive_issues = validate_protocol(project_root, require_substantive=True)
    protocol = _load_protocol(project_root)
    substantive_errors = [item for item in substantive_issues if item.code == "protocol_not_substantive"]
    schema_errors = [item for item in schema_issues if item.severity == "error"]
    return {
        "schema_valid": not schema_errors,
        "substantively_populated": not schema_errors and not substantive_errors,
        "pending_human_review": protocol.get("status") == "draft" and not schema_errors and not substantive_errors,
        "approved": protocol.get("status") == "approved",
        "protocol_status": protocol.get("status"),
        "issues": [item.to_dict() for item in substantive_issues],
    }


def validate_phase(project_root: Path, phase: int, allow_example_data: bool = False) -> list[Issue]:
    issues: list[Issue] = []
    for relative in PHASE_ARTIFACTS[phase]:
        path = project_root / relative
        if not path.exists():
            issues.append(Issue("error", "missing_phase_artifact", str(path), f"Required for Phase {phase}."))
        elif path.is_file() and path.stat().st_size == 0 and relative != "03_library/references.bib":
            issues.append(Issue("error", "empty_phase_artifact", str(path), f"Required for Phase {phase}."))
    if phase == 0:
        issues.extend(validate_protocol(project_root, require_approved=True))
    elif phase == 3:
        search_log_path = project_root / "01_search/SEARCH_LOG.csv"
        if search_log_path.exists():
            _, search_rows = _read_csv(search_log_path)
            if not search_rows:
                issues.append(Issue("error", "empty_search_log", str(search_log_path), "Phase 3 requires executed or explicitly failed search attempts."))
            from .scholarly.access import SEARCH_PROVIDERS
            official_rows = [row for row in search_rows if row.get("database") in SEARCH_PROVIDERS]
            if official_rows:
                issues.extend(validate_discovery_provenance(project_root, require_runs=True))
    elif phase == 4:
        from .citations.pipeline import CitationPipeline
        try:
            result = CitationPipeline(project_root).completion()
            issues.extend(Issue("error", "citation_phase4_incomplete", str(project_root / "02_discovery"), message) for message in result["issues"])
        except (ValueError, OSError, KeyError, RuntimeError) as exc:
            issues.append(Issue("error", "citation_phase4_incomplete", str(project_root / "02_discovery"), str(exc)))
    elif phase == 6:
        issues.extend(validate_screening(project_root, require_rows=True, allow_example_data=allow_example_data))
    elif phase == 5:
        issues.extend(validate_registry(project_root, require_rows=True, allow_example_data=allow_example_data))
        # Acquisition does not itself complete Phase 5: require an explicit per-source review.
        review_path = project_root / "03_library/ACQUISITION_REVIEW.json"
        try:
            review = json.loads(review_path.read_text(encoding="utf-8"))
            _, records = _read_csv(project_root / "03_library/PAPER_REGISTRY.csv")
            if not review.get("reviewed_by") or not review.get("reviewed_at"):
                raise ValueError("Named acquisition review and date are required.")
            for record in records:
                disposition = review.get("papers", {}).get(record["paper_id"], {})
                if disposition.get("status") not in {"acquired", "unavailable", "manual_access_required", "pending_screening"} or not disposition.get("basis"):
                    raise ValueError("Every registered paper needs an explicit access disposition and basis.")
                if disposition["status"] == "acquired":
                    from .documents.pipeline import DocumentPipeline
                    pipeline = DocumentPipeline(project_root)
                    data = pipeline.store.load()
                    document, _ = pipeline._document_file(data, disposition.get("document_id"))
                    if document["paper_id"] != record["paper_id"]:
                        raise ValueError("Acquisition review refers to a different paper identity.")
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues.append(Issue("error", "acquisition_review_required", str(review_path), str(error)))
        bibliography = project_root / "03_library/references.bib"
        if bibliography.exists() and not bibliography.read_text(encoding="utf-8").strip():
            issues.append(Issue("error", "empty_bibliography", str(bibliography), "Registered papers require bibliography records."))
    elif phase == 7:
        issues.extend(validate_reading_completion(project_root, 7))
    elif phase == 8:
        issues.extend(validate_evidence(project_root, require_rows=False, allow_example_data=allow_example_data))
        issues.extend(validate_reading_completion(project_root, 8))
    elif phase in {9, 10, 11, 12}:
        issues.extend(validate_synthesis_completion(project_root, phase))
        if phase == 11:
            issues.extend(validate_claims(project_root, require_rows=True, allow_example_data=allow_example_data))
    elif phase in range(13, 19):
        issues.extend(validate_writing_completion(project_root, phase))
    return issues


def validate_writing_completion(project_root: Path, phase: int = 18) -> list[Issue]:
    from .writing.pipeline import WritingPipeline
    try:
        result = WritingPipeline(project_root).completion(phase)
        return [Issue("error", "writing_completion_required", "09_writing", message) for message in result["blockers"]]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return [Issue("error", "writing_completion_required", "09_writing", str(exc))]


def validate_synthesis_completion(project_root: Path, phase: int = 11) -> list[Issue]:
    from .synthesis.pipeline import SynthesisPipeline
    try:
        result = SynthesisPipeline(project_root).completion(phase)
        return [Issue("error", "synthesis_completion_required", "07_synthesis", message) for message in result["blockers"]]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return [Issue("error", "synthesis_completion_required", "07_synthesis", str(exc))]


def validate_reading_completion(project_root: Path, phase: int = 8) -> list[Issue]:
    from .reading.pipeline import ReadingPipeline
    try:
        result = ReadingPipeline(project_root).completion(phase)
        return [Issue("error", "reading_evidence_completion_required", str(project_root / "06_evidence"), message)
                for message in result["blockers"]]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return [Issue("error", "reading_evidence_completion_required", str(project_root / "06_evidence"), str(exc))]


def validate_project(project_root: Path, allow_example_data: bool = False) -> list[Issue]:
    issues = [
        Issue("error", "invalid_workflow_registry", "workflow/phases.json", message)
        for message in validate_workflow_registry()
    ]
    issues.extend(validate_protocol(project_root))
    csv_fields = _project_csv_fields(project_root)
    for relative_path, schema_name in INITIAL_CSV_FILES.items():
        issues.extend(_csv_issues(project_root / relative_path, csv_fields[schema_name]))
    issues.extend(validate_registry(project_root, allow_example_data=allow_example_data))
    issues.extend(validate_discovery_provenance(project_root))
    if (project_root / "03_library/documents").exists():
        from .documents.pipeline import DocumentPipeline
        try:
            result = DocumentPipeline(project_root).validate()
            for error in result["errors"]:
                issues.append(Issue("error", "document_provenance_invalid", "03_library/documents", str(error)))
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues.append(Issue("error", "document_provenance_invalid", "03_library/documents", str(error)))
    issues.extend(validate_screening(project_root, allow_example_data=allow_example_data))
    issues.extend(validate_evidence(project_root, allow_example_data=allow_example_data))
    issues.extend(validate_claims(project_root, allow_example_data=allow_example_data))
    state_path = project_root / ".review/state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        protocol = _load_protocol(project_root)
        if state.get('project_id') != protocol.get('project_id') or state.get('research_question') != protocol.get('research_question'):
            issues.append(Issue('error', 'protocol_state_identity_mismatch', str(state_path), 'Protocol and state identities/questions must agree.'))
        if len(state.get("phases", {})) != 19:
            issues.append(Issue("error", "invalid_phase_count", str(state_path), "Expected 19 phases (0-18)."))
        if state.get("reading_data"):
            from .reading.pipeline import ReadingPipeline
            result = ReadingPipeline(project_root).validate()
            issues.extend(Issue("error", "reading_source_integrity", "05_reading_notes", message) for message in result["errors"])
        if state.get("synthesis_data"):
            from .synthesis.pipeline import SynthesisPipeline
            result = SynthesisPipeline(project_root).validate()
            issues.extend(Issue("error", "synthesis_integrity", "07_synthesis", message) for message in result["errors"])
        if state.get("writing_data"):
            from .writing.pipeline import WritingPipeline
            result = WritingPipeline(project_root).validate()
            issues.extend(Issue("error", "writing_integrity", "09_writing", message) for message in result["errors"])
        if state.get("citation_data"):
            from .citations.pipeline import CitationPipeline
            result = CitationPipeline(project_root).validate()
            issues.extend(Issue("error", "citation_integrity", "02_discovery", message) for message in result["errors"])
            if result["stale_run_ids"]:
                issues.append(Issue("warning", "stale_citation_history", "02_discovery", ", ".join(result["stale_run_ids"])))
            if state["phases"]["4"]["status"] == "completed":
                issues.extend(validate_phase(project_root, 4, allow_example_data))
    except (OSError, json.JSONDecodeError):
        issues.append(Issue("error", "invalid_state", str(state_path), "State file is missing or invalid; run recover."))
    return issues

