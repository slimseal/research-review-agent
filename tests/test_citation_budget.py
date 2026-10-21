"""FICTIONAL metadata only, isolated TemporaryDirectory labs; no real HTTP."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from research_review_agent.citations import budget
from research_review_agent.citations.pipeline import CitationPipeline, initialize_lab, digest
from research_review_agent.scholarly.registry import PaperRegistry
from research_review_agent.scholarly.transport import ProviderRequestError
from research_review_agent.state import load_state, persist_state, recover_state
from test_scholarly_discovery import candidate


class Crash(BaseException):
    pass


class Response(io.BytesIO):
    status = 200
    headers = {"content-type": "application/json"}


class Wire:
    def __init__(self, results):
        self.results, self.calls = list(results), []

    def __call__(self, req, timeout):
        self.calls.append(req.full_url)
        if not self.results:
            raise AssertionError("Unexpected HTTP attempt")
        item = self.results.pop(0)
        if isinstance(item, BaseException):
            raise item
        return Response(item if isinstance(item, bytes) else json.dumps(item).encode())


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "fictional-lab"
        initialize_lab(self.root)
        reg = PaperRegistry(self.root)
        self.ids = []
        for i in range(3):
            self.ids.append(reg.register(candidate(provider="openalex", provider_id=f"https://openalex.org/W999900{i}",
                title=f"FICTIONAL seed {i}", authors=["Fixture"], year=2020, doi=f"10.5555/fictional.seed{i}")).paper_id)

    def tearDown(self):
        self.temp.cleanup()

    def refs(self, i=0, n=24):
        return {"message": {"DOI": f"10.5555/fictional.seed{i}",
                            "reference": [{"DOI": f"10.5555/fictional.ref{j}"} for j in range(n)]}}

    def oa(self, n=24):
        return {"results": [{"id": f"https://openalex.org/W88880{j}", "title": f"FICTIONAL citing {j}",
                              "doi": f"10.5555/fictional.citing{j}", "publication_year": 2020} for j in range(n)],
                "meta": {"next_cursor": "UNAUTHORIZED_SECOND_PAGE", "count": 999}}

    def setup_plan(self, results=(), count=1):
        self.wire = Wire(results)
        p = CitationPipeline(self.root, budget_opener=self.wire)
        self.config = {"selected_paper_ids": self.ids[:count], "selection_reason": {pid: "FICTIONAL test only" for pid in self.ids},
                       "provider_plan": budget.PLAN, "expansion_depth_limit": 1, "max_requests": 6, "max_candidates": 120,
                       "budget_policy": budget.POLICY, "expected_protocol_sha256": digest(p.context())}
        p.register_seeds(self.config, "fixture-selector")
        p.approve_seeds("fixture-selector", "FICTIONAL lab selection", True, 1, p.seed()["plan_sha256"])
        return p

    def reopen(self):
        return CitationPipeline(self.root, budget_opener=self.wire)

    def test_crossref_full_raw_first20_unresolved_no_lookup(self):
        p = self.setup_plan([self.refs(n=81)])
        r = p.start("crossref", "backward")
        page = r["pages"][0]
        self.assertEqual((page["provider_row_count"], page["processed_count"], page["unprocessed_count"]), (81, 20, 61))
        self.assertEqual(r["unresolved_count"], 20)
        self.assertEqual(len(self.wire.calls), 1)
        self.assertEqual(len(json.loads(p.store.verify_raw_response(page["raw_response_path"], page["sha256"]))["message"]["reference"]), 81)
        self.assertTrue(p.validate()["valid"], p.validate())

    def test_openalex_one_page20_no_continuation(self):
        p = self.setup_plan([self.oa()])
        r = p.start("openalex", "forward")
        self.assertIn("per_page=20", self.wire.calls[0])
        self.assertEqual(len(self.wire.calls), 1)
        self.assertEqual(r["discovered_count"], 20)
        self.assertEqual(r["pages"][0]["returned_next_cursor_unused"], "UNAUTHORIZED_SECOND_PAGE")

    def test_six_requests_shared_120_observations_and_idempotence(self):
        p = self.setup_plan([self.refs(i) for i in range(3)] + [self.oa()] * 3, 3)
        a = p.start("crossref", "backward")
        b = p.start("openalex", "forward")
        self.assertEqual(len(self.wire.calls), 6)
        self.assertEqual(len(p.data["candidates"]), 120)
        self.assertEqual(len(p.budget_transport.inspect()), 6)
        self.assertEqual(p.start("crossref", "backward")["expansion_run_id"], a["expansion_run_id"])
        p.resume(b["expansion_run_id"])
        self.assertEqual(len(self.wire.calls), 6)
        self.assertTrue(p.validate()["valid"], p.validate())

    def test_unscoped_doi_query_blocked(self):
        p = self.setup_plan()
        with self.assertRaisesRegex(ProviderRequestError, "HTTP_SCOPE_REQUIRED"):
            p.providers.metadata("10.5555/fictional.unexpected")
        with self.assertRaisesRegex(ProviderRequestError, "HTTP_SCOPE_REQUIRED"):
            p.providers.openalex_identity("10.5555/fictional.unexpected")
        self.assertEqual(self.wire.calls, [])

    def test_wrong_url_pagination_blocked_at_transport(self):
        p = self.setup_plan()
        with patch.object(p, "resume", side_effect=Crash):
            with self.assertRaises(Crash):
                p.start("openalex", "forward")
        r = next(iter(p.data["runs"].values()))
        with p.budget_transport.scope(r, self.ids[0]), patch.dict("os.environ", {"OPENALEX_API_KEY": "fictional-test-not-a-key"}):
            with self.assertRaisesRegex(ProviderRequestError, "HTTP_REQUEST_NOT_AUTHORIZED"):
                p.providers.request("openalex", "forward", p.registry.data["records"][self.ids[0]], "second", per_page=20)
        self.assertEqual(self.wire.calls, [])

    def test_http_failure_no_retry_and_saved_error_body(self):
        error = urllib.error.HTTPError("https://fixture.invalid", 429, "limit", {}, io.BytesIO(b'{"message":"quota_exceeded"}'))
        p = self.setup_plan([error])
        r = p.start("crossref", "backward")
        self.assertEqual(r["stop_reason"], "QUOTA_EXHAUSTED")
        p.resume(r["expansion_run_id"])
        self.assertEqual(len(self.wire.calls), 1)
        self.assertEqual(p.budget_transport.inspect()[0]["response"]["http_status"], 429)

    def test_timeout_consumes_slot_blocks_all_new_sends(self):
        p = self.setup_plan([TimeoutError()])
        r = p.start("crossref", "backward")
        self.assertEqual(r["stop_reason"], "REQUEST_SEND_UNKNOWN")
        p.resume(r["expansion_run_id"])
        p.start("openalex", "forward")
        self.assertEqual(len(self.wire.calls), 1)
        self.assertFalse(p.validate()["valid"])

    def test_interrupt_before_wire_no_blind_resend(self):
        p = self.setup_plan([self.refs()])
        with patch.object(budget, "fault", side_effect=lambda stage: (_ for _ in ()).throw(Crash()) if stage == "after_reservation" else None):
            with self.assertRaises(Crash):
                p.start("crossref", "backward")
        recover_state(self.root)
        p = self.reopen()
        r = p.resume(next(iter(p.data["runs"])))
        self.assertEqual(r["stop_reason"], "REQUEST_SEND_UNKNOWN")
        self.assertEqual(len(self.wire.calls), 0)
        self.assertEqual(r["request_count"], 1)

    def test_interrupt_after_wire_before_receipt_never_resends(self):
        p = self.setup_plan([self.refs()])
        with patch.object(budget, "fault", side_effect=lambda stage: (_ for _ in ()).throw(Crash()) if stage == "after_wire_before_receipt" else None):
            with self.assertRaises(Crash):
                p.start("crossref", "backward")
        p = self.reopen()
        self.assertEqual(p.resume(next(iter(p.data["runs"]))) ["stop_reason"], "REQUEST_SEND_UNKNOWN")
        self.assertEqual(len(self.wire.calls), 1)

    def test_interrupt_after_receipt_replays_without_network(self):
        p = self.setup_plan([self.refs()])
        with patch.object(budget, "fault", side_effect=lambda stage: (_ for _ in ()).throw(Crash()) if stage == "after_response_receipt" else None):
            with self.assertRaises(Crash):
                p.start("crossref", "backward")
        recover_state(self.root)
        p = self.reopen()
        r = p.resume(next(iter(p.data["runs"])))
        self.assertEqual((r["discovered_count"], len(self.wire.calls)), (20, 1))
        self.assertTrue(p.validate()["valid"], p.validate())

    def test_seed_replacement_and_downgrade_cannot_reset_budget(self):
        p = self.setup_plan([self.refs()])
        p.start("crossref", "backward")
        with self.assertRaisesRegex(ValueError, "FROZEN_AFTER_RUN_START"):
            p.register_seeds(self.config, "fixture")
        with self.assertRaisesRegex(ValueError, "DOWNGRADE_FORBIDDEN"):
            p.register_seeds({k: v for k, v in self.config.items() if k != "budget_policy"}, "fixture")

    def test_version_hash_and_identity_conflicts(self):
        p = self.setup_plan()
        with self.assertRaisesRegex(ValueError, "VERSION_OR_HASH_CONFLICT"):
            p.approve_seeds("fixture", "fixture", True, 9, p.seed()["plan_sha256"])
        p.registry.data["records"][self.ids[0]]["provider_ids"]["openalex"] = ["https://openalex.org/W111111"]
        with self.assertRaisesRegex(ValueError, "IDENTITY_CONFLICT"):
            p.start("crossref", "backward")
        self.assertEqual(self.wire.calls, [])

    def test_stale_instance_cannot_write_or_send(self):
        p = self.setup_plan()
        state = load_state(self.root)
        persist_state(self.root, state, "fictional_concurrent_writer")
        with self.assertRaisesRegex(ValueError, "STATE_VERSION_CONFLICT"):
            p.start("crossref", "backward")
        self.assertEqual(self.wire.calls, [])

    def test_no_redirect_handler(self):
        self.assertIsNone(budget.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://fixture.invalid"))

    def test_local_registry_resolution(self):
        data = self.refs(n=1)
        data["message"]["reference"][0]["DOI"] = "10.5555/fictional.seed1"
        p = self.setup_plan([data])
        r = p.start("crossref", "backward")
        self.assertEqual((r["resolved_count"], r["duplicate_count"], len(self.wire.calls)), (1, 1, 1))

    def test_preflight_has_no_side_effects(self):
        p = self.setup_plan()
        before = load_state(self.root)
        result = budget.preflight(p)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["human_approved"])
        self.assertEqual(load_state(self.root), before)
        self.assertEqual(self.wire.calls, [])

    def test_raw_tamper_blocks_resume(self):
        p = self.setup_plan([self.refs()])
        r = p.start("crossref", "backward")
        # Deliberate corruption in a disposable fictional directory only.
        (self.root / r["pages"][0]["raw_response_path"]).write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError, "CHECKSUM_MISMATCH"):
            p.resume(r["expansion_run_id"])
        self.assertEqual(len(self.wire.calls), 1)

    def test_budget_exhaustion_at_wire_boundary(self):
        p = self.setup_plan()
        with patch.object(p, "resume", side_effect=Crash):
            with self.assertRaises(Crash):
                p.start("crossref", "backward")
        run = next(iter(p.data["runs"].values()))
        # Boundary unit test only: six prior, complete reservations.
        entries = [{"directory": f"fictional-{i}", "status": "response_saved"} for i in range(6)]
        with p.budget_transport.scope(run, self.ids[0]), patch.object(p.budget_transport, "inspect", return_value=entries):
            with self.assertRaisesRegex(ProviderRequestError, "REQUEST_LIMIT"):
                p.providers.request("crossref", "backward", p.registry.data["records"][self.ids[0]])
        self.assertEqual(self.wire.calls, [])

    def test_interrupt_after_candidate_commit_is_idempotent(self):
        p = self.setup_plan([self.refs()])
        save = p.save
        def stop(event):
            save(event)
            if event == "citation_candidate_registered":
                raise Crash()
        with patch.object(p, "save", side_effect=stop):
            with self.assertRaises(Crash):
                p.start("crossref", "backward")
        recover_state(self.root)
        p = self.reopen()
        r = p.resume(next(iter(p.data["runs"])))
        self.assertEqual((r["discovered_count"], len(p.data["candidates"]), len(self.wire.calls)), (20, 20, 1))
        self.assertTrue(p.validate()["valid"], p.validate())

    def test_invalid_and_duplicate_positions_still_consume_limit(self):
        data = self.refs(n=30)
        data["message"]["reference"][:3] = [None, {"DOI": "10.5555/fictional.seed1"}, {"DOI": "10.5555/fictional.seed1"}]
        p = self.setup_plan([data])
        r = p.start("crossref", "backward")
        self.assertEqual(r["discovered_count"], 20)
        self.assertEqual(r["duplicate_count"], 2)
        self.assertEqual(r["pages"][0]["unprocessed_count"], 10)

    def test_malformed_response_retained_not_zero_result(self):
        p = self.setup_plan([b'not-json'])
        r = p.start("crossref", "backward")
        self.assertEqual(r["stop_reason"], "MALFORMED_RESPONSE")
        self.assertNotEqual(r["status"], "complete_empty")
        p.resume(r["expansion_run_id"])
        self.assertEqual(len(self.wire.calls), 1)

    def test_invalid_limits_and_protocol_conflict_before_network(self):
        p = self.setup_plan()
        for change in ({"max_requests": 60}, {"expansion_depth_limit": 2}, {"expected_protocol_sha256": "wrong"}):
            with self.assertRaises(ValueError):
                p.register_seeds({**self.config, **change}, "fixture")
        self.assertEqual(self.wire.calls, [])

    def test_conflicting_operation_lock_blocks_before_request(self):
        import threading
        from research_review_agent.amendments import project_lock
        p = self.setup_plan()
        errors = []
        def conflict():
            try:
                p.start("crossref", "backward")
            except ValueError as exc:
                errors.append(str(exc))
        with project_lock(self.root):
            thread = threading.Thread(target=conflict)
            thread.start()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors)
        self.assertEqual(self.wire.calls, [])

    def test_transport_retry_loop_cannot_send_twice(self):
        from research_review_agent.scholarly.transport import HttpTransport
        p = self.setup_plan([TimeoutError()])
        with patch.object(p, "resume", side_effect=Crash):
            with self.assertRaises(Crash):
                p.start("crossref", "backward")
        run = next(iter(p.data["runs"].values()))
        def wrapper(req, timeout):
            return p.budget_transport.get(provider="crossref", url=req.full_url, headers={})
        transport = HttpTransport(opener=wrapper, max_attempts=3, sleep=lambda _: None)
        url = budget.requests(p.seed(), p.registry.data["records"])[0]["url"]
        with p.budget_transport.scope(run, self.ids[0]):
            for _ in range(3):
                with self.assertRaisesRegex(ProviderRequestError, "REQUEST_SEND_UNKNOWN"):
                    transport.get(provider="crossref", url=url, headers={})
        self.assertEqual(len(self.wire.calls), 1)

    def test_restore_prior_state_does_not_erase_reserved_budget(self):
        from research_review_agent.state import write_json_atomic
        p = self.setup_plan([self.refs()])
        old_state = json.loads(json.dumps(load_state(self.root)))
        p.start("crossref", "backward")
        write_json_atomic(self.root / ".review/state.json", old_state)
        # Orphan receipt is fail-closed until existing journal recovery.
        old = self.reopen()
        with self.assertRaisesRegex(ValueError, "ORPHAN_RESERVATION"):
            old.budget_transport.inspect()
        recover_state(self.root)
        recovered = self.reopen()
        recovered.start("crossref", "backward")
        self.assertEqual(len(self.wire.calls), 1)

    def test_seed_approval_is_not_screening_or_formal_lab_approval(self):
        p = self.setup_plan([self.refs()])
        with self.assertRaisesRegex(ValueError, "PILOT_SELECTION"):
            p.approve_seeds("fixture", "fixture", False, 1, p.seed()["plan_sha256"])
        p.start("crossref", "backward")
        self.assertFalse(p.completion()["valid"])
        self.assertTrue(all(c["screening_status"] == "not_screened" for c in p.data["candidates"].values()))
