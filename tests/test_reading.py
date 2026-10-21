"""FICTIONAL fixtures and reviewer assertions. No semantic accuracy/gold-standard claims."""
import copy
import importlib.util
import json
import unittest
from unittest.mock import patch

import test_screening as screening_fixtures
from research_review_agent.reading.pipeline import ReadingPipeline, initialize_lab
from research_review_agent.reading.contracts import CONTENT_FIELDS, validate_note, validate_item
from research_review_agent.documents.pipeline import DocumentPipeline
from research_review_agent.state import load_state, persist_state, write_json_atomic
from research_review_agent.workflow import transition_phase, evaluate_gates
from research_review_agent.validation import validate_phase

HAS_PARSER = bool(importlib.util.find_spec("pypdf"))


class ReadingContractTests(unittest.TestCase):
    def test_contract_has_all_content_and_support_boundaries(self):
        from research_review_agent.reading.contracts import schema
        self.assertEqual(len(schema()["note_content_fields"]), 25)
        self.assertEqual(len(schema()["support_boundaries"]), 5)

    def test_empty_note_is_not_a_reading_record(self):
        with self.assertRaises(ValueError):
            validate_note({})

    def test_empty_evidence_is_not_an_extraction(self):
        with self.assertRaises(ValueError):
            validate_item({})


def note_config(p, pid, did, aid):
    doc = p.dp.store.load()["documents"][did]
    content = {k: {"status": "not_applicable", "reason": "Explicitly fictional engineering fixture, not a scientific paper."} for k in CONTENT_FIELDS}
    content["research_problem"] = {"status": "present", "text": "Fictional result only", "epistemic_role": "source_report", "source_anchor_ids": [aid]}
    return {"paper_id": pid, "document_id": did, "document_sha256": doc["sha256"], "document_version": doc["version_kind"],
            "generator": "FICTIONAL model", "reading_status": "completed", "unresolved_material": [], "content": content,
            "source_coverage": {"pages_read": [1], "visual_pages": [1], "layout_assessment": "Synthetic one-line page; fixture assertion only",
                                "sections": [{"name": "entire synthetic source", "status": "read", "basis": "test-only one-page fixture"}]}}


def evidence_config(p, note, kind="argument"):
    return {"paper_id": note["paper_id"], "document_id": note["document_id"], "document_sha256": note["document_sha256"],
            "reading_note_id": note["reading_note_id"], "source_anchor_ids": note["source_anchor_ids"],
            "research_question": p.context()["research_question"], "source_basis": "full_text", "research_context": "Synthetic test only",
            "evidence_type": "fictional_test", "research_types": ["theoretical_conceptual"], "extension_json": {},
            "finding_argument_proposition": "Fictional " + kind, "limitations_uncertainty": "Not genuine research evidence",
            "result_kind": kind, "extraction_run_id": "FICTIONAL-RUN", "generator": "fixture", "example_data": True,
            "extraction_status": "supported", "citation_basis": "primary_in_this_source", "source_scope": "body_text", "inference_class": "conceptual",
            "support_boundaries": {k: "Fictional software test only; not actual findings" for k in ("source_reports", "author_interpretation", "codex_inference", "uncertainty", "cannot_support")}}


