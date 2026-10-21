from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from research_review_agent.project import initialize_project
from research_review_agent.registry import REQUIRED_PHASE_KEYS, load_workflow_registry, read_procedure, validate_registry_data, validate_workflow_registry
from research_review_agent.workflow import next_action, phase_context, transition_phase


class WorkflowRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "review"
        initialize_project(self.project, "How should a fictional workflow registry test behave?", "software-test")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_registry_is_complete_and_authoritative(self) -> None:
        registry = load_workflow_registry()
        self.assertEqual(registry["phase_count"], 19)
        self.assertEqual([item["phase_id"] for item in registry["phases"]], list(range(19)))
        self.assertFalse(validate_workflow_registry())
        for phase in registry["phases"]:
            self.assertTrue(REQUIRED_PHASE_KEYS.issubset(phase))
            procedure = read_procedure(phase["research_procedure"])
            for heading in (
                "## Objective and rationale",
                "## Required inputs",
                "## Research operations",
                "## Expected artifacts",
                "## Evidence and provenance requirements",
                "## Academic judgment points",
                "## Uncertainty and failure handling",
                "## Prohibited actions",
                "## Completion requirements",
            ):
                self.assertIn(heading, procedure)

    def test_missing_procedure_is_rejected(self) -> None:
        registry = copy.deepcopy(load_workflow_registry())
        registry["phases"][4]["research_procedure"] = "procedures/does-not-exist.md"
        errors = validate_registry_data(registry, lambda path: path != "procedures/does-not-exist.md")
        self.assertTrue(any("procedure is missing" in error for error in errors))

    def test_next_and_phase_context_load_plain_procedure(self) -> None:
        result = next_action(self.project)
        self.assertEqual(result["next_phase"], 0)
        self.assertTrue(result["allowed_to_start"])
        self.assertFalse(result["completion_ready"])
        context = phase_context(self.project, 0)
        self.assertIn("# Phase 0", context["procedure"])
        self.assertNotIn("$research-review", context["procedure"])
        self.assertIn("edit_expected_outputs", context["permitted_actions"])
        self.assertNotIn("request_human_protocol_approval", context["permitted_actions"])

    def test_registry_prerequisite_controls_transition(self) -> None:
        with self.assertRaisesRegex(ValueError, r"Registry prerequisites are incomplete: \[1\]"):
            transition_phase(self.project, 2, "in_progress")


if __name__ == "__main__":
    unittest.main()

