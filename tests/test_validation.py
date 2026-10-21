from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_review_agent.project import initialize_project
from research_review_agent.validation import validate_claims, validate_evidence
from tests.helpers import fictional_claim_row, fictional_evidence_row, fictional_registry_row, write_rows


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "archaeology"
        initialize_project(
            self.project,
            "How do ceramic petrography methods contribute to reconstructing exchange networks in Late Bronze Age coastal settlements?",
            "archaeology",
            self.repo / "examples/configs/archaeology.json",
        )
        write_rows(self.project / "03_library/PAPER_REGISTRY.csv", "paper_registry", [fictional_registry_row()])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_core_and_extension_evidence(self) -> None:
        extension = {"material_class": "fictional ceramic", "chronology": "fictional period", "analytical_technique": "fictional method"}
        write_rows(self.project / "06_evidence/EVIDENCE_MATRIX.csv", "evidence", [fictional_evidence_row(extension)])
        write_rows(self.project / "08_argument/CLAIM_MAP.csv", "claim", [fictional_claim_row()])
        self.assertEqual(validate_evidence(self.project, require_rows=True, allow_example_data=True), [])
        self.assertEqual(validate_claims(self.project, require_rows=True, allow_example_data=True), [])

    def test_missing_required_extension_is_rejected(self) -> None:
        write_rows(self.project / "06_evidence/EVIDENCE_MATRIX.csv", "evidence", [fictional_evidence_row({"material_class": "fictional ceramic"})])
        codes = {issue.code for issue in validate_evidence(self.project, require_rows=True, allow_example_data=True)}
        self.assertIn("missing_extension_fields", codes)

    def test_wrong_extension_type_is_rejected(self) -> None:
        extension = {"material_class": "fictional ceramic", "chronology": "fictional period", "analytical_technique": ["wrong", "type"]}
        write_rows(self.project / "06_evidence/EVIDENCE_MATRIX.csv", "evidence", [fictional_evidence_row(extension)])
        codes = {issue.code for issue in validate_evidence(self.project, require_rows=True, allow_example_data=True)}
        self.assertIn("extension_type_mismatch", codes)

    def test_bad_locator_and_unknown_paper_are_rejected(self) -> None:
        row = fictional_evidence_row({"material_class": "x", "chronology": "x", "analytical_technique": "x"}, paper_id="UNKNOWN")
        row["evidence_locator"] = "[]"
        write_rows(self.project / "06_evidence/EVIDENCE_MATRIX.csv", "evidence", [row])
        codes = {issue.code for issue in validate_evidence(self.project, require_rows=True, allow_example_data=True)}
        self.assertIn("unknown_paper_id", codes)
        self.assertIn("invalid_evidence_locator", codes)

    def test_example_rows_are_rejected_by_default(self) -> None:
        extension = {"material_class": "x", "chronology": "x", "analytical_technique": "x"}
        write_rows(self.project / "06_evidence/EVIDENCE_MATRIX.csv", "evidence", [fictional_evidence_row(extension)])
        codes = {issue.code for issue in validate_evidence(self.project, require_rows=True)}
        self.assertIn("example_data_disallowed", codes)


if __name__ == "__main__":
    unittest.main()

