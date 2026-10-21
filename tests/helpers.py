from __future__ import annotations

import csv
import json
from pathlib import Path

from research_review_agent.constants import CSV_FIELDS, CSV_FIELDS_V1


def write_rows(path: Path, schema: str, rows: list[dict[str, str]], *, legacy: bool = False) -> None:
    fields = CSV_FIELDS_V1[schema] if legacy else CSV_FIELDS[schema]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def fictional_registry_row(paper_id: str = "FICT001") -> dict[str, str]:
    return {
        "paper_id": paper_id,
        "title": "Fictional study for software validation only",
        "authors": "Example, A.",
        "year": "2099",
        "journal": "Nonexistent Test Journal",
        "doi": "",
        "url": "",
        "pdf_path": f"03_library/papers/{paper_id}.pdf",
        "paper_type": "fictional_test_record",
        "retrieval_source": "generated test fixture",
        "retrieval_date": "2099-01-01",
        "fulltext_available": "true",
        "license": "not_applicable",
        "sha256": "0" * 64,
        "example_data": "true",
        "extension_json": "{}",
    }


def fictional_evidence_row(
    extension: dict[str, object],
    paper_id: str = "FICT001",
    evidence_id: str = "FICT001-E01",
    research_types: tuple[str, ...] = ("archaeological_material",),
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "paper_id": paper_id,
        "research_question": "Fictional test question",
        "source_basis": "full_text",
        "research_context": "synthetic software-validation fixture",
        "evidence_type": "fictional_test_record",
        "research_types": json.dumps(list(research_types)),
        "finding_argument_proposition": "Synthetic value used only to exercise validation.",
        "evidence_locator": json.dumps([{"pdf_page": 1, "section": "synthetic fixture", "evidence_note": "Not a real paper"}]),
        "limitations_uncertainty": "This is not scientific evidence.",
        "verification_status": "unverified",
        "example_data": "true",
        "extension_json": json.dumps(extension),
    }


def legacy_fictional_evidence_row(extension: dict[str, object], paper_id: str = "FICT001", evidence_id: str = "FICT001-E01") -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "paper_id": paper_id,
        "research_question": "Fictional legacy test question",
        "theme": "software validation",
        "subtheme": "legacy schema behavior",
        "study_context": "synthetic fixture",
        "population": "not_applicable",
        "sample_size": "not_applicable",
        "study_design": "fictional_test_record",
        "method": "not_applicable",
        "predictor_or_exposure": "not_applicable",
        "outcome": "validator pass/fail",
        "finding": "Synthetic legacy value used only to exercise validation.",
        "effect_direction": "not_applicable",
        "effect_size": "not_applicable",
        "uncertainty": "not_applicable",
        "mediator": "not_applicable",
        "moderator": "not_applicable",
        "authors_interpretation": "not_applicable",
        "alternative_explanation": "not_applicable",
        "limitations": "This is not scientific evidence.",
        "supports_claim": "FICT-CLAIM-01",
        "contradicts_claim": "",
        "evidence_strength": "not_assessed",
        "evidence_locator": json.dumps([{"pdf_page": 1, "section": "synthetic fixture", "evidence_note": "Not a real paper"}]),
        "source_basis": "full_text",
        "example_data": "true",
        "extension_json": json.dumps(extension),
    }


def fictional_claim_row(evidence_id: str = "FICT001-E01") -> dict[str, str]:
    return {
        "claim_id": "FICT-CLAIM-01",
        "claim": "The validator accepts a structurally valid fictional row.",
        "supporting_evidence": evidence_id,
        "contradictory_evidence": "",
        "evidence_type": "fictional_test_record",
        "evidence_strength": "not_assessed",
        "boundary_conditions": "software tests only",
        "allowed_wording": "accepts the fixture",
        "prohibited_overclaim": "supports a scientific conclusion",
        "confidence": "not_applicable",
        "verdict": "not_auditable",
        "example_data": "true",
        "extension_json": "{}",
    }

