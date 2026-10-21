from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_review_agent.project import approve_protocol, initialize_project
from research_review_agent.state import load_state, persist_state, recover_state
from research_review_agent.workflow import evaluate_gates
from tests.helpers import fictional_claim_row, fictional_evidence_row, fictional_registry_row, write_rows


class GatesAndRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "education"
        initialize_project(
            self.project,
            "Which classroom feedback practices support conceptual understanding in secondary-school mathematics?",
            "education",
            self.repo / "examples/configs/education.json",
        )
        approve_protocol(self.project, "fictional-test-reviewer")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _set_completed(self, phases: list[int]) -> None:
        state = load_state(self.project)
        for phase in phases:
            state["phases"][str(phase)]["status"] = "completed"
        persist_state(self.project, state, "fictional_test_setup", {"phases": phases})

    def test_gate_1_requires_completed_screening(self) -> None:
        failed = evaluate_gates(self.project, 7, allow_example_data=True)
        self.assertEqual(failed["gate-1-screening-before-reading"]["status"], "fail")
        write_rows(self.project / "04_screening/SCREENING_MASTER.csv", "screening", [{
            "paper_id": "FICT001", "stage": "full_text", "criteria_version": "0.1",
            "decision": "include", "exclusion_reason": "", "decision_basis": "fictional fixture",
            "evidence_available": "fictional full text", "reviewer": "test", "timestamp": "2099-01-01T00:00:00Z",
            "review_role": "core", "priority": "test", "example_data": "true", "extension_json": "{}",
        }])
        self._set_completed([1, 2, 3, 4, 5, 6])
        passed = evaluate_gates(self.project, 7, allow_example_data=True)
        # Round 2F intentionally closes the legacy single-row bypass. This is not
        # an approved scope, versioned history, or genuine Phase 4/5 completion.
        self.assertEqual(passed["gate-1-screening-before-reading"]["status"], "fail")

    def test_gates_2_and_3_require_evidence_and_claims(self) -> None:
        write_rows(self.project / "03_library/PAPER_REGISTRY.csv", "paper_registry", [fictional_registry_row()])
        extension = {
            "participants_or_cases": "fictional participants",
            "data_collection": "fictional interviews",
            "analytic_approach": "fictional thematic analysis",
        }
        write_rows(
            self.project / "06_evidence/EVIDENCE_MATRIX.csv",
            "evidence",
            [fictional_evidence_row(extension, research_types=("qualitative_empirical",))],
        )
        self._set_completed([1, 2, 3, 4, 5, 6, 7, 8])
        failed = evaluate_gates(self.project, 15, allow_example_data=True)
        # Round 2G closes the single-CSV-row bypass: no reviewed corpus/reading history.
        self.assertEqual(failed["gate-2-evidence-before-drafting"]["status"], "fail")
        self.assertEqual(failed["gate-3-claims-before-gap"]["status"], "fail")
        write_rows(self.project / "08_argument/CLAIM_MAP.csv", "claim", [fictional_claim_row()])
        self._set_completed([9, 10, 11])
        passed = evaluate_gates(self.project, 15, allow_example_data=True)
        self.assertEqual(passed["gate-2-evidence-before-drafting"]["status"], "fail")
        # Round 2H closes the legacy CSV-only bypass: maps, normalized links,
        # current source dependencies and semantic/human reviews are required.
        self.assertEqual(passed["gate-3-claims-before-gap"]["status"], "fail")

    def test_recovery_ignores_corrupt_state_and_bad_event(self) -> None:
        state = load_state(self.project)
        state["phases"]["1"]["status"] = "blocked"
        expected = persist_state(self.project, state, "fictional_interruption", {"reason": "test"})
        with (self.project / ".review/events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write('{"broken": true}\n')
        (self.project / ".review/state.json").write_text("not json", encoding="utf-8")
        recovered = recover_state(self.project)
        self.assertEqual(recovered["seq"], expected["seq"])
        self.assertEqual(recovered["phases"]["1"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()

