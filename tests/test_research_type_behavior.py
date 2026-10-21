from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_review_agent.project import initialize_project
from research_review_agent.validation import protocol_status, validate_project


class ResearchTypeBehaviorTests(unittest.TestCase):
    CASES = {
        "quantitative": {
            "question": "How is rotating shift frequency associated with reported fatigue among hospital nurses?",
            "research_type": "quantitative_empirical",
            "fields": ["population", "predictor_or_exposure", "outcome", "effect_size"],
        },
        "qualitative_education": {
            "question": "How do adult literacy tutors describe adapting feedback for multilingual learners?",
            "research_type": "qualitative_empirical",
            "fields": ["participants_or_cases", "data_collection", "analytic_approach", "researcher_positioning"],
        },
        "historical_documentary": {
            "question": "How did municipal rationing records frame household fuel scarcity during the 1940s?",
            "research_type": "historical_documentary",
            "fields": ["source_genre", "archive_or_collection", "authorship_or_provenance", "historical_context"],
        },
        "archaeological_material": {
            "question": "What can microwear patterns on ground-stone tools reveal about plant processing practices?",
            "research_type": "archaeological_material",
            "fields": ["material_class", "provenience", "chronology", "analytical_technique"],
        },
    }

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _config(self, case: dict[str, object]) -> dict[str, object]:
        research_type = str(case["research_type"])
        question = str(case["question"])
        fields = list(case["fields"])
        return {
            "title": "Fictional software behavior test protocol",
            "review_type": "rigorous_narrative_or_thematic",
            "research_types": [research_type],
            "scope": {
                "units_of_analysis": ["Units derived from the test question"],
                "phenomena_or_topics": [question],
                "relationships_or_questions": ["The relationship or interpretation stated in the question"],
                "contexts": ["Contexts eligible under the question"],
                "geographic_scope": ["To be confirmed during human review"],
                "temporal_scope": "Defined by the question or human review",
                "languages": ["English for this software fixture"],
                "source_types": ["Research-type-appropriate sources"],
            },
            "subquestions": ["How is the focal phenomenon defined?", "Which contexts and methods bound the available evidence?"],
            "concept_definitions": [{"id": "D1", "label": "Focal phenomenon", "definition": question, "boundaries": "No conclusion is presupposed."}],
            "concept_blocks": [{"id": "C1", "label": "Question-derived concepts", "terms": [question.split()[2], question.split()[-1].rstrip("?")]}],
            "screening": {
                "criteria_version": "0.1-draft",
                "include": ["Directly addresses the question using an applicable evidence type"],
                "exclude": ["Does not provide an interpretable contribution to the question"],
            },
            "search": {
                "databases": [],
                "strategy_groups": [{"id": "S1", "name": "Question-derived discovery", "purpose": "Locate relevant sources without executing a search.", "concept_blocks": ["C1"]}],
                "status": "planned_not_executed",
            },
            "evidence_extensions": [
                {"name": name, "label": name.replace("_", " ").title(), "description": f"Research-type field for {name}.", "type": "string", "required": False, "research_types": [research_type]}
                for name in fields
            ],
            "human_decisions": {"resolved": [], "pending": ["Confirm scope and terminology before approval."]},
        }

    def test_four_methodological_profiles_are_distinct_and_case_neutral(self) -> None:
        banned = ["social media", "political participation", "political efficacy", "tiktok", "instagram", "university students"]
        outputs: dict[str, dict[str, object]] = {}
        for name, case in self.CASES.items():
            config = self.root / f"{name}.json"
            config.write_text(json.dumps(self._config(case), ensure_ascii=False), encoding="utf-8")
            project = self.root / f"project-{name}"
            initialize_project(project, str(case["question"]), name, config)
            protocol = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
            outputs[name] = protocol
            self.assertEqual(protocol["research_types"], [case["research_type"]])
            self.assertEqual({field["name"] for field in protocol["evidence_extensions"]}, set(case["fields"]))
            status = protocol_status(project)
            self.assertTrue(status["schema_valid"])
            self.assertTrue(status["substantively_populated"])
            self.assertTrue(status["pending_human_review"])
            self.assertFalse(status["approved"])
            self.assertFalse([issue for issue in validate_project(project) if issue.severity == "error"])
            corpus = json.dumps(protocol, ensure_ascii=False).lower()
            for term in banned:
                self.assertNotIn(term, corpus)

        field_sets = [{field["name"] for field in protocol["evidence_extensions"]} for protocol in outputs.values()]
        self.assertEqual(len({frozenset(fields) for fields in field_sets}), 4)


if __name__ == "__main__":
    unittest.main()
