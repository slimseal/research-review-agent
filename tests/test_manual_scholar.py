"""Synthetic manual records only; no genuine Scholar search or human approval."""
import contextlib
import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_review_agent.cli import main
from research_review_agent.scholarly.access import SEARCH_PROVIDERS
from research_review_agent.scholarly.manual_scholar import FIELDS, RELATIVE_DIR, manual_coverage, prepare
from research_review_agent.scholarly.source_plan import source_plan, coverage_report


PLAN = {"research_question": "Fictional fixture question?", "suitability": "optional",
        "rationale": "Fixture only", "coverage_gaps": "Unexamined sources",
        "year_filter": "pending confirmation", "stop_rule": "20 positions per query, no extra branches",
        "queries": [{"id": f"Q{i}", "query": f'"fictional topic {i}"', "purpose": "Fixture only",
                     "max_results_to_check": 20} for i in range(1, 4)]}


class ManualScholarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.output = self.project / RELATIVE_DIR

    def sessions(self, change=None):
        row = {"session_id": "FICTIONAL-S1", "query_id": "Q1", "exact_query": PLAN["queries"][0]["query"],
               "date": "2026-10-22", "year_filter": "none", "sort": "relevance", "first_result": 1,
               "last_result": 10, "checked_count": 10, "stop_reason": "fixture budget", "record_source": "synthetic test only"}
        row.update(change or {})
        (self.output / "SESSIONS.json").write_text(json.dumps({"sessions": [row]}))

    def candidate(self, change=None):
        row = dict.fromkeys(FIELDS, "")
        row.update(candidate_id="FICTIONAL-C1", session_id="FICTIONAL-S1", title="Fictional candidate",
                   authors="Fictional author", year="2099", url="https://example.invalid/fictional",
                   source="google_scholar", verification_status="unverified", duplicate_status="unresolved",
                   needs_screening="true", import_status="not_imported")
        row.update(change or {})
        with (self.output / "RESULTS.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(row)

    def test_preparation_is_offline_not_performed_and_non_overwriting(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            result = prepare(PLAN, self.output)
            self.assertEqual(result["network_requests"], 0)
            self.assertEqual(manual_coverage(self.project)["status"], "not_performed")
        with self.assertRaises(FileExistsError):
            prepare(PLAN, self.output)
        self.assertFalse((self.project / "03_library").exists())
        self.assertFalse((self.project / "02_discovery/search_runs").exists())

    def test_query_contract(self):
        for mutation in ({"queries": []}, {"suitability": "approved"}, {"research_question": ""}):
            with self.assertRaises(ValueError):
                prepare({**PLAN, **mutation}, self.output)
        modified = copy.deepcopy(PLAN)
        modified["queries"][0]["query"] = '"unclosed'
        with self.assertRaises(ValueError):
            prepare(modified, self.output)
        self.assertFalse(self.output.exists())

    def test_plans_and_proposals_never_prove_execution(self):
        plan = source_plan("teaching", include=["google_scholar"])
        self.assertEqual(plan["sources"], [])
        self.assertTrue(plan["manual_supplements"][0]["proposed"])
        self.assertNotIn("google_scholar", SEARCH_PROVIDERS)
        plan["manual_supplements"][0]["status"] = "completed"
        self.assertEqual(coverage_report(self.project, plan)["manual_supplements"][0]["status"], "not_performed")
        self.assertFalse(source_plan("teaching", exclude=["google_scholar"])["manual_supplements"][0]["proposed"])
        self.assertFalse(source_plan("teaching", include=["crossref"])["manual_supplements"][0]["proposed"])

    def test_manual_counts_do_not_become_api_counts(self):
        prepare(PLAN, self.output)
        before = coverage_report(self.project)
        self.sessions()
        self.candidate()
        after = coverage_report(self.project)
        for key in ("providers", "raw_result_count", "canonical_paper_count", "http_requests_accounted"):
            self.assertEqual(before[key], after[key])
        report = after["manual_supplements"][0]
        self.assertEqual(report["status"], "performed_as_reported")
        self.assertEqual(report["candidate_observations"], 1)
        self.assertEqual(report["registry_imports"], 0)
        self.assertEqual(report["unperformed_query_ids"], ["Q2", "Q3"])
        self.assertEqual(report["unresolved_identity_observations"], 1)
        self.assertEqual(report["unresolved_duplicate_observations"], 1)
        self.assertEqual(report["completed_scope"], "not_assessed")

    def test_unperformed_candidates_invalid(self):
        prepare(PLAN, self.output)
        self.candidate()
        self.assertEqual(manual_coverage(self.project)["status"], "invalid_records")

    def test_zero_results_must_have_actual_session_and_cannot_have_candidates(self):
        prepare(PLAN, self.output)
        self.sessions({"first_result": 0, "last_result": 0, "checked_count": 0,
                       "stop_reason": "observed_zero_results"})
        self.assertEqual(manual_coverage(self.project)["status"], "performed_as_reported")
        self.candidate()
        self.assertEqual(manual_coverage(self.project)["status"], "invalid_records")

    def test_bad_provenance_scope_dates_and_plan_mismatch(self):
        prepare(PLAN, self.output)
        for bad in ({"date": "tomorrow"}, {"record_source": ""}, {"exact_query": "other"},
                    {"last_result": 21}, {"checked_count": 11}, {"first_result": True}):
            self.sessions(bad)
            self.assertEqual(manual_coverage(self.project)["status"], "invalid_records", bad)

    def test_no_claimed_import_approval_or_unsupported_verification(self):
        prepare(PLAN, self.output)
        self.sessions()
        for bad in ({"import_status": "imported"}, {"needs_screening": "false"},
                    {"verification_status": "verified"}, {"duplicate_status": "confirmed_unique"}):
            self.candidate(bad)
            self.assertEqual(manual_coverage(self.project)["status"], "invalid_records", bad)

    def test_corrupt_logs_are_not_success_or_empty_search(self):
        prepare(PLAN, self.output)
        (self.output / "SESSIONS.json").write_text("{")
        result = manual_coverage(self.project)
        self.assertEqual(result["status"], "invalid_records")
        self.assertTrue(result["validation_errors"])

    def test_duplicate_session_and_cumulative_budget(self):
        prepare(PLAN, self.output)
        self.sessions()
        path = self.output / "SESSIONS.json"
        s = json.loads(path.read_text())["sessions"][0]
        for rows in ([s, s], [s, {**s, "session_id": "FICTIONAL-S2"}, {**s, "session_id": "FICTIONAL-S3"}]):
            path.write_text(json.dumps({"sessions": rows}))
            self.assertEqual(manual_coverage(self.project)["status"], "invalid_records")

    def test_api_runs_retained_independent_of_manual_records(self):
        runs = self.project / "02_discovery/search_runs"
        runs.mkdir(parents=True)
        (runs / "fixture.json").write_text(json.dumps({"search_run_id": "FICTIONAL-RUN", "provider": "crossref",
            "retrieval_status": "complete_empty", "retrieved_count": 0, "exact_query": "fixture only"}))
        prepare(PLAN, self.output)
        self.sessions()
        self.candidate()
        report = coverage_report(self.project)
        self.assertEqual(report["providers"]["crossref"]["runs"][0]["search_run_id"], "FICTIONAL-RUN")
        self.assertEqual(report["raw_result_count"], 0)
        self.assertEqual(report["manual_supplements"][0]["candidate_observations"], 1)

    def test_cli_generates_real_files_without_transport(self):
        input_path = self.project / "input.json"
        input_path.write_text(json.dumps(PLAN))
        with contextlib.redirect_stdout(io.StringIO()), patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            self.assertEqual(main(["scholar-prepare", "--plan", str(input_path), "--output", str(self.output)]), 0)
        self.assertIn("Cited by", (self.output / "CHECKLIST_ZH.md").read_text())
        self.assertEqual(len(list(self.output.iterdir())), 5)


if __name__ == "__main__":
    unittest.main()
