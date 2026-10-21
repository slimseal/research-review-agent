"""FICTIONAL SOFTWARE TESTS ONLY. Reviewer assertions below are NOT real human review."""
import json
import tempfile
import unittest
import contextlib
import io
import importlib.util
from pathlib import Path

import test_citations as citation_fixtures
from research_review_agent.screening.pipeline import ScreeningPipeline, initialize_lab, digest
from research_review_agent.screening.contracts import FIELDS
from research_review_agent.documents.pipeline import DocumentPipeline
from research_review_agent.project import initialize_project, approve_protocol
from research_review_agent.scholarly.registry import PaperRegistry
from research_review_agent.state import load_state, persist_state, write_json_atomic
from research_review_agent.workflow import transition_phase, evaluate_gates
from research_review_agent.validation import validate_screening, validate_phase
from tests.pdf_fixtures import pdf_bytes
from research_review_agent.cli import main as cli_main
from test_scholarly_discovery import candidate

HAS_PARSER = bool(importlib.util.find_spec("pypdf"))


def config(pipe):
    context = pipe.context()
    rules = []
    for kind in ("include", "exclude"):
        for i, text in enumerate(context.get("screening", {}).get(kind, ["Fictional " + kind + " eligibility criterion"])):
            rules.append({"id": kind + str(i), "text": text, "kind": kind, "stages": ["title", "abstract", "fulltext_eligibility"]})
    return {"rules": rules}


