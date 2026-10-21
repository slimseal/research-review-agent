"""All bibliographic objects in this file are FICTIONAL TEST DATA, not evidence."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_review_agent.citations.pipeline import CitationPipeline, initialize_lab
from research_review_agent.citations.providers import CitationProviders, parse_page, fail
from research_review_agent.citations.cli import execute
from research_review_agent.cli import build_parser
from research_review_agent.scholarly.registry import PaperRegistry
from research_review_agent.scholarly.transport import HttpResponse, HttpTransport
from research_review_agent.state import load_state, persist_state, write_json_atomic
from research_review_agent.project import initialize_project, approve_protocol
from research_review_agent.validation import validate_phase
from research_review_agent.workflow import transition_phase, evaluate_gates, phase_context
from test_scholarly_discovery import candidate, SequenceAdapter, fetched_page
import test_scholarly_discovery as discovery_tests
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline


SEED = "10.5555/fictional.seed"
OTHER = "10.5555/fictional.other"


def work(doi=OTHER, title="Fictional 测试 reference", year=2020, kind="journal-article"):
    return {"message": {"DOI": doi, "title": [title], "author": [{"family": "Fixture", "given": "A"}], "issued": {"date-parts": [[year]]}, "type": kind}}


def refs(*items):
    return {"message": {"DOI": SEED, "reference": list(items)}}


def oa(identifier="W999999999", doi=OTHER, cursor=None):
    return {"results": [{"id": "https://openalex.org/" + identifier, "title": "Fictional citation 测试", "doi": doi, "publication_year": 2020}], "meta": {"next_cursor": cursor}}


class QueueTransport:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        if not self.outcomes:
            raise AssertionError("No fixture response left; accidental external request")
        item = self.outcomes.pop(0)
        if isinstance(item, BaseException):
            raise item
        body = item if isinstance(item, bytes) else json.dumps(item, ensure_ascii=False).encode()
        return HttpResponse(200, {"content-type": "application/json"}, body, kwargs["url"])


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "lab"
        initialize_lab(self.root)
        self.seed_id = PaperRegistry(self.root).register(candidate(provider="crossref", provider_id=SEED, title="Fictional seed", authors=["Fixture"], year=2019, doi=SEED)).paper_id

    def tearDown(self):
        self.temp.cleanup()

    def setup_plan(self, outcomes=(), plan=None, **limits):
        self.transport = QueueTransport(*outcomes)
        p = CitationPipeline(self.root, CitationProviders(self.transport))
        if any(x["provider"] == "openalex" for x in plan or []):
            p.registry.register(candidate(provider="openalex", provider_id="https://openalex.org/W999999990", title="Fictional seed", authors=["Fixture"], year=2019, doi=SEED))
        config = {"selected_paper_ids": [self.seed_id], "selection_reason": {self.seed_id: "Fictional test only"}, "provider_plan": plan or [{"provider": "crossref", "direction": "backward"}], **limits}
        p.register_seeds(config, "fixture-selector")
        p.approve_seeds("fixture-selector", "Synthetic infrastructure selection", pilot=True)
        return p

    def test_backward_direction_unicode_doi_normalization_and_raw(self):
        p = self.setup_plan([refs({"DOI": "https://doi.org/10.5555/FICTIONAL.OTHER"}), work()])
        run = p.start("crossref", "backward")
        self.assertEqual(run["unique_new_count"], 1)
        edge = next(iter(p.data["edges"].values()))
        self.assertEqual(edge["citing_identity"], self.seed_id)
        self.assertNotEqual(edge["cited_identity"], self.seed_id)
        self.assertEqual(len(run["raw_response_reference"]), 2)
        self.assertTrue(p.validate()["valid"])
        self.assertIn("测试", (self.root / "03_library/PAPER_REGISTRY.csv").read_text())

    def test_forward_pagination_resume_idempotence(self):
        plan = [{"provider": "openalex", "direction": "forward"}]
        p = self.setup_plan([oa(cursor="next"), fail("TIMEOUT", "fixture", "openalex"), {"results": [], "meta": {}}], plan)
        with patch.dict("os.environ", {"OPENALEX_API_KEY": "fixture-secret"}):
            run = p.start("openalex", "forward")
            self.assertEqual(run["status"], "partial_failure")
            result = p.resume(run["expansion_run_id"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["unique_new_count"], 1)
        self.assertEqual(next(iter(p.data["edges"].values()))["cited_identity"], self.seed_id)
        self.assertNotIn("fixture-secret", json.dumps(p.data))

    def test_unstructured_and_unknown_ids_preserved(self):
        p = self.setup_plan([refs({"unstructured": "Fictional book, no DOI"}, "原始无标识参考文献", {"DOI": "not-a-doi"}, None)])
        run = p.start("crossref", "backward")
        self.assertEqual(run["unresolved_count"], 4)
        self.assertEqual(len(p.data["edges"]), 3)
        self.assertEqual(len(p.registry.data["records"]), 1)

    def test_missing_reference_list_not_empty_success(self):
        p = self.setup_plan([{"message": {"DOI": SEED}}])
        run = p.start("crossref", "backward")
        self.assertIn("REFERENCE_LIST_UNAVAILABLE", run["coverage_limitations"])

    def test_success_empty_not_no_references_claim(self):
        p = self.setup_plan([refs()])
        run = p.start("crossref", "backward")
        self.assertEqual(run["status"], "complete_empty")
        self.assertIn("SUCCESS_EMPTY_INDEX_RESULT", run["coverage_limitations"])

    def test_duplicate_edges_repeated_runs_stable_ids(self):
        p = self.setup_plan([refs({"DOI": OTHER}, {"DOI": OTHER}), work(), refs({"DOI": OTHER})])
        first = p.start("crossref", "backward")
        second = p.start("crossref", "backward")
        self.assertEqual((first["unique_new_count"], first["duplicate_count"], second["unique_new_count"]), (1, 1, 0))
        self.assertEqual(len(p.data["edges"]), 1)
        self.assertEqual(len(next(iter(p.data["edges"].values()))["provenance"]), 3)
        self.assertEqual(len(p.registry.data["records"]), 2)

    def test_cross_provider_reconciliation_and_separate_graph_provenance(self):
        plan = [{"provider": "crossref", "direction": "backward"}, {"provider": "opencitations", "direction": "backward"}]
        p = self.setup_plan([refs({"DOI": OTHER}), work(), [{"oci": "fictional-1", "citing": "doi:" + SEED, "cited": "doi:" + OTHER}]], plan)
        p.start("crossref", "backward")
        run = p.start("opencitations", "backward")
        self.assertEqual(run["duplicate_count"], 1)
        self.assertEqual(len(p.data["edges"]), 1)
        self.assertEqual(len(next(iter(p.data["edges"].values()))["provenance"]), 2)

    def test_opencitations_forward_and_multi_doi_not_collapsed(self):
        p = self.setup_plan([[{"oci": "fictional-2", "citing": "doi:" + OTHER + " doi:10.5555/fictional.version", "cited": "doi:" + SEED}]], [{"provider": "opencitations", "direction": "forward"}])
        run = p.start("opencitations", "forward")
        self.assertEqual(run["unresolved_count"], 1)
        self.assertEqual(next(iter(p.data["edges"].values()))["cited_identity"], self.seed_id)
        self.assertEqual(next(iter(p.data["candidates"].values()))["identity_resolution_status"], "ambiguous_multiple_dois")

    def test_wrong_seed_relation_is_not_an_edge(self):
        p = self.setup_plan([[{"oci": "fixture", "citing": "doi:" + OTHER, "cited": "doi:" + OTHER}]], [{"provider": "opencitations", "direction": "forward"}])
        p.start("opencitations", "forward")
        self.assertEqual(len(p.data["edges"]), 0)
        self.assertEqual(len(p.data["candidates"]), 1)

    def test_self_citation_is_not_a_new_paper(self):
        p = self.setup_plan([refs({"DOI": SEED})])
        run = p.start("crossref", "backward")
        self.assertEqual((run["unique_new_count"], run["duplicate_count"]), (0, 1))
        edge = next(iter(p.data["edges"].values()))
        self.assertEqual(edge["citing_identity"], edge["cited_identity"])

    def test_seed_unknown_rejected_and_approval_required(self):
        p = self.setup_plan()
        config = dict(p.seed())
        config["selected_paper_ids"] = ["UNKNOWN"]
        with self.assertRaisesRegex(ValueError, "INVALID_SEEDS"):
            p.register_seeds(config, "fixture")
        p.seed()["approval_status"] = "pending_human_review"
        with self.assertRaisesRegex(ValueError, "SEED_APPROVAL_REQUIRED"):
            p.start("crossref", "backward")
        self.assertFalse(self.transport.calls)

    def test_changed_seed_set_marks_stale(self):
        p = self.setup_plan([refs()])
        run = p.start("crossref", "backward")
        p.register_seeds(dict(p.seed()), "fixture")
        p.approve_seeds("fixture", "new selection", pilot=True)
        self.assertEqual(p.effective(run)["effective_status"], "stale")
        with self.assertRaisesRegex(ValueError, "STALE_EXPANSION_RUN"):
            p.resume(run["expansion_run_id"])

    def test_hash_tamper_blocks_replay(self):
        p = self.setup_plan([refs({"DOI": SEED})])
        run = p.start("crossref", "backward")
        (self.root / run["raw_response_reference"][0]).write_text("{}")
        self.assertFalse(p.validate()["valid"])
        with self.assertRaises(RuntimeError):
            p.resume(run["expansion_run_id"])

    def test_reversed_edge_fails_validation(self):
        p = self.setup_plan([refs({"unstructured": "Fictional"})])
        p.start("crossref", "backward")
        edge = next(iter(p.data["edges"].values()))
        edge["citing_identity"], edge["cited_identity"] = edge["cited_identity"], edge["citing_identity"]
        self.assertFalse(p.validate()["valid"])

    def test_cursor_stall_preserves_first_page(self):
        p = self.setup_plan([oa(cursor="again"), oa(cursor="again")], [{"provider": "openalex", "direction": "forward"}])
        with patch.dict("os.environ", {"OPENALEX_API_KEY": "fixture"}):
            run = p.start("openalex", "forward")
        self.assertEqual(run["stop_reason"], "CURSOR_STALLED")
        self.assertEqual(run["discovered_count"], 2)
        self.assertEqual(len(p.data["edges"]), 1)

    def test_missing_openalex_key_stops_pagination_honestly(self):
        p = self.setup_plan([oa(cursor="next")], [{"provider": "openalex", "direction": "forward"}])
        with patch.dict("os.environ", {}, clear=True):
            run = p.start("openalex", "forward")
        self.assertEqual(run["stop_reason"], "REQUIRES_API_KEY")
        self.assertEqual(len(self.transport.calls), 1)

    def test_all_transport_failures_remain_failures(self):
        for code in ["NETWORK_UNAVAILABLE", "AUTHENTICATION_FAILED", "ACCESS_FORBIDDEN", "HTTP_RATE_LIMITED", "HTTP_SERVER_ERROR", "QUOTA_EXHAUSTED", "TIMEOUT"]:
            with self.subTest(code=code):
                p = self.setup_plan([fail(code, "Fictional failure", "crossref")])
                result = p.start("crossref", "backward")
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["stop_reason"], code)
                self.assertEqual(len(self.transport.calls), 1)

    def test_malformed_bytes_preserved_not_success(self):
        p = self.setup_plan([b"not JSON"])
        run = p.start("crossref", "backward")
        self.assertEqual(run["stop_reason"], "MALFORMED_RESPONSE")
        self.assertEqual((self.root / run["raw_response_reference"][0]).read_bytes(), b"not JSON")

    def test_candidate_limit_retains_unprocessed_raw(self):
        p = self.setup_plan([refs({"unstructured": "Fictional A"}, {"unstructured": "Fictional B"})], max_candidates=1)
        run = p.start("crossref", "backward")
        self.assertEqual(run["stop_reason"], "CANDIDATE_LIMIT")
        self.assertEqual(run["pages"][0]["provider_row_count"], 2)
        self.assertEqual(run["discovered_count"], 1)

    def test_request_limit_preserves_unresolved_doi(self):
        p = self.setup_plan([refs({"DOI": OTHER})], max_requests=1)
        run = p.start("crossref", "backward")
        self.assertEqual(run["stop_reason"], "REQUEST_LIMIT")
        self.assertEqual(run["unresolved_count"], 1)
        self.assertEqual(len(self.transport.calls), 1)

    def test_depth_and_round_accounting(self):
        p = self.setup_plan([refs({"DOI": SEED}), refs({"DOI": SEED})], expansion_depth_limit=2)
        p.start("crossref", "backward", 1)
        p.start("crossref", "backward", 2)
        self.assertEqual(p.round_usage(1), (1, 1))
        self.assertEqual(p.round_usage(2), (1, 1))
        with self.assertRaisesRegex(ValueError, "DEPTH_LIMIT"):
            p.start("crossref", "backward", 3)

    def test_interruption_after_candidate_commit_resumes_without_duplicate(self):
        p = self.setup_plan([refs({"DOI": SEED})])
        original = p.save
        def interrupt(event):
            original(event)
            if event == "citation_candidate_registered":
                raise KeyboardInterrupt("simulated power loss")
        with patch.object(p, "save", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                p.start("crossref", "backward")
        restored = CitationPipeline(self.root, CitationProviders(QueueTransport()))
        result = restored.resume(next(iter(restored.data["runs"])))
        self.assertEqual(result["discovered_count"], 1)
        self.assertEqual(len(next(iter(restored.data["edges"].values()))["provenance"]), 1)

    def test_recovery_restores_existing_journal_and_views(self):
        p = self.setup_plan([refs({"DOI": SEED})])
        run = p.start("crossref", "backward")
        (self.root / ".review/state.json").write_text("broken")
        result = execute(build_parser().parse_args(["citations-recover", "--project", str(self.root)]))
        self.assertTrue(result["validation"]["valid"])
        self.assertIn(run["expansion_run_id"], load_state(self.root)["citation_data"]["runs"])

    def test_registry_document_fields_and_manual_columns_preserved(self):
        path = self.root / "03_library/PAPER_REGISTRY.csv"
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        rows[0].update(pdf_path="papers/authorized.pdf", fulltext_available="true", license="unknown", sha256="fixture-hash", custom="manual", extension_json='{"custom_extension": "keep"}')
        PaperRegistry._write_csv_atomic(path, list(rows[0]), rows)
        p = self.setup_plan([refs({"DOI": OTHER}), work()])
        p.start("crossref", "backward")
        with path.open() as handle:
            after = list(csv.DictReader(handle))[0]
        self.assertEqual(after["pdf_path"], "papers/authorized.pdf")
        self.assertEqual(after["custom"], "manual")
        self.assertEqual(json.loads(after["extension_json"])["custom_extension"], "keep")

    def test_legacy_ids_reserved_not_silently_migrated(self):
        path = self.root / "03_library/PAPER_REGISTRY.csv"
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        legacy = dict(rows[0], paper_id="P0000002", doi="10.5555/fictional.legacy", title="Legacy fictional")
        PaperRegistry._write_csv_atomic(path, list(rows[0]), rows + [legacy])
        p = self.setup_plan([refs({"DOI": OTHER}, {"DOI": legacy["doi"]}), work()])
        p.start("crossref", "backward")
        self.assertIn("P0000003", p.registry.data["records"])
        self.assertNotIn("P0000002", p.registry.data["records"])
        self.assertTrue(any(c["identity_resolution_status"] == "legacy_identity_requires_review" for c in p.data["candidates"].values()))

    def test_preprints_not_merged_and_ambiguity_preserved(self):
        p = self.setup_plan([refs({"DOI": OTHER}, {"DOI": "10.5555/fictional.preprint"}), work(), work("10.5555/fictional.preprint", kind="posted-content")])
        run = p.start("crossref", "backward")
        self.assertEqual(run["unique_new_count"], 2)
        versions = [r for r in p.registry.data["records"].values() if r["doi"] != SEED]
        self.assertTrue(all(r["related_versions"] for r in versions))

    def test_ambiguous_title_author_year_not_merged(self):
        p = self.setup_plan([refs({"DOI": OTHER}, {"DOI": "10.5555/fictional.ambiguous"}), work(kind="unknown"), work("10.5555/fictional.ambiguous", kind="unknown")])
        run = p.start("crossref", "backward")
        self.assertEqual(run["unresolved_count"], 1)
        self.assertEqual(run["unique_new_count"], 1)

    def test_lab_cannot_approve_phase_or_nest_in_real_project(self):
        p = self.setup_plan([refs()])
        p.start("crossref", "backward")
        self.assertFalse(p.completion()["valid"])
        with self.assertRaisesRegex(ValueError, "LAB_CANNOT_APPROVE"):
            p.review("fixture", "note", "limits", "human_stop")
        (self.root / "00_protocol").mkdir()
        (self.root / "00_protocol/PROTOCOL.json").write_text("{}")
        with self.assertRaises(ValueError):
            p.authorize()
        with self.assertRaises(ValueError):
            initialize_lab(self.root / "nested")

    def official(self):
        helper = discovery_tests.ScholarlyDiscoveryTests()
        helper.repo, helper.temp = Path(__file__).resolve().parents[1], self.temp
        root = helper.ready_project()
        request = helper.request(root)
        ScholarlyDiscoveryPipeline(root, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])}).run_search(request)
        transition_phase(root, 3, "completed")
        transition_phase(root, 4, "in_progress")
        p = CitationPipeline(root, CitationProviders(QueueTransport()))
        sid = p.eligible()[0]["paper_id"]
        seed = p.registry.data["records"][sid]
        p.providers = CitationProviders(QueueTransport({"message": {"DOI": seed["doi"], "reference": []}}))
        p.register_seeds({"selected_paper_ids": [sid], "selection_reason": {sid: "Fictional test relevance"}, "provider_plan": [{"provider": "crossref", "direction": "backward"}]}, "fixture-human")
        p.approve_seeds("fixture-human", "Synthetic test approval")
        return p

    def test_phase4_requires_human_review_and_preserves_downstream_gates(self):
        p = self.official()
        p.start("crossref", "backward")
        self.assertFalse(p.completion()["valid"])
        with self.assertRaises(ValueError):
            transition_phase(p.root, 4, "completed")
        self.assertTrue(p.review("fictional-human", "Reviewed fixture", "Empty index is not empty literature", "planned_paths_executed")["valid"])
        transition_phase(p.root, 4, "completed")
        self.assertFalse(validate_phase(p.root, 4))
        for target, gate in [(7, "gate-1-screening-before-reading"), (15, "gate-2-evidence-before-drafting"), (12, "gate-3-claims-before-gap")]:
            self.assertEqual(evaluate_gates(p.root, target)[gate]["status"], "fail")
        self.assertTrue(validate_phase(p.root, 5))
        self.assertTrue(validate_phase(p.root, 6))

    def test_changed_protocol_without_version_change_stales_results(self):
        p = self.official()
        run = p.start("crossref", "backward")
        path = p.root / "00_protocol/PROTOCOL.json"
        data = json.loads(path.read_text())
        data["research_question"] += " changed"
        write_json_atomic(path, data)
        self.assertEqual(p.effective(run)["effective_status"], "stale")
        self.assertFalse(p.completion()["valid"])

    def test_unapproved_protocol_blocks_before_any_network(self):
        root = Path(self.temp.name) / "unapproved"
        initialize_project(root, "Fictional protocol", "testing")
        p = CitationPipeline(root, CitationProviders(QueueTransport()))
        with self.assertRaisesRegex(ValueError, "PHASE4_AUTHORIZATION"):
            p.register_seeds({}, "fixture")

    def test_schema_v1_v2_and_no_skills_procedure(self):
        p = self.official()
        for version in ["1.0.0", "2.0.0"]:
            protocol = p.root / "00_protocol/PROTOCOL.json"
            value = json.loads(protocol.read_text())
            value["schema_version"] = version
            write_json_atomic(protocol, value)
            self.assertEqual(CitationPipeline(p.root).context()["schema_version"], version)
            context = phase_context(p.root, 4)
            self.assertIn("Citation", json.dumps(context))
        repo = Path(__file__).resolve().parents[1]
        self.assertFalse(list((repo / "research_review_agent").rglob("SKILL.md")))
        self.assertFalse((repo / ".agents/skills").exists())

    def test_modified_exports_block_completion_and_downstream(self):
        p = self.official()
        p.start("crossref", "backward")
        p.review("fixture", "Reviewed synthetic data", "Accepted fixture limitations", "human_stop")
        transition_phase(p.root, 4, "completed")
        (p.root / "02_discovery/CITATION_EDGES.csv").write_text("modified")
        self.assertFalse(p.validate()["valid"])
        self.assertEqual(evaluate_gates(p.root, 5)["citation-phase4-artifacts-current"]["status"], "fail")

    def test_literal_unstructured_doi_and_year_tokens_not_invented(self):
        p = self.setup_plan([refs({"unstructured": "Fictional 2020 doi:10.5555/fictional.other"}), work()])
        run = p.start("crossref", "backward")
        self.assertEqual(run["resolved_count"], 1)
        self.assertEqual(next(iter(p.data["candidates"].values()))["literal_parse"]["year_tokens"], ["2020"])

    def test_openalex_seed_identity_lookup_is_provenanced(self):
        p = self.setup_plan([{"id": "https://openalex.org/W999999990", "doi": SEED}, oa()], [{"provider": "openalex", "direction": "forward"}])
        p.registry.data["records"][self.seed_id]["provider_ids"].pop("openalex")
        p.registry.save()
        run = p.start("openalex", "forward")
        self.assertEqual(run["request_count"], 2)
        self.assertIn(self.seed_id, run["seed_identity_pages"])
        self.assertIn("cites%3AW999999990", self.transport.calls[1]["url"])

    def test_human_review_invalidated_by_another_run(self):
        p = self.official()
        p.start("crossref", "backward")
        self.assertTrue(p.review("fixture", "review", "limits", "human_stop")["valid"])
        p.providers = CitationProviders(QueueTransport(fail("TIMEOUT", "Fixture", "crossref")))
        p.start("crossref", "backward")
        self.assertFalse(p.completion()["valid"])

    def test_nonimplemented_related_cannot_become_edges(self):
        p = self.setup_plan()
        with self.assertRaises(ValueError):
            p.start("openalex", "related")
        self.assertFalse(p.data["edges"])

    def test_metadata_not_found_keeps_unresolved_reference(self):
        p = self.setup_plan([refs({"DOI": OTHER}), fail("IDENTIFIER_NOT_FOUND", "Fixture", "crossref")])
        run = p.start("crossref", "backward")
        self.assertEqual(run["unresolved_count"], 1)
        self.assertIn("METADATA_MISSING:" + OTHER, run["warnings"])


if __name__ == "__main__":
    unittest.main()
