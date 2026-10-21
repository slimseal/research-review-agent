from __future__ import annotations

import unittest
from pathlib import Path


class NoSkillsArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]

    def test_project_skill_tree_is_absent(self) -> None:
        self.assertFalse((self.repo / ".agents/skills").exists())
        self.assertFalse(list(self.repo.rglob("SKILL.md")))
        self.assertFalse(list(self.repo.rglob("openai.yaml")))

    def test_active_instructions_route_through_registry(self) -> None:
        for relative in ("AGENTS.md", "README.md", "docs/architecture.md", "docs/tutorial.md"):
            text = (self.repo / relative).read_text(encoding="utf-8")
            self.assertIn("workflow", text.lower())
            self.assertNotIn("$research-review-", text)
        agents = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("rragent next", agents)
        self.assertIn("rragent phase-context", agents)

    def test_obsolete_skill_validator_is_absent(self) -> None:
        self.assertFalse((self.repo / "scripts/validate_skills.py").exists())
        self.assertFalse((self.repo / "scripts/validate_skills.sh").exists())


if __name__ == "__main__":
    unittest.main()
