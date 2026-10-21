from __future__ import annotations

import csv
import json
import re
import unicodedata
import uuid
from importlib.resources import files
from pathlib import Path
from typing import Any

from .constants import INITIAL_CSV_FILES, PROJECT_DIRECTORIES, csv_fields_for_version
from .state import new_state, persist_state, utc_now, write_json_atomic


def load_schema_catalog() -> dict[str, Any]:
    resource = files("research_review_agent").joinpath("resources/schema_catalog.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _write_csv_header(path: Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(fields)


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _artifact_notice(protocol: dict[str, Any]) -> list[str]:
    notice = protocol.get("artifact_notice")
    if protocol.get("example_data") and notice:
        return [f"> **Demonstration notice:** {notice}", ""]
    return []


def _render_protocol(protocol: dict[str, Any]) -> str:
    scope = protocol["scope"]
    lines = ["# Review Protocol", "", *_artifact_notice(protocol),
        f"Status: **{protocol['status']}**",
        "",
        "## Research question",
        "",
        protocol["research_question"],
        "",
        "## Review design",
        "",
        f"- Review type: `{protocol['review_type']}`",
        f"- Domain: `{protocol['domain']}`",
        f"- Protocol version: `{protocol['protocol_version']}`",
        f"- Schema version: `{protocol.get('schema_version', '1.0.0')}`",
        f"- Research types: `{', '.join(protocol.get('research_types', [])) or 'Not yet specified'}`",
        "",
        "## Scope",
        "",
    ]
    for key, value in scope.items():
        rendered = _render_value(value)
        lines.append(f"- {key}: {rendered or 'Not yet specified'}")
    lines.extend(["", "## Subquestions", ""])
    lines.extend([f"{index}. {item}" for index, item in enumerate(protocol["subquestions"], start=1)] or ["Not yet specified."])
    lines.extend(["", "## Concept definitions", ""])
    for concept in protocol.get("concept_definitions", []):
        label = concept.get("label", concept.get("name", concept.get("concept", concept.get("id", "concept"))))
        definition = concept.get("definition", "Not yet specified")
        boundaries = concept.get("boundaries", concept.get("scope_note", ""))
        lines.append(f"- **{label}:** {definition}" + (f" Boundaries: {boundaries}" if boundaries else ""))
    if not protocol.get("concept_definitions"):
        lines.append("Not yet specified.")
    lines.extend(["", "## Concept blocks", ""])
    for block in protocol["concept_blocks"]:
        terms = ", ".join(block.get("terms", []))
        lines.append(f"- **{block.get('label', block.get('name', block.get('id', 'concept')))}:** {terms}")
    if not protocol["concept_blocks"]:
        lines.append("Not yet specified.")
    lines.extend(["", "## Proposed search strategies", ""])
    strategies = protocol.get("search", {}).get("strategy_groups", [])
    if not strategies:
        strategies = protocol.get("search", {}).get("strategy_templates", [])
    if not strategies:
        strategies = protocol.get("search", {}).get("query_families", [])
    for strategy in strategies:
        if isinstance(strategy, dict):
            name = strategy.get("name", strategy.get("id", "strategy"))
            purpose = strategy.get("purpose", strategy.get("description", ""))
            blocks = strategy.get("concept_blocks", strategy.get("blocks", []))
            suffix = f"; concept blocks: {', '.join(blocks)}" if blocks else ""
            lines.append(f"- **{name}:** {purpose}{suffix}")
        else:
            lines.append(f"- {strategy}")
    if not strategies:
        lines.append("Not yet specified. Search has not been executed.")
    lines.extend(["", "## Inclusion criteria", ""])
    lines.extend([f"- {item}" for item in protocol["screening"]["include"]] or ["Not yet specified."])
    lines.extend(["", "## Exclusion criteria", ""])
    lines.extend([f"- {item}" for item in protocol["screening"]["exclude"]] or ["Not yet specified."])
    lines.extend([
        "", "## Evidence extension fields", "",
        "Universal fields are fixed by the kit. The following fields are specific to this draft or approved protocol:", "",
    ])
    for field in protocol["evidence_extensions"]:
        lines.append(f"- `{field['name']}` ({field['type']}, required={str(field['required']).lower()}): {field['description']}")
    if not protocol["evidence_extensions"]:
        lines.append("No domain-specific extension fields have been defined yet.")
    lines.extend(["", "## Human decisions", ""])
    decisions = protocol.get("human_decisions", {})
    pending = decisions.get("pending", decisions.get("pending_human_confirmation", [])) if isinstance(decisions, dict) else []
    resolved = decisions.get("resolved", decisions.get("confirmed_by_user", [])) if isinstance(decisions, dict) else []
    lines.append("### Resolved")
    lines.append("")
    lines.extend([f"- {_render_value(item)}" for item in resolved] or ["- None recorded."])
    lines.extend(["", "### Pending", ""])
    lines.extend([f"- {_render_value(item)}" for item in pending] or ["- None recorded."])
    for key, title in (("analysis_plan", "Analysis plan"),
                       ("anticipated_limitations", "Anticipated limitations"),
                       ("evaluation_checkpoint_note", "Independent evaluation checkpoint")):
        if protocol.get(key):
            lines.extend(["", f"## {title}", "", _render_value(protocol[key])])
    if protocol.get("independent_evaluation_policy"):
        lines.extend(["", "## Independent evaluation policy", "",
                      "This is a requirement, not a completed evaluation or human approval.", "",
                      "```json", json.dumps(protocol["independent_evaluation_policy"], ensure_ascii=False, indent=2), "```"])
    if protocol.get("search", {}).get("coverage_plan"):
        lines.extend(["", "## Search budget and limitations", "", protocol["search"]["coverage_plan"], "",
                      protocol["search"].get("supplements", "")])
    lines.extend([
        "", "## Evidence policy", "",
        "- Search metadata and abstracts are discovery evidence only.",
        "- Detailed Methods, Results, numbers, and limitations require full-text evidence with exact locators.",
        "- Supporting, contradictory, negative, and null findings must be retained.",
        "- Approval freezes this protocol version. Later material changes require a new version and a decision-log entry.",
    ])
    return "\n".join(lines) + "\n"


def _render_questions(protocol: dict[str, Any]) -> str:
    lines = ["# Research Questions", "", *_artifact_notice(protocol), "## Primary question", "", protocol["research_question"], "", "## Subquestions", ""]
    lines.extend([f"{i}. {q}" for i, q in enumerate(protocol["subquestions"], start=1)] or ["Not yet specified."])
    return "\n".join(lines) + "\n"


def _render_criteria(protocol: dict[str, Any]) -> str:
    lines = [
        "# Inclusion and Exclusion Criteria", "", *_artifact_notice(protocol), f"Criteria version: `{protocol['protocol_version']}`",
        "", "## Include", "",
    ]
    lines.extend([f"- {item}" for item in protocol["screening"]["include"]] or ["Not yet specified."])
    lines.extend(["", "## Exclude", ""])
    lines.extend([f"- {item}" for item in protocol["screening"]["exclude"]] or ["Not yet specified."])
    lines.extend(["", "Uncertain records must remain uncertain until the missing eligibility information is available.", ""])
    return "\n".join(lines)


def _validate_extension_definition(fields_value: list[dict[str, Any]]) -> None:
    names: set[str] = set()
    allowed_types = {"string", "integer", "number", "boolean", "array", "object"}
    for item in fields_value:
        missing = {"name", "label", "description", "type", "required"} - set(item)
        if missing:
            raise ValueError(f"Extension field is missing keys: {sorted(missing)}")
        name = item["name"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError(f"Invalid extension field name: {name}")
        if name in names:
            raise ValueError(f"Duplicate extension field name: {name}")
        if item["type"] not in allowed_types:
            raise ValueError(f"Unsupported extension field type: {item['type']}")
        if not isinstance(item["required"], bool):
            raise ValueError(f"Extension field required flag must be boolean: {name}")
        research_types = item.get("research_types", [])
        if research_types and (not isinstance(research_types, list) or not all(isinstance(value, str) for value in research_types)):
            raise ValueError(f"Extension field research_types must be a string array: {name}")
        names.add(name)


def _extension_schema(protocol: dict[str, Any]) -> dict[str, Any]:
    schema = {
        "schema_version": protocol.get("schema_version", "1.0.0"),
        "project_id": protocol["project_id"],
        "research_types": protocol.get("research_types", []),
        "fields": protocol.get("evidence_extensions", []),
    }
    if protocol.get("example_data"):
        schema["example_data"] = True
        schema["artifact_notice"] = protocol.get("artifact_notice", "Demonstration data; not verified evidence.")
    return schema


def render_protocol_artifacts(project_root: Path, protocol: dict[str, Any]) -> None:
    write_json_atomic(project_root / "00_protocol/PROTOCOL.json", protocol)
    (project_root / "00_protocol/REVIEW_PROTOCOL.md").write_text(_render_protocol(protocol), encoding="utf-8")
    (project_root / "00_protocol/RESEARCH_QUESTIONS.md").write_text(_render_questions(protocol), encoding="utf-8")
    (project_root / "00_protocol/INCLUSION_EXCLUSION.md").write_text(_render_criteria(protocol), encoding="utf-8")
    write_json_atomic(project_root / "00_protocol/DOMAIN_EXTENSION_SCHEMA.json", _extension_schema(protocol))


def initialize_project(output: Path, question: str, domain: str = "unspecified", config_path: Path | None = None) -> Path:
    question = " ".join(question.split())
    if not question:
        raise ValueError("Research question cannot be empty.")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for directory in PROJECT_DIRECTORIES:
        (output / directory).mkdir(parents=True, exist_ok=True)

    supplied: dict[str, Any] = {}
    if config_path:
        supplied = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(supplied, dict):
            raise ValueError("Configuration must be a JSON object.")
    project_id = f"RRA-{uuid.uuid4().hex[:10].upper()}"
    protocol: dict[str, Any] = {
        "schema_version": "2.0.0",
        "protocol_version": "0.1-draft",
        "project_id": project_id,
        "title": supplied.get("title", "Research review"),
        "research_question": question,
        "domain": domain,
        "review_type": "rigorous_narrative_or_thematic",
        "research_types": [],
        "status": "draft",
        "created_at": utc_now(),
        "approved_at": None,
        "approved_by": None,
        "scope": {
            "units_of_analysis": [], "phenomena_or_topics": [], "relationships_or_questions": [],
            "contexts": [], "geographic_scope": [], "temporal_scope": "Not yet specified",
            "languages": [], "source_types": [],
        },
        "subquestions": [],
        "concept_definitions": [],
        "concept_blocks": [],
        "screening": {"criteria_version": "0.1-draft", "include": [], "exclude": []},
        "search": {"databases": [], "strategy_groups": [], "status": "not_developed"},
        "evidence_extensions": [],
        "human_decisions": {"resolved": [], "pending": []},
    }
    protocol = _deep_merge(protocol, supplied)
    protocol["project_id"] = project_id
    protocol["research_question"] = question
    protocol["domain"] = domain if domain != "unspecified" else protocol.get("domain", domain)
    protocol["status"] = "draft"
    protocol["approved_at"] = None
    protocol["approved_by"] = None
    _validate_extension_definition(protocol["evidence_extensions"])

    render_protocol_artifacts(output, protocol)
    write_json_atomic(output / "00_protocol/UNIVERSAL_SCHEMA_CATALOG.json", load_schema_catalog())
    csv_fields = csv_fields_for_version(protocol["schema_version"])
    for relative_path, schema_name in INITIAL_CSV_FILES.items():
        _write_csv_header(output / relative_path, csv_fields[schema_name])
    (output / "03_library/references.bib").write_text("", encoding="utf-8")
    (output / "DECISIONS.md").write_text(
        "# Decision Log\n\nRecord protocol changes, scope decisions, deviations, and gate overrides here. Gate overrides require explicit human authorization.\n",
        encoding="utf-8",
    )
    state = new_state(project_id, question, protocol["domain"])
    persist_state(output, state, "project_initialized", {"config": str(config_path) if config_path else None})
    return output


def update_protocol_draft(project_root: Path, config_path: Path) -> dict[str, Any]:
    from .amendments import assert_available
    assert_available(project_root)
    path = project_root / "00_protocol/PROTOCOL.json"
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "draft":
        raise ValueError("Only a draft protocol can be updated with this command.")
    supplied = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(supplied, dict):
        raise ValueError("Protocol draft configuration must be a JSON object.")
    protected = {"project_id", "research_question", "status", "approved_at", "approved_by", "created_at", "schema_version"}
    attempted = sorted(protected.intersection(supplied))
    if attempted:
        raise ValueError("Protocol draft update cannot replace protected fields: " + ", ".join(attempted))
    updated = _deep_merge(protocol, supplied)
    from .state import load_state
    if load_state(project_root).get('independent_evaluation_required'):
        if updated.get('independent_evaluation_policy', {}).get('required_before_phase') != 9:
            raise ValueError('INDEPENDENT_EVALUATION_REQUIREMENT_CANNOT_BE_REMOVED')
    updated["status"] = "draft"
    updated["approved_at"] = None
    updated["approved_by"] = None
    _validate_extension_definition(updated.get("evidence_extensions", []))
    render_protocol_artifacts(project_root, updated)
    from .state import load_state

    state = load_state(project_root)
    state["domain"] = updated.get("domain", state.get("domain", "unspecified"))
    persist_state(project_root, state, "protocol_draft_updated", {"config": str(config_path)})
    return updated


def approve_protocol(project_root: Path, approved_by: str) -> dict[str, Any]:
    from .amendments import assert_available
    assert_available(project_root)
    path = project_root / "00_protocol/PROTOCOL.json"
    protocol = json.loads(path.read_text(encoding="utf-8"))
    from .validation import validate_protocol

    issues = validate_protocol(project_root, require_substantive=True)
    errors = [issue.message for issue in issues if issue.severity == "error"]
    if errors:
        raise ValueError("Protocol cannot be approved: " + "; ".join(errors))
    decisions = protocol.get("human_decisions", {})
    pending = decisions.get("pending", decisions.get("pending_human_confirmation", [])) if isinstance(decisions, dict) else []
    if pending:
        raise ValueError("Protocol cannot be approved while human decisions remain pending.")
    _validate_extension_definition(protocol.get("evidence_extensions", []))
    protocol["status"] = "approved"
    protocol["protocol_version"] = re.sub(r"-draft$", "", protocol.get("protocol_version", "1.0"))
    protocol["screening"]["criteria_version"] = protocol["protocol_version"]
    protocol["approved_at"] = utc_now()
    protocol["approved_by"] = approved_by
    render_protocol_artifacts(project_root, protocol)
    from .state import load_state

    state = load_state(project_root)
    state["phases"]["0"].update(status="completed", updated_at=utc_now(), note=f"Approved by {approved_by}")
    persist_state(project_root, state, "protocol_approved", {"approved_by": approved_by, "protocol_version": protocol["protocol_version"]})
    return protocol