@unittest.skipUnless(HAS_PARSER, "Optional PDF extra required for fictional reading integration")
class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.h = screening_fixtures.ScreeningTests()
        self.h.setUp()
        self.addCleanup(self.h.tearDown)
        self.did = self.h.import_pdf()
        self.pid = self.h.pid
        self.root = self.h.base / "reading"
        initialize_lab(self.root, self.h.root, "Fictional method-neutral test question", [self.did])
        self.setup_reading()

    def setup_reading(self):
        self.p = ReadingPipeline(self.root)
        parsed = self.p.dp.parse(self.did)
        self.assertIn(parsed["status"], {"parsed", "replayed"})
        self.p = ReadingPipeline(self.root)
        ctx = self.p.reading_context(self.pid, self.did)
        self.a = self.p.dp.anchor(self.did, ctx["pages"][0]["text"], pdf_page=1)
        self.ncfg = note_config(self.p, self.pid, self.did, self.a["anchor_id"])
        self.note = self.p.submit("notes", self.ncfg)
        self.ecfg = evidence_config(self.p, self.note)

    def official(self):
        # Existing 2F end-to-end synthetic approval fixture, never real reviewer approval.
        self.h.test_official_fulltext_inclusion_with_exact_version()
        self.root, self.pid = self.h.root, self.h.pid
        self.did = self.h.p.latest(self.pid)["document_id"]
        transition_phase(self.root, 7, "in_progress")
        self.setup_reading()
        self.note = self.p.review("notes", self.note["reading_note_id"], "accept", "FICTIONAL reviewer", "Synthetic test-only acceptance")
        transition_phase(self.root, 7, "completed")
        transition_phase(self.root, 8, "in_progress")
        self.p = ReadingPipeline(self.root)
        self.ecfg = evidence_config(self.p, self.note)
        self.ecfg["research_types"] = self.p.context()["research_types"][:1]
        self.ecfg["extension_json"] = {"participants_or_cases": "fictional fixture", "data_collection": "fictional interviews", "analytic_approach": "fictional coding"}

    def test_multiple_findings_and_result_kinds(self):
        for kind in ("positive", "negative", "null", "mixed", "contradictory", "conditional", "argument", "interpretation", "uncertain"):
            self.p.submit("evidence", evidence_config(self.p, self.note, kind))
        self.assertEqual(self.p.coverage()["evidence_count"], 9)
        self.assertTrue(self.p.validate()["valid"])

    def test_five_types_and_composable_rows(self):
        extensions = {"quantitative_empirical": {"study_design": "fictional association"},
                      "qualitative_empirical": {"theme_or_interpretation": "fictional theme; no invented interview quote"},
                      "historical_documentary": {"source_type": "fictional archive"},
                      "theoretical_conceptual": {"premises": "fictional premise"},
                      "archaeological_material": {"provenience": "fictional site"}}
        for research_type, ext in extensions.items():
            self.p.submit("evidence", {**self.ecfg, "research_types": [research_type], "extension_json": ext})
        self.p.submit("evidence", {**self.ecfg, "research_types": list(extensions), "extension_json": {k: v for ext in extensions.values() for k, v in ext.items()}})
        self.assertEqual(self.p.coverage()["evidence_count"], 6)

    def test_missing_locator_rejected_but_uncertainty_retained(self):
        cfg = {**self.ecfg, "source_anchor_ids": []}
        with self.assertRaisesRegex(ValueError, "SOURCE_ANCHOR"):
            self.p.submit("evidence", cfg)
        cfg.update(extraction_status="uncertain", grounding_unavailable_reason="Unresolved source representation")
        item = self.p.submit("evidence", cfg)
        self.assertEqual(item["verification_status"], "not_auditable")

    def test_bad_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError, "CHECKSUM"):
            self.p.submit("evidence", {**self.ecfg, "document_sha256": "invalid"})

    def test_unknown_document_rejected(self):
        with self.assertRaisesRegex(ValueError, "CORPUS"):
            self.p.submit("evidence", {**self.ecfg, "document_id": "unknown"})

    def test_wrong_version_rejected(self):
        with self.assertRaisesRegex(ValueError, "VERSION"):
            self.p.prepare("notes", {**self.ncfg, "document_version": "preprint"})

    def test_unknown_paper_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_PAPER"):
            self.p.submit("evidence", {**self.ecfg, "paper_id": "unknown"})

    def test_abstract_cannot_be_fulltext(self):
        with self.assertRaisesRegex(ValueError, "FULL_TEXT_REQUIRED"):
            self.p.submit("evidence", {**self.ecfg, "source_basis": "abstract"})

    def test_secondary_reports_remain_secondary(self):
        cfg = {**self.ecfg, "citation_basis": "secondary_report"}
        with self.assertRaisesRegex(ValueError, "SECONDARY"):
            self.p.submit("evidence", cfg)
        cfg["secondary_source_reference"] = "Unverified source referred to by fictional paper"
        self.assertEqual(self.p.submit("evidence", cfg)["citation_basis"], "secondary_report")

    def test_incomplete_methods_and_results_are_explicit(self):
        cfg = copy.deepcopy(self.ncfg)
        for k in ("methods", "empirical_findings"):
            cfg["content"][k] = {"status": "not_reliably_extractable", "reason": "Fictional extraction failure"}
        cfg.update(reading_status="partial", reading_note_id=self.note["reading_note_id"], supersedes_revision=self.note["revision_id"])
        self.p.submit("notes", cfg)
        self.assertEqual(self.p.coverage()["reading_counts"], {"partial": 1})

    def test_unreadable_table_figure_requires_manual_review(self):
        for scope in ("table", "figure", "equation", "supplement"):
            with self.assertRaisesRegex(ValueError, "REPRESENTATION"):
                self.p.submit("evidence", {**self.ecfg, "source_scope": scope})

    def test_missing_supplement_remains_unresolved(self):
        cfg = {**self.ecfg, "source_scope": "supplement", "source_anchor_ids": [], "extraction_status": "incomplete", "grounding_unavailable_reason": "Supplement inaccessible"}
        self.p.submit("evidence", cfg)
        self.assertEqual(self.p.coverage()["papers"][0]["unsupported_ambiguous_items"], 1)

    def test_unsupported_effect_size_rejected(self):
        cfg = {**self.ecfg, "research_types": ["quantitative_empirical"], "extension_json": {"effect_size": "fictional 0.75"}}
        with self.assertRaisesRegex(ValueError, "EFFECT_SIZE"):
            self.p.submit("evidence", cfg)

    def test_reported_value_requires_exact_literal(self):
        cfg = {**self.ecfg, "reported_values": [{"anchor_id": self.a["anchor_id"], "literal": "nonexistent estimate", "units": "test", "denominator": "test", "uncertainty": "test"}]}
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_REPORTED"):
            self.p.submit("evidence", cfg)

    def test_association_not_auto_causal(self):
        with self.assertRaisesRegex(ValueError, "CAUSAL_IDENTIFICATION"):
            self.p.submit("evidence", {**self.ecfg, "inference_class": "causal"})
        self.assertEqual(self.p.submit("evidence", {**self.ecfg, "inference_class": "associational"})["inference_class"], "associational")

    def test_idempotent_replay(self):
        a = self.p.submit("evidence", self.ecfg)
        b = self.p.submit("evidence", self.ecfg)
        self.assertEqual(a["evidence_id"], b["evidence_id"])
        self.assertEqual(len(self.p.data["evidence"]), 1)

    def test_pilot_not_human_reviewed(self):
        e = self.p.submit("evidence", {**self.ecfg, "review_status": "accepted"})
        self.assertEqual(e["review_status"], "pending")
        with self.assertRaisesRegex(ValueError, "PILOT"):
            self.p.review("notes", self.note["reading_note_id"], "accept", "Codex", "not authorized")

    def test_document_change_stales_evidence(self):
        e = self.p.submit("evidence", self.ecfg)
        doc = self.p.dp.store.load()["documents"][self.did]
        (self.root / doc["local_path"]).write_bytes(b"Fictional corruption")
        self.assertEqual(self.p.inspect("evidence", e["evidence_id"])["effective_status"], "stale")

    def test_parser_change_stales_evidence(self):
        e = self.p.submit("evidence", self.ecfg)
        with patch("research_review_agent.reading.pipeline.parser_version", return_value="changed"):
            self.assertTrue(self.p.stale(e, "evidence"))

    def test_anchor_change_stales_evidence(self):
        e = self.p.submit("evidence", self.ecfg)
        data = self.p.dp.store.load()
        data["anchors"][self.a["anchor_id"]]["section"] = "changed fictional section"
        self.p.dp.store.commit(data, "fictional anchor change")
        self.assertTrue(self.p.stale(e, "evidence"))

    def test_protocol_change_stales_evidence(self):
        e = self.p.submit("evidence", self.ecfg)
        marker = self.p.context()
        marker["protocol_version"] = "changed"
        write_json_atomic(self.root / "READING_LAB.json", marker)
        self.assertTrue(self.p.stale(e, "evidence"))

    def test_note_revision_stales_evidence(self):
        e = self.p.submit("evidence", self.ecfg)
        self.p.submit("notes", {**self.ncfg, "reading_note_id": self.note["reading_note_id"], "supersedes_revision": self.note["revision_id"], "unresolved_material": ["New concern"]})
        self.assertTrue(self.p.stale(e, "evidence"))

    def test_unrelated_record_does_not_stale_evidence(self):
        e = self.p.submit("evidence", self.ecfg)
        self.p.submit("evidence", {**self.ecfg, "finding_argument_proposition": "Another distinct synthetic finding"})
        self.assertFalse(self.p.stale(e, "evidence"))

    def test_interrupt_and_projection_recovery(self):
        self.p.submit("evidence", self.ecfg)
        (self.root / ".review/state.json").write_text("corrupt fixture")
        self.assertTrue(self.p.recover()["valid"])
        (self.root / "06_evidence/EVIDENCE_MATRIX.csv").write_text("manual fixture tamper")
        self.assertFalse(self.p.validate()["valid"])
        self.assertTrue(self.p.recover()["valid"])

    def test_gate2_blocked_without_human_and_coverage(self):
        self.p.submit("evidence", self.ecfg)
        self.assertFalse(self.p.completion()["allowed"])
        self.assertEqual(self.p.coverage()["papers"][0]["evidence_pending_review"], 1)

    def test_official_review_correction_gate2_and_gate3(self):
        self.official()
        item = self.p.submit("evidence", self.ecfg)
        self.assertFalse(self.p.completion()["allowed"])
        item = self.p.review("evidence", item["evidence_id"], "reject", "FICTIONAL", "test rejection")
        item = self.p.review("evidence", item["evidence_id"], "correct", "FICTIONAL", "test correction", {"finding_argument_proposition": "Corrected fictional argument"})
        self.assertEqual(item["review_status"], "pending")
        item = self.p.review("evidence", item["evidence_id"], "accept", "FICTIONAL", "test acceptance")
        self.p.close_extraction(self.pid, "complete", "Fictional full extraction review", "FICTIONAL")
        self.assertTrue(self.p.completion()["allowed"])
        self.assertFalse(validate_phase(self.root, 8, allow_example_data=True))
        transition_phase(self.root, 8, "completed", allow_example_data=True)
        gates = evaluate_gates(self.root, 15, allow_example_data=True)
        self.assertEqual(gates["gate-2-evidence-before-drafting"]["status"], "pass")
        self.assertEqual(gates["gate-3-claims-before-gap"]["status"], "fail")

    def test_official_gate1_and_screening_reopen(self):
        self.official()
        e = self.p.submit("evidence", self.ecfg)
        # Reopening upstream is a test-only recorded change; eligibility must be revoked.
        state = load_state(self.root)
        state["phases"]["6"]["status"] = "in_progress"
        persist_state(self.root, state, "fictional_screening_reopened")
        p = ReadingPipeline(self.root)
        self.assertTrue(p.stale(e, "evidence"))
        with self.assertRaisesRegex(ValueError, "GATE1_BLOCKED"):
            p.submit("evidence", self.ecfg)

    def test_legacy_matrix_not_overwritten(self):
        marker = self.p.context()
        marker["schema_version"] = "1.0.0"
        write_json_atomic(self.root / "READING_LAB.json", marker)
        old = (self.root / "06_evidence/EVIDENCE_MATRIX.csv").read_bytes()
        self.p.export()
        self.assertEqual(old, (self.root / "06_evidence/EVIDENCE_MATRIX.csv").read_bytes())
        self.assertTrue((self.root / "06_evidence/EVIDENCE_MATRIX_V2.csv").exists())

    def test_no_case_leakage_or_skills_dependency(self):
        text = json.dumps(self.p.reading_context(self.pid, self.did)).lower()
        for term in ("social media", "political participation", "political efficacy", "tiktok", "instagram"):
            self.assertNotIn(term, text)
        import research_review_agent.reading.pipeline as module
        self.assertNotIn("SKILL.md", __import__("pathlib").Path(module.__file__).read_text())

    def test_zero_items_not_absence_claim(self):
        c = self.p.coverage()
        self.assertEqual(c["evidence_count"], 0)
        self.assertTrue(c["papers"][0]["parsing_limitations"])
        self.assertIsNone(c["papers"][0]["extraction_disposition"])
        self.assertFalse(self.p.completion()["allowed"])

    def test_false_complete_page_coverage_rejected(self):
        cfg = copy.deepcopy(self.ncfg)
        cfg["source_coverage"]["pages_read"] = []
        cfg["source_coverage"]["visual_pages"] = []
        with self.assertRaisesRegex(ValueError, "PAGE_COVERAGE"):
            self.p.prepare("notes", cfg)

    def test_fabricated_locator_rejected(self):
        with self.assertRaisesRegex(ValueError, "READING_NOTE|UNKNOWN_ANCHOR"):
            self.p.submit("evidence", {**self.ecfg, "source_anchor_ids": ["fabricated"]})

    def test_anchor_from_another_document_rejected(self):
        data = self.p.dp.store.load()
        data["anchors"][self.a["anchor_id"]]["paper_id"] = "OTHER-PAPER"
        self.p.dp.store.commit(data, "fictional wrong-paper anchor")
        with self.assertRaisesRegex(ValueError, "STALE|WRONG_DOCUMENT"):
            self.p.submit("evidence", self.ecfg)

    def test_exact_locator_and_document_retrieval(self):
        e = self.p.submit("evidence", self.ecfg)
        inspected = self.p.inspect("evidence", e["evidence_id"])
        a = inspected["anchors"][0]
        self.assertEqual(a["resolved_pdf_page"], 1)
        self.assertTrue(__import__("pathlib").Path(a["resolved_pdf"]).is_file())
        self.assertEqual(a["verification_status"], "machine_located")
        self.assertNotEqual(e["verification_status"], "verified")

    def test_all_review_actions_and_append_history(self):
        self.official()
        item = self.p.submit("evidence", self.ecfg)
        for action in ("uncertain", "incomplete", "reread", "comment"):
            item = self.p.review("evidence", item["evidence_id"], action, "FICTIONAL", "Test-only methodological comment")
        self.assertEqual(len(self.p.data["evidence"]), 5)
        self.assertFalse(item["identity_authenticated"])
        self.assertFalse(self.p.completion()["allowed"])

    def test_evidence_revision_invalidates_coverage_closure(self):
        e = self.p.submit("evidence", self.ecfg)
        self.p.close_extraction(self.pid, "complete", "Provisional test closure, not approved")
        self.assertIsNotNone(self.p.coverage()["papers"][0]["extraction_disposition"])
        self.p.submit("evidence", {**self.ecfg, "evidence_id": e["evidence_id"], "supersedes_revision": e["revision_id"], "finding_argument_proposition": "Changed fixture"})
        self.assertIsNone(self.p.coverage()["papers"][0]["extraction_disposition"])

    def test_superseded_replay_is_not_current(self):
        e = self.p.submit("evidence", self.ecfg)
        self.p.submit("evidence", {**self.ecfg, "evidence_id": e["evidence_id"], "supersedes_revision": e["revision_id"], "finding_argument_proposition": "Changed fixture"})
        self.assertEqual(self.p.submit("evidence", self.ecfg)["effective_status"], "stale")

    def test_zero_findings_requires_documented_human_disposition(self):
        self.official()
        self.p.close_extraction(self.pid, "no_relevant_findings", "FICTIONAL no relevant findings after complete inspection", "FICTIONAL")
        self.assertTrue(self.p.completion()["allowed"])
        self.assertFalse(validate_phase(self.root, 8, allow_example_data=True))

    def test_unselected_and_inapplicable_extensions(self):
        with self.assertRaisesRegex(ValueError, "APPLICABILITY"):
            self.p.submit("evidence", {**self.ecfg, "extension_json": {"sample_size": "fictional"}})
        with self.assertRaisesRegex(ValueError, "RESEARCH_TYPE"):
            self.p.submit("evidence", {**self.ecfg, "research_types": ["made_up"]})

    def test_optional_parser_error_is_explicit(self):
        from research_review_agent.documents.contracts import DocumentError
        with patch("research_review_agent.reading.pipeline.parser_version", side_effect=DocumentError("PARSER_UNAVAILABLE", "fixture")):
            with self.assertRaisesRegex(ValueError, "PARSER_UNAVAILABLE"):
                self.p.reading_context(self.pid, self.did)

    def test_legacy_markdown_alone_not_phase7_completion(self):
        self.h.official()
        (self.h.root / "05_reading_notes/fake.md").write_text("Fictional ungrounded note")
        self.assertTrue(validate_phase(self.h.root, 7))

    def test_lab_cannot_be_nested_in_formal_review(self):
        with self.assertRaisesRegex(ValueError, "ISOLATED"):
            initialize_lab(self.root / "nested", self.h.root, "test", [self.did])
