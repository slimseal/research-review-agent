from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_review_agent.project import approve_protocol, initialize_project
from research_review_agent.validation import validate_project


class InitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create(self, domain: str, question: str) -> Path:
        project = self.base / domain
        config = self.repo / "examples/configs" / f"{domain}.json"
        initialize_project(project, question, domain, config)
        return project

    def test_three_domains_initialize_and_approve(self) -> None:
        cases = {
            "social-sciences": "How do neighborhood green spaces relate to perceived social cohesion among urban residents?",
            "archaeology": "How do ceramic petrography methods contribute to reconstructing exchange networks in Late Bronze Age coastal settlements?",
            "education": "Which classroom feedback practices support conceptual understanding in secondary-school mathematics?",
        }
        for domain, question in cases.items():
            with self.subTest(domain=domain):
                project = self._create(domain, question)
                protocol = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
                self.assertEqual(protocol["research_question"], question)
                self.assertEqual(protocol["status"], "draft")
                self.assertTrue(protocol["evidence_extensions"])
                approve_protocol(project, "fictional-test-reviewer")
                approved = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
                self.assertEqual(approved["status"], "approved")
                self.assertFalse([issue for issue in validate_project(project, allow_example_data=True) if issue.severity == "error"])

    def test_case_terms_do_not_leak_into_unrelated_projects(self) -> None:
        banned = [
            "social media", "political participation", "political efficacy", "tiktok", "instagram",
            "voting", "protest", "university students", "college students",
        ]
        for domain, question in {
            "archaeology": "How do ceramic petrography methods contribute to reconstructing exchange networks in Late Bronze Age coastal settlements?",
            "education": "Which classroom feedback practices support conceptual understanding in secondary-school mathematics?",
        }.items():
            project = self._create(domain, question)
            corpus = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in project.rglob("*")
                if path.is_file() and path.suffix.lower() in {".md", ".json", ".csv", ".bib"}
            ).lower()
            for term in banned:
                self.assertNotIn(term, corpus, f"{term!r} leaked into {domain}")

    def test_case_terms_do_not_leak_into_core_or_workflow(self) -> None:
        banned = ["social media", "political participation", "political efficacy", "tiktok", "instagram"]
        roots = [self.repo / "research_review_agent", self.repo / "workflow"]
        corpus = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for root in roots
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".py", ".json", ".md", ".yaml"}
        ).lower()
        for term in banned:
            self.assertNotIn(term, corpus)


if __name__ == "__main__":
    unittest.main()