def proposal(pipe, packet, decision="uncertain", role="include_core", facts=None):
    return {"packet_id": packet["packet_id"], "decision": decision, "review_role": role if decision == "include" else None,
            "reason_codes": ["criterion_not_met" if decision == "exclude" else "potentially_relevant" if decision == "include" else "insufficient_information"],
            "explanation": "FICTIONAL TEST ONLY: tests control flow, not academic accuracy.", "reviewer_id": "fixture-model",
            "criteria_ids": list(pipe.rules_for(pipe.current(), packet["paper_id"], packet["stage"])),
            "source_facts": facts if facts is not None else ([{"location": "title", "quote": packet["basic_metadata"]["title"]}] if packet["stage"] != "fulltext_eligibility" else []),
            "uncertainty_flags": ["fictional_test_data"]}


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        src = self.base / "source"
        citation_fixtures.initialize_lab(src)
        registry = PaperRegistry(src)
        for i in range(3):
            registry.register(candidate(provider="crossref", provider_id=f"fictional-{i}", title=f"Fictional source {i}", authors=["Fixture"], year=2099, doi=None))
        self.root = self.base / "screening"
        initialize_lab(self.root, src, "Fictional test question, not a literature review")
        self.p = ScreeningPipeline(self.root)
        self.p.register(config(self.p), "Fictional setup")
        self.pid = self.p.current()["candidate_ids"][0]

    def tearDown(self):
        self.temp.cleanup()

    def context(self, stage="title", **kwargs):
        return self.p.stage_context(self.pid, stage, **kwargs)

    def submit(self, stage="title", decision="uncertain", **kwargs):
        return self.p.propose(proposal(self.p, self.context(stage), decision, **kwargs))

    def add_abstract(self):
        r = self.p.registry.data["records"][self.pid]
        relative = "02_discovery/raw/fictional-abstract.json"
        write_json_atomic(self.root / relative, {"message": {"title": [r["title"]], "abstract": "<jats:p>Fictional qualitative interview study.</jats:p>"}})
        r["provenance"].append({"provider": "crossref", "raw_response_path": relative, "raw_record_index": 0})
        self.p.registry.save()
        self.p = ScreeningPipeline(self.root)
        self.p.register(config(self.p), "Fictional metadata supplement before decisions")

    def import_pdf(self, text=None, version="version_of_record", scanned=False):
        path = self.base / "synthetic.pdf"
        path.write_bytes(pdf_bytes(text=text or (self.p.registry.data["records"][self.pid]["title"] + " FICTIONAL eligibility passage; synthetic version-of-record marker"), scanned=scanned))
        result = DocumentPipeline(self.root).acquire(paper_id=self.pid, local=path, authorization={"access_basis": "researcher_asserted_authorized", "asserted_by": "fixture", "reason": "Synthetic software test only"}, version_kind=version)
        self.assertIn("document", result, result)
        return result["document"]["document_id"]

    def fulltext_context(self, doc=None):
        self.submit()
        self.submit("abstract", "defer")
        return self.p.stage_context(self.pid, "fulltext_eligibility", doc, [1] if doc else None)

    def official(self, pdf=False):
        helper = citation_fixtures.CitationTests()
        helper.temp = self.temp
        cp = helper.official()
        cp.start("crossref", "backward")
        cp.review("FICTIONAL human", "Synthetic approval", "Synthetic empty index", "human_stop")
        transition_phase(cp.root, 4, "completed")
        transition_phase(cp.root, 5, "in_progress")
        self.root = cp.root
        self.p = ScreeningPipeline(self.root)
        self.pid = next(iter(self.p.registry.data["records"]))
        doc = self.import_pdf() if pdf else None
        dispositions = {pid: {"status": "pending_screening", "basis": "Synthetic title-first acquisition disposition"} for pid in self.p.registry.data["records"]}
        if doc:
            dispositions[self.pid] = {"status": "acquired", "document_id": doc, "basis": "Synthetic PDF only"}
        write_json_atomic(self.root / "03_library/ACQUISITION_REVIEW.json", {"reviewed_by": "FICTIONAL reviewer", "reviewed_at": "2099-01-01", "papers": dispositions})
        transition_phase(self.root, 5, "completed")
        transition_phase(self.root, 6, "in_progress")
        self.p = ScreeningPipeline(self.root)
        self.p.register(config(self.p), "Fictional criteria mapping")
        self.p.approve_criteria("FICTIONAL human", "Synthetic test only; NOT genuine research approval")
        return doc

    def approve(self, value):
        return self.p.review(value["decision_id"], "approve", "FICTIONAL human", "Synthetic test-only approval")

    def finish_excluded(self):
        for pid in self.p.current()["candidate_ids"]:
            packet = self.p.stage_context(pid, "title")
            self.approve(self.p.propose(proposal(self.p, packet, "exclude")))

    def test_title_decision_enum_roles_and_no_doi(self):
        for decision in ("include", "exclude", "uncertain", "defer"):
            packet = self.context()
            value = proposal(self.p, packet, decision)
            old = self.p.latest(self.pid, "title")
            if old:
                value["superseded_decision_id"] = old["decision_id"]
            self.assertEqual(self.p.propose(value)["decision"], decision)
        self.assertEqual(len(self.p.data["decisions"]), 4)

    def test_title_packet_has_no_abstract_or_pdf(self):
        self.add_abstract()
        packet = self.context()
        self.assertNotIn("abstract", packet)
        self.assertNotIn("pages", packet)
        value = proposal(self.p, packet, "include", facts=[{"location": "abstract", "quote": "Fictional qualitative interview study."}])
        with self.assertRaisesRegex(ValueError, "PERMITTED_EVIDENCE"):
            self.p.propose(value)

    def test_abstract_original_and_exact_source_fact(self):
        self.add_abstract()
        self.submit()
        packet = self.context("abstract")
        self.assertIn("jats", packet["abstract"]["original"])
        value = self.p.propose(proposal(self.p, packet, "include", facts=[{"location": "abstract", "quote": "Fictional qualitative interview study."}]))
        self.assertEqual(value["source_basis"], "abstract")

    def test_missing_abstract_cannot_be_excluded_or_included(self):
        self.submit()
        packet = self.context("abstract")
        for decision in ("include", "exclude"):
            with self.assertRaisesRegex(ValueError, "MISSING_ABSTRACT"):
                self.p.propose(proposal(self.p, packet, decision))
        self.assertEqual(self.p.propose(proposal(self.p, packet, "defer"))["decision"], "defer")

    def test_missing_stage_cannot_be_skipped(self):
        with self.assertRaisesRegex(ValueError, "PREVIOUS_STAGE"):
            self.context("abstract")

    def test_excluded_previous_stage_cannot_progress(self):
        self.submit(decision="exclude")
        with self.assertRaisesRegex(ValueError, "PREVIOUS_STAGE"):
            self.context("abstract")

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_fulltext_identity_and_locator(self):
        doc = self.import_pdf()
        packet = self.fulltext_context(doc)
        text = packet["pages"][0]["text"]
        facts = [{"location": "1", "quote": text, "purpose": p} for p in ("identity", "eligibility", "version")]
        d = self.p.propose(proposal(self.p, packet, "include", facts=facts))
        self.assertEqual(d["document_id"], doc)
        self.assertFalse((self.root / "06_evidence/EVIDENCE_MATRIX.csv").exists())

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_fulltext_missing_identity_passage_rejected(self):
        doc = self.import_pdf(text="Wrong fictional document content")
        packet = self.fulltext_context(doc)
        with self.assertRaisesRegex(ValueError, "IDENTITY_PASSAGE"):
            self.p.propose(proposal(self.p, packet, "include", facts=[{"location": "1", "quote": "Wrong fictional document content", "purpose": "eligibility"}]))

    def test_missing_fulltext_preserved(self):
        packet = self.fulltext_context()
        self.assertEqual(packet["eligibility_status"], "awaiting_authorized_import")
        with self.assertRaisesRegex(ValueError, "UNAVAILABLE_OR_WRONG"):
            self.p.propose(proposal(self.p, packet, "include"))
        self.p.propose(proposal(self.p, packet, "defer"))
        self.assertEqual(self.p.coverage()["deferred"], 1)

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_wrong_version_preserved(self):
        doc = self.import_pdf(version="unknown")
        packet = self.fulltext_context(doc)
        self.assertEqual(packet["eligibility_status"], "wrong_document_version")
        with self.assertRaises(ValueError):
            self.p.propose(proposal(self.p, packet, "exclude"))

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_unreadable_fulltext_preserved(self):
        doc = self.import_pdf(scanned=True)
        packet = self.fulltext_context(doc)
        self.assertEqual(packet["eligibility_status"], "text_extraction_insufficient")

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_targeted_pages_required(self):
        doc = self.import_pdf()
        self.submit()
        self.submit("abstract", "defer")
        with self.assertRaisesRegex(ValueError, "TARGETED_PAGES"):
            self.p.stage_context(self.pid, "fulltext_eligibility", doc, [200])

    def test_unknown_reason_rejected(self):
        value = proposal(self.p, self.context())
        value["reason_codes"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "REASON"):
            self.p.propose(value)

    def test_protocol_role_extension_and_four_roles(self):
        cfg = config(self.p)
        cfg["role_extensions"] = {"include_primary_material": "Fictional archival primary material"}
        self.p.register(cfg, "Fictional extension")
        for role in ("include_core", "include_context", "include_method", "include_theory", "include_primary_material"):
            value = proposal(self.p, self.context(), "include", role)
            old = self.p.latest(self.pid, "title")
            if old:
                value["superseded_decision_id"] = old["decision_id"]
            self.assertEqual(self.p.propose(value)["review_role"], role)

    def test_model_cannot_import_human_approval(self):
        value = proposal(self.p, self.context(), "include")
        value.update(approval_status="approved", reviewer_type="human_declared")
        d = self.p.propose(value)
        self.assertEqual(d["approval_status"], "proposed")
        with self.assertRaisesRegex(ValueError, "PILOT_CANNOT"):
            self.p.review(d["decision_id"], "approve", "Codex", "not authorized")

    def test_human_override_history_and_reopen(self):
        self.official()
        first = self.submit(decision="include")
        second = self.p.review(first["decision_id"], "override", "FICTIONAL", "Synthetic override rationale", {"decision": "exclude", "review_role": None, "reason_codes": ["criterion_not_met"], "explanation": "Synthetic explicit criterion exclusion"})
        self.assertEqual(self.p.data["decisions"][0]["decision"], "include")
        self.assertEqual(second["superseded_decision_id"], first["decision_id"])
        self.assertFalse(second["identity_authenticated"])
        third = self.p.review(second["decision_id"], "reopen", "FICTIONAL", "Synthetic reopening")
        self.assertEqual(third["approval_status"], "reopened")
        self.assertEqual(self.p.coverage()["final_records"], 0)

    def test_reject_uncertain_defer_preserve_history(self):
        self.official()
        d = self.submit()
        for action in ("reject", "uncertain", "defer"):
            d = self.p.review(d["decision_id"], action, "FICTIONAL", "Synthetic reason")
        self.assertEqual(len(self.p.data["decisions"]), 4)
        self.assertEqual(d["decision"], "defer")

    def test_replay_idempotence_and_conflicting_decision(self):
        value = proposal(self.p, self.context(), "include")
        first = self.p.propose(value)
        self.assertEqual(first["decision_id"], self.p.propose(value)["decision_id"])
        value["decision"] = "exclude"
        with self.assertRaisesRegex(ValueError, "SUPERSESSION"):
            self.p.propose(value)

    def test_related_versions_and_unresolved_upstream(self):
        write_json_atomic(self.root / "02_discovery/EXPANSION_CANDIDATES.json", [{"candidate_id": "fictional-unresolved", "resolved_paper_id": None}])
        r = self.p.registry.data["records"][self.pid]
        r["related_versions"] = [{"paper_id": self.p.current()["candidate_ids"][1], "basis": "fictional-test"}]
        self.p.registry.save()
        self.p = ScreeningPipeline(self.root)
        self.p.register(config(self.p), "Related fictional version update")
        self.assertEqual(self.p.coverage()["upstream_unresolved_candidates"], 1)
        self.assertEqual(self.p.coverage()["related_version_records"], 1)
        self.assertEqual(len(self.p.registry.data["records"]), 3)

    def test_counts_reconcile_with_incomplete_coverage(self):
        self.submit()
        counts = self.p.coverage()
        self.assertTrue(counts["reconciled"])
        self.assertEqual(counts["not_screened"], 2)
        self.assertEqual(counts["pending_review"], 3)
        self.assertEqual(self.p.gate()["status"], "blocked")

    def test_criteria_change_only_affects_applicable_records(self):
        ids = self.p.current()["candidate_ids"]
        for pid in ids:
            self.p.propose(proposal(self.p, self.p.stage_context(pid, "title")))
        cfg = config(self.p)
        cfg["rules"].append({"id": "bounded", "text": "Fictional bounded material criterion", "kind": "include", "stages": ["title"], "paper_ids": [ids[0]]})
        self.p.register(cfg, "Fictional bounded amendment")
        self.assertTrue(self.p.stale(self.p.latest(ids[0])))
        self.assertFalse(self.p.stale(self.p.latest(ids[1])))
        self.assertEqual(self.p.gate()["status"], "fail")

    def test_protocol_edit_detected_without_overwrite(self):
        self.official()
        path = self.root / "00_protocol/PROTOCOL.json"
        value = json.loads(path.read_text())
        value["research_question"] += " amended without review"
        write_json_atomic(path, value)
        self.assertIn("PROTOCOL_AMENDMENT_DETECTED", self.p.validate()["errors"])
        self.assertEqual(json.loads(path.read_text()), value)

    def test_old_packet_not_reused_for_new_version(self):
        packet = self.context()
        self.p.register(config(self.p), "Fictional new criteria version")
        with self.assertRaisesRegex(ValueError, "NEW_CONTEXT"):
            self.p.propose(proposal(self.p, packet))

    def test_previous_stage_reopening_invalidates_later(self):
        self.official()
        title = self.approve(self.submit())
        self.submit("abstract", "defer")
        self.p.review(title["decision_id"], "reopen", "FICTIONAL", "Synthetic change")
        self.assertTrue(self.p.stale(self.p.latest(self.pid, "abstract")))

    def test_gate_pass_and_workflow_completion_for_fictional_exclusions(self):
        self.official()
        self.finish_excluded()
        self.assertEqual(self.p.gate(require_completed=False)["status"], "pass")
        transition_phase(self.root, 6, "completed")
        self.assertEqual(ScreeningPipeline(self.root).gate()["status"], "pass")
        self.assertEqual(evaluate_gates(self.root, 7)["gate-1-screening-before-reading"]["status"], "pass")

    def test_gate_warn_only_for_human_approved_bounded_scope(self):
        self.official()
        ids = self.p.current()["candidate_ids"]
        cfg = config(self.p)
        cfg.update(candidate_ids=ids[:1], scope_exceptions={pid: "Fictional explicitly bounded scope, not scientific exclusion" for pid in ids[1:]})
        self.p.register(cfg, "Synthetic bounded scope")
        self.assertEqual(self.p.gate(False)["status"], "blocked")
        with self.assertRaisesRegex(ValueError, "APPROVE_CRITERIA"):
            self.context()
        self.p.approve_criteria("FICTIONAL", "Test-only approval of scope exceptions")
        self.finish_excluded()
        self.assertEqual(self.p.gate(False)["status"], "warn")

    def test_upstream_phase4_cannot_be_bypassed(self):
        self.official()
        state = load_state(self.root)
        state["citation_data"]["reviews"] = []
        persist_state(self.root, state, "fictional_remove_review")
        p = ScreeningPipeline(self.root)
        with self.assertRaisesRegex(ValueError, "UPSTREAM_BLOCKED"):
            p.stage_context(self.pid, "title")
        self.assertEqual(p.gate(False)["status"], "blocked")

    def test_phase5_pending_screening_and_unknown_rights(self):
        self.official()
        self.assertFalse(validate_phase(self.root, 5))
        rows = self.p.acquisition()
        self.assertTrue(all(r["license_status"] == "unknown" for r in rows))
        self.assertTrue(all(r["fulltext_availability"] == "pending_screening" for r in rows))

    def test_phase5_missing_disposition_blocks(self):
        self.official()
        path = self.root / "03_library/ACQUISITION_REVIEW.json"
        value = json.loads(path.read_text())
        value["papers"].pop(self.pid)
        write_json_atomic(path, value)
        self.assertTrue(validate_phase(self.root, 5))
        result = self.p.gate(False)
        self.assertEqual(result["status"], "fail")  # altered source also stales the acquisition projection
        self.assertTrue(any("access disposition" in x for x in result["blockers"]))

    def test_artifact_tamper_recovery_and_history(self):
        d = self.submit()
        path = self.root / "04_screening/SCREENING_MASTER.csv"
        path.write_text("corrupt")
        self.assertFalse(self.p.validate()["valid"])
        with self.assertRaisesRegex(ValueError, "EXPORT_CHANGED"):
            self.context()
        self.p.recover()
        self.assertTrue(self.p.validate()["valid"])
        self.assertEqual(self.p.data["decisions"][0]["decision_id"], d["decision_id"])

    def test_packet_tamper_fails(self):
        d = self.submit()
        ref = self.p.data["packets"][d["packet_id"]]
        (self.root / ref["path"]).write_text("tampered")
        self.assertFalse(self.p.validate()["valid"])

    def test_empty_legacy_screening_never_passes(self):
        self.official()
        self.assertFalse(self.p.gate(False)["allowed"])

    def test_four_domains_have_no_fixed_population_fields(self):
        for domain, phrase in [("social", "Institutional trust"), ("education", "Teachers interpret feedback"), ("archaeology", "Ceramic chronology"), ("history", "Municipal archival arguments")]:
            cfg = config(self.p)
            cfg["rules"][0]["text"] = phrase
            self.p.register(cfg, "Fictional " + domain + " criteria")
            packet = self.context()
            d = self.p.propose({**proposal(self.p, packet), **({"superseded_decision_id": self.p.latest(self.pid, "title")["decision_id"]} if self.p.latest(self.pid, "title") else {})})
            self.assertTrue(set(FIELDS).issubset(d))
            self.assertNotIn("exposure", d)
            self.assertNotIn("political participation", json.dumps(packet).lower())

    def test_schema_v1_v2_remain_readable(self):
        self.official()
        path = self.root / "00_protocol/PROTOCOL.json"
        for version in ("1.0.0", "2.0.0"):
            value = json.loads(path.read_text())
            value["schema_version"] = version
            write_json_atomic(path, value)
            self.assertEqual(ScreeningPipeline(self.root).context()["schema_version"], version)

    def test_no_skills_and_no_official_reading_in_lab(self):
        repo = Path(__file__).resolve().parents[1]
        self.assertFalse((repo / ".agents/skills").exists())
        with self.assertRaisesRegex(ValueError, "NOT_SCIENTIFIC_READING"):
            DocumentPipeline(self.root).parse("nonexistent")

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_official_fulltext_inclusion_with_exact_version(self):
        doc = self.official(pdf=True)
        self.approve(self.submit(decision="include"))
        # Missing abstract is explicitly deferred, not fabricated. Full text can resolve it.
        self.approve(self.submit("abstract", "defer"))
        packet = self.p.stage_context(self.pid, "fulltext_eligibility", doc, [1])
        text = packet["pages"][0]["text"]
        self.approve(self.p.propose(proposal(self.p, packet, "include", facts=[{"location": "1", "quote": text, "purpose": x} for x in ("identity", "eligibility", "version")])))
        for pid in self.p.current()["candidate_ids"]:
            if pid != self.pid:
                self.approve(self.p.propose(proposal(self.p, self.p.stage_context(pid, "title"), "exclude")))
        self.assertEqual(self.p.gate(False)["eligible_paper_ids"], [self.pid])
        transition_phase(self.root, 6, "completed")
        self.assertEqual(ScreeningPipeline(self.root).gate()["status"], "pass")

    def test_cli_recovers_corrupt_state_and_inspects_original_packet(self):
        d = self.submit()
        (self.root / ".review/state.json").write_text("corrupt fixture")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli_main(["screening-recover", "--project", str(self.root)]), 0)
        self.assertTrue(json.loads(output.getvalue())["validation"]["valid"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli_main(["screening-inspect", "--project", str(self.root), "--decision-id", d["decision_id"]]), 0)
        self.assertEqual(json.loads(output.getvalue())["evidence"]["packet_id"], d["packet_id"])

    def test_lawful_unavailability_preserves_uncertainty(self):
        write_json_atomic(self.root / "03_library/ACQUISITION_REVIEW.json", {"papers": {self.pid: {"status": "unavailable", "basis": "Fictional retrieval failure"}}})
        packet = self.fulltext_context()
        self.assertEqual(packet["eligibility_status"], "fulltext_unavailable")
        self.assertEqual(self.p.propose(proposal(self.p, packet, "uncertain"))["decision"], "uncertain")

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra needed to prepare fixture before simulating dependency removal")
    def test_missing_pdf_parser_is_not_model_substitution(self):
        from unittest.mock import patch
        from research_review_agent.documents.contracts import DocumentError
        doc = self.import_pdf()
        with patch("research_review_agent.screening.pipeline.run_parser", side_effect=DocumentError("PARSER_UNAVAILABLE", "Test-only missing dependency")):
            with self.assertRaisesRegex(ValueError, "PARSER_UNAVAILABLE"):
                self.fulltext_context(doc)
        self.assertIsNone(self.p.latest(self.pid, "fulltext_eligibility"))

    def test_phase4_flag_without_citation_records_is_rejected(self):
        self.official()
        state = load_state(self.root)
        state.pop("citation_data")
        persist_state(self.root, state, "fictional_remove_citation_state")
        gate = evaluate_gates(self.root, 5)
        self.assertEqual(gate["citation-phase4-artifacts-current"]["status"], "fail")

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_document_checksum_change_invalidates_eligibility(self):
        doc = self.import_pdf()
        packet = self.fulltext_context(doc)
        self.p.propose(proposal(self.p, packet))
        from research_review_agent.documents.store import DocumentStore
        record = DocumentStore(self.root).load()["documents"][doc]
        (self.root / record["local_path"]).write_bytes(b"broken synthetic PDF")
        self.assertFalse(self.p.validate()["valid"])

    def test_acquisition_export_before_criteria(self):
        root = self.base / "new-official"
        initialize_project(root, "Fictional no criteria", "test")
        p = ScreeningPipeline(root)
        p.export_acquisition()
        self.assertTrue((root / "03_library/ACQUISITION_STATUS.csv").exists())
        self.assertFalse(p.data["criteria"])

    @unittest.skipUnless(HAS_PARSER, "Optional pdf extra required for synthetic PDF integration")
    def test_version_requires_observed_passage_not_only_import_label(self):
        doc = self.import_pdf()
        packet = self.fulltext_context(doc)
        text = packet["pages"][0]["text"]
        with self.assertRaisesRegex(ValueError, "VERSION_PASSAGE"):
            self.p.propose(proposal(self.p, packet, "include", facts=[{"location": "1", "quote": text, "purpose": x} for x in ("identity", "eligibility")]))

    def test_conflicting_registry_identity_cannot_enter_scope(self):
        self.p.registry.data["records"][self.pid]["verification_status"] = "conflict"
        self.p.registry.save()
        self.p = ScreeningPipeline(self.root)
        with self.assertRaisesRegex(ValueError, "IDENTITY_CONFLICT"):
            self.p.register(config(self.p), "Fictional conflict test")

    def test_same_title_different_doi_does_not_supply_abstract(self):
        r = self.p.registry.data["records"][self.pid]
        r["doi"] = "10.5555/fictional.a"
        relative = "02_discovery/raw/conflicting.json"
        write_json_atomic(self.root / relative, {"message": {"DOI": "10.5555/fictional.b", "title": [r["title"]], "abstract": "Fictional wrong-version abstract"}})
        r["provenance"].append({"provider": "crossref", "raw_response_path": relative})
        self.p.registry.save()
        self.assertIsNone(ScreeningPipeline(self.root).abstract(self.pid)["text"])
