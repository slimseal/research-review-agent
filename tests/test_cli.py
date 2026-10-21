from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_init_status_validate_and_draft_gate(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "review"
            init = subprocess.run(
                [sys.executable, "-m", "research_review_agent", "init", "--question", "What is the fictional test question?", "--domain", "test", "--output", str(project)],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertEqual(json.loads(init.stdout)["status"], "created")
            validate = subprocess.run(
                [sys.executable, "-m", "research_review_agent", "validate", "--project", str(project)],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(validate.returncode, 0, validate.stderr)
            gate = subprocess.run(
                [sys.executable, "-m", "research_review_agent", "gate", "--project", str(project), "--phase", "1"],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(gate.returncode, 2)
            self.assertEqual(json.loads(gate.stdout)["protocol-approved"]["status"], "fail")

            protocol_status = subprocess.run(
                [sys.executable, "-m", "research_review_agent", "protocol-status", "--project", str(project)],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(protocol_status.returncode, 0, protocol_status.stderr)
            status_data = json.loads(protocol_status.stdout)
            self.assertTrue(status_data["schema_valid"])
            self.assertFalse(status_data["substantively_populated"])
            self.assertFalse(status_data["approved"])

    def test_capabilities_report_packaged_metadata_and_missing_fulltext_adapters(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "research_review_agent", "capabilities"],
            cwd=repo, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        capabilities = {item["name"]: item for item in json.loads(result.stdout)["capabilities"]}
        self.assertEqual(capabilities["project_cli"]["status"], "available")
        self.assertEqual(capabilities["scholarly_discovery"]["status"], "available_with_network")
        self.assertEqual(capabilities["bibliography_enrichment"]["status"], "available_with_network")
        self.assertIn(capabilities["paper_acquisition"]["status"], {"available", "optional_dependency_missing"})

    def test_cli_recovery_restores_corrupt_state_from_journal(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "recovery"
            init = subprocess.run(
                [sys.executable, "-m", "research_review_agent", "init", "--question", "Can the CLI recover fictional state?", "--output", str(project)],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            (project / ".review/state.json").write_text("corrupt", encoding="utf-8")
            recover = subprocess.run(
                [sys.executable, "-m", "research_review_agent", "recover", "--project", str(project)],
                cwd=repo, text=True, capture_output=True, check=False,
            )
            self.assertEqual(recover.returncode, 0, recover.stderr)
            self.assertEqual(json.loads(recover.stdout)["status"], "recovered")
            restored = json.loads((project / ".review/state.json").read_text(encoding="utf-8"))
            self.assertEqual(restored["seq"], 1)

    def test_provider_status_never_prints_credentials(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        environment = dict(os.environ)
        environment["OPENALEX_API_KEY"] = "DO-NOT-PRINT-THIS-OPENALEX-SECRET"
        environment["CROSSREF_PLUS_API_TOKEN"] = "DO-NOT-PRINT-THIS-CROSSREF-SECRET"
        result = subprocess.run(
            [sys.executable, "-m", "research_review_agent", "provider-status"],
            cwd=repo, env=environment, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)["providers"]
        self.assertTrue(data["openalex"]["adapter_packaged"])
        self.assertTrue(data["crossref"]["adapter_packaged"])
        self.assertNotIn("DO-NOT-PRINT", result.stdout)


if __name__ == "__main__":
    unittest.main()

