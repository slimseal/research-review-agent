from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from research_review_agent.adapters import AdapterUnavailableError, require_adapter
from research_review_agent.constants import LEGACY_EVIDENCE_FIELDS, UNIVERSAL_EVIDENCE_FIELDS
from research_review_agent.project import approve_protocol, initialize_project, update_protocol_draft
from research_review_agent.validation import protocol_status, validate_evidence, validate_protocol
from tests.helpers import fictional_evidence_row, fictional_registry_row, legacy_fictional_evidence_row, write_rows


class ProtocolV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_three_domains_use_distinct_composable_research_types(self) -> None:
        cases = {
            "social-sciences": ("quantitative_empirical", {"population", "predictor_or_exposure", "outcome"}),
            "education": ("qualitative_empirical", {"participants_or_cases", "data_collection", "analytic_approach"}),
            "archaeology": ("archaeological_material", {"material_class", "chronology", "analytical_technique"}),
        }
        for domain, (research_type, required_fields) in cases.items():
            with self.subTest(domain=domain):
                project = self.base / domain
                config = self.repo / "examples/configs" / f"{domain}.json"
                initialize_project(project, f"Fictional {domain} protocol behavior test?", domain, config)
                protocol = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
                extension_names = {field["name"] for field in protocol["evidence_extensions"]}
                self.assertEqual(protocol["research_types"], [research_type])
                self.assertTrue(required_fields.issubset(extension_names))
                self.assertTrue(protocol["search"]["strategy_groups"])
                self.assertNotIn("query_families", protocol["search"])
                status = protocol_status(project)
                self.assertTrue(status["schema_valid"])
                self.assertTrue(status["substantively_populated"])
                self.assertTrue(status["pending_human_review"])
                self.assertFalse(status["approved"])

        education = json.loads((self.base / "education/00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
        education_fields = {field["name"] for field in education["evidence_extensions"]}
        self.assertFalse({"effect_size", "mediator", "moderator", "predictor_or_exposure"} & education_fields)

    def test_draft_update_preserves_question_status_and_requires_review(self) -> None:
        project = self.base / "draft"
        initialize_project(project, "How are historical arguments constructed from contested archives?", "history")
        fragment = self.base / "fragment.json"
        fragment.write_text(
            json.dumps(
                {
                    "domain": "documentary history",
                    "research_types": ["historical_documentary"],
                    "scope": {"units_of_analysis": ["archival documents"], "source_types": ["correspondence"]},
                    "subquestions": ["How is provenance assessed?"],
                    "concept_definitions": [{"id": "D1", "label": "Contested archive", "definition": "An archive with disputed completeness or provenance."}],
                    "concept_blocks": [{"id": "C1", "label": "Archive", "terms": ["archive", "correspondence"]}],
                    "screening": {"include": ["Uses inspectable archival sources"], "exclude": ["Provides no identifiable source basis"]},
                    "search": {"strategy_groups": [{"id": "S1", "name": "Archive and provenance", "purpose": "Locate documentary studies", "concept_blocks": ["C1"]}], "status": "planned_not_executed"},
                    "evidence_extensions": [{"name": "provenance", "label": "Provenance", "description": "Documented source history.", "type": "string", "required": True, "research_types": ["historical_documentary"]}],
                    "human_decisions": {"resolved": [], "pending": ["Confirm geographic scope"]},
                }
            ),
            encoding="utf-8",
        )
        original = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
        updated = update_protocol_draft(project, fragment)
        self.assertEqual(updated["research_question"], original["research_question"])
        self.assertEqual(updated["status"], "draft")
        state = json.loads((project / ".review/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["domain"], "documentary history")
        status = protocol_status(project)
        self.assertTrue(status["schema_valid"])
        self.assertTrue(status["substantively_populated"])
        self.assertTrue(status["pending_human_review"])
        self.assertFalse(status["approved"])
        with self.assertRaisesRegex(ValueError, "human decisions remain pending"):
            approve_protocol(project, "fictional-reviewer")

    def test_v1_evidence_header_and_rows_remain_valid(self) -> None:
        project = self.base / "legacy"
        config = self.base / "legacy.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "scope": {"population_or_units": ["fictional units"]},
                    "subquestions": ["What does the legacy validator accept?"],
                    "concept_blocks": [{"id": "C1", "label": "Legacy", "terms": ["legacy"]}],
                    "screening": {"include": ["Fictional eligible record"], "exclude": ["Fictional ineligible record"]},
                    "evidence_extensions": [],
                }
            ),
            encoding="utf-8",
        )
        initialize_project(project, "Can a version 1 project still validate?", "software-test", config)
        with (project / "06_evidence/EVIDENCE_MATRIX.csv").open(encoding="utf-8", newline="") as handle:
            self.assertEqual(next(csv.reader(handle)), LEGACY_EVIDENCE_FIELDS)
        write_rows(project / "03_library/PAPER_REGISTRY.csv", "paper_registry", [fictional_registry_row()])
        write_rows(project / "06_evidence/EVIDENCE_MATRIX.csv", "evidence", [legacy_fictional_evidence_row({})], legacy=True)
        self.assertEqual(validate_protocol(project, require_substantive=True), [])
        self.assertEqual(validate_evidence(project, require_rows=True, allow_example_data=True), [])

    def test_new_projects_use_v2_evidence_header(self) -> None:
        project = self.base / "v2"
        initialize_project(project, "What evidence model is initialized?", "software-test")
        with (project / "06_evidence/EVIDENCE_MATRIX.csv").open(encoding="utf-8", newline="") as handle:
            self.assertEqual(next(csv.reader(handle)), UNIVERSAL_EVIDENCE_FIELDS)

    def test_composed_extensions_require_only_fields_for_each_evidence_row_type(self) -> None:
        project = self.base / "composed"
        config = self.base / "composed.json"
        config.write_text(
            json.dumps(
                {
                    "research_types": ["historical_documentary", "archaeological_material"],
                    "scope": {"units_of_analysis": ["documents and sites"]},
                    "subquestions": ["How do the two source types relate?"],
                    "concept_definitions": [{"id": "D1", "label": "Case", "definition": "A fictional mixed-source case."}],
                    "concept_blocks": [{"id": "C1", "label": "Sources", "terms": ["archive", "site"]}],
                    "screening": {"include": ["Has an inspectable source"], "exclude": ["Has no source basis"]},
                    "search": {"strategy_groups": [{"id": "S1", "name": "Mixed sources", "purpose": "Locate documentary or material studies", "concept_blocks": ["C1"]}], "status": "planned_not_executed"},
                    "evidence_extensions": [
                        {"name": "provenance", "label": "Provenance", "description": "Document provenance.", "type": "string", "required": True, "research_types": ["historical_documentary"]},
                        {"name": "material_class", "label": "Material class", "description": "Material evidence class.", "type": "string", "required": True, "research_types": ["archaeological_material"]},
                    ],
                    "human_decisions": {"resolved": ["Fictional test only"], "pending": []},
                }
            ),
            encoding="utf-8",
        )
        initialize_project(project, "How are documentary and material sources combined?", "mixed-test", config)
        write_rows(project / "03_library/PAPER_REGISTRY.csv", "paper_registry", [fictional_registry_row()])
        row = fictional_evidence_row(
            {"provenance": "fictional archive"},
            research_types=("historical_documentary",),
        )
        write_rows(project / "06_evidence/EVIDENCE_MATRIX.csv", "evidence", [row])
        self.assertEqual(validate_evidence(project, require_rows=True, allow_example_data=True), [])

    def test_packaged_and_missing_adapters_are_distinguished(self) -> None:
        require_adapter("scholarly_discovery")
        with self.assertRaisesRegex(AdapterUnavailableError, "ADAPTER_UNAVAILABLE"):
            require_adapter("full_text_pdf_reading")


if __name__ == "__main__":
    unittest.main()
