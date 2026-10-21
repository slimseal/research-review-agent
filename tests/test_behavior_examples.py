from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from research_review_agent.state import load_state
from research_review_agent.validation import protocol_status, validate_project


class SavedBehaviorExampleTests(unittest.TestCase):
    def test_four_saved_no_skills_protocols_remain_drafts_without_evidence(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        base = repo / "examples/round2b-no-skills-behavior"
        manifest = json.loads((base / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["no_skills"]["confirmed"])
        self.assertFalse(manifest["no_skills"]["project_or_global_skills_used"])
        self.assertFalse(manifest["failures"])
        self.assertEqual(len(manifest["projects"]), 4)
        banned = ["social media", "political participation", "political efficacy", "tiktok", "instagram", "university students"]
        for project in sorted((base / "projects").iterdir()):
            with self.subTest(project=project.name):
                protocol = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
                status = protocol_status(project)
                self.assertTrue(status["schema_valid"])
                self.assertTrue(status["substantively_populated"])
                self.assertTrue(status["pending_human_review"])
                self.assertFalse(status["approved"])
                self.assertIn("demonstration", protocol["title"].lower())
                self.assertEqual(protocol["search"]["status"], "planned_not_executed")
                self.assertFalse([issue for issue in validate_project(project) if issue.severity == "error"])
                state = load_state(project)
                self.assertEqual(state["phases"]["0"]["status"], "in_progress")
                self.assertTrue(all(state["phases"][str(index)]["status"] == "pending" for index in range(1, 19)))
                for relative in (
                    "02_discovery/DISCOVERY_MASTER.csv",
                    "03_library/PAPER_REGISTRY.csv",
                    "04_screening/SCREENING_MASTER.csv",
                    "06_evidence/EVIDENCE_MATRIX.csv",
                    "08_argument/CLAIM_MAP.csv",
                ):
                    with (project / relative).open(encoding="utf-8", newline="") as handle:
                        self.assertFalse(list(csv.DictReader(handle)), relative)
                corpus = json.dumps(protocol, ensure_ascii=False).lower()
                for term in banned:
                    self.assertNotIn(term, corpus)


if __name__ == "__main__":
    unittest.main()
