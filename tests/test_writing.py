"""FICTIONAL engineering data/reviewer assertions, NOT semantic accuracy evaluation."""
import copy
import json
import unittest
import tempfile
import contextlib
import io
from pathlib import Path
from unittest.mock import patch

import test_synthesis as synth
from research_review_agent.writing.pipeline import WritingPipeline, initialize_lab
from research_review_agent.writing.contracts import CHECKS, validate, schema
from research_review_agent.writing.bibliography import parse_bib, reconcile
from research_review_agent.state import recover_state, persist_state
from research_review_agent.workflow import transition_phase


def outline(p):
    claims = list(p.sp.latest("claim"))
    return {"review_type": "FICTIONAL methodological comparison", "target_word_count": 300,
            "argument_progression": "Compare bounded claims, then identify limits", "coverage_limitations": "FICTIONAL test sources only",
            "gap_connection": "Only a reviewed corpus-bounded limitation, not field novelty", "duplication_policy": "Each claim once",
            "generator": "FICTIONAL writer", "example_data": True,
            "section_structure": [{"section_id": "comparison", "title": "Bounded comparison", "purpose": "Compare source-bounded arguments",
                                   "argument_progression": "Support, contrast, limit", "planned_counterarguments": "Include every linked contradiction/qualification",
                                   "claim_ids": claims, "gap_ids": []}]}


def brief(p, section="comparison"):
    s = next(s for s in p.outline()["section_structure"] if s["section_id"] == section)
    ids = s["claim_ids"] + s["gap_ids"]
    links = p.links(ids)
    evs = p.rp.latest("evidence")
    v = {k: "FICTIONAL bounded argument; no generalization" for k in ("purpose", "central_argument", "boundary_conditions", "methodological_issues", "relevant_theories", "suggested_argument_progression", "cannot_claim")}
    v.update(section_id=section, required_claim_ids=ids, unresolved_questions=[], generator="FICTIONAL writer", example_data=True)
    for rel, field in (("supports", "supporting_evidence_ids"), ("contradicts", "contradictory_evidence_ids"), ("qualifies", "qualifying_evidence_ids")):
        v[field] = sorted({l["evidence_id"] for l in links if l["relation"] == rel})
    v["planned_citations"] = sorted({evs[l["evidence_id"]]["paper_id"] for l in links})
    return v


def draft(p, section="comparison"):
    b = p.sections("brief")[section]
    evs = sorted(set(b["supporting_evidence_ids"] + b["contradictory_evidence_ids"] + b["qualifying_evidence_ids"]))
    citations = b["planned_citations"]
    return {"section_id": section, "writer": "FICTIONAL writer", "writer_context_id": "fictional-writing-context", "example_data": True,
            "spans": [{"text": "The fictional sources illustrate a bounded test argument " + " ".join("[@" + k + "]" for k in citations) + ".",
                       "classification": "substantive", "claim_ids": b["required_claim_ids"], "evidence_ids": evs, "citation_keys": citations}]}


def audit_config(context, fail=None, partial=False):
    reviews = {}
    for span in context["spans"][:1] if partial else context["spans"]:
        refs = [{"evidence_id": e, "document_id": s["evidence"]["document_id"], "anchor_id": s["evidence"]["source_anchor_ids"][0]} for e, s in context["sources"].items()]
        checks = {k: {"status": "pass", "reason": "FICTIONAL fixture assertion; not a semantic gold standard"} for k in CHECKS}
        if fail:
            checks[fail] = {"status": "fail", "reason": "FICTIONAL injected audit finding", "suggested_correction": "Return to the bounded source wording", "severity": "blocking"}
        reviews[span["span_id"]] = {"outcome": "unsupported" if fail else "supported", "source_references": refs, "checks": checks}
    return {"auditor": context["declared_auditor"], "context_id": context["context_id"], "span_reviews": reviews}


def revision(v):
    config = copy.deepcopy(v)
    config["supersedes_version"] = v["version"]
    config.pop("review_status", None)
    for s in config.get("spans", []):
        for k in ("source_verification_status", "semantic_review_status", "audit_status"):
            s.pop(k, None)
    return config


class WritingContractTests(unittest.TestCase):
    def test_version_and_checks(self):
        self.assertEqual(len(CHECKS), 14)
        self.assertEqual(schema()["contract_version"], "writing/1")

    def test_empty_contracts(self):
        for kind in ("outline", "brief", "draft"):
            with self.assertRaises(ValueError):
                validate(kind, {})

    def test_bib_nested_and_escaped_fields(self):
        entries, errors = parse_bib('@article{P1,title={A {Nested} \\& example}, author={Name}, year={2020}}')
        self.assertFalse(errors)
        self.assertEqual(entries[0]["fields"]["title"], r"A {Nested} \& example")

    def test_unsupported_macros_explicit(self):
        self.assertTrue(parse_bib('@string{foo="bar"}')[1])

    def test_legacy_schema_stays_additive(self):
        from research_review_agent.constants import csv_fields_for_version
        for version in ("1.0.0", "2.0.0"):
            self.assertIn("claim_id", csv_fields_for_version(version)["claim"])

    def test_no_skills_and_nineteen_phases(self):
        from research_review_agent.registry import load_workflow_registry
        repo = Path(__file__).resolve().parents[1]
        self.assertFalse(list(repo.rglob("SKILL.md")))
        self.assertEqual(len(load_workflow_registry()["phases"]), 19)


@unittest.skipUnless(synth.fixtures.HAS_PARSER, "Optional PDF extra required")
class WritingTests(unittest.TestCase):
    def setUp(self):
        self.h = synth.SynthesisTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.h.submit("claim")
        self.h.submit("link")
        self.root = self.h.root.parent / "writing"
        initialize_lab(self.root, self.h.root)
        self.p = WritingPipeline(self.root)

    def prepared(self):
        self.p.submit("outline", outline(self.p))
        self.p.submit("brief", brief(self.p))
        return self.p.submit("draft", draft(self.p))["record"]

    def audited(self, fail=None):
        self.prepared()
        self.p.bibliography()
        context = self.p.audit_context("FICTIONAL independent model", "fresh-fixture-context")
        return self.p.audit_submit(context["audit_id"], audit_config(context, fail))

    def test_outline_claim_consistency_and_unknown_claim(self):
        cfg = outline(self.p)
        cfg["section_structure"][0]["claim_ids"] = ["UNKNOWN"]
        with self.assertRaisesRegex(ValueError, "UNKNOWN_CLAIM"):
            self.p.submit("outline", cfg)

    def test_brief_completeness_and_support_coverage(self):
        self.p.submit("outline", outline(self.p))
        cfg = brief(self.p)
        cfg["supporting_evidence_ids"] = []
        with self.assertRaisesRegex(ValueError, "MISSING_SUPPORTING"):
            self.p.submit("brief", cfg)

    def test_span_trace_full_chain(self):
        v = self.prepared()
        t = self.p.trace(v["spans"][0]["span_id"])
        self.assertTrue(t["claims"])
        self.assertTrue(t["claim_evidence_links"])
        self.assertFalse(t["stale_reasons"])
        self.assertEqual(t["span"]["exact_text_hash"], v["spans"][0]["exact_text_hash"])

    def test_unknown_citation(self):
        self.p.submit("outline", outline(self.p))
        self.p.submit("brief", brief(self.p))
        c = draft(self.p)
        c["spans"][0]["citation_keys"] = ["UNKNOWN"]
        c["spans"][0]["text"] = "FICTIONAL [@UNKNOWN]."
        with self.assertRaisesRegex(ValueError, "CITATION_EVIDENCE"):
            self.p.submit("draft", c)

    def test_unknown_evidence(self):
        self.p.submit("outline", outline(self.p))
        self.p.submit("brief", brief(self.p))
        c = draft(self.p)
        c["spans"][0]["evidence_ids"].append("UNKNOWN")
        with self.assertRaisesRegex(ValueError, "UNKNOWN_EVIDENCE"):
            self.p.submit("draft", c)

    def test_wrong_document_version(self):
        self.p.submit("outline", outline(self.p))
        self.p.submit("brief", brief(self.p))
        c = draft(self.p)
        c["spans"][0]["document_ids"] = ["WRONG"]
        with self.assertRaisesRegex(ValueError, "INCORRECT_DOCUMENT"):
            self.p.submit("draft", c)

    def test_missing_trace_rejected(self):
        self.p.submit("outline", outline(self.p))
        self.p.submit("brief", brief(self.p))
        c = draft(self.p)
        c["spans"][0]["claim_ids"] = []
        with self.assertRaisesRegex(ValueError, "UNTRACED"):
            self.p.submit("draft", c)

    def test_disguised_transition_is_not_automatically_verified(self):
        self.prepared()
        cfg = revision(next(iter(self.p.latest("draft").values())))
        cfg["spans"].append({"text": "Studies show a benefit.", "classification": "transition", "justification": "FICTIONAL disguise", "claim_ids": [], "evidence_ids": [], "citation_keys": []})
        with self.assertRaisesRegex(ValueError, "DISGUISED_AS_TRANSITION"):
            self.p.submit("draft", cfg)

    def test_writer_cannot_set_audit_or_approve(self):
        self.prepared()
        with self.assertRaisesRegex(ValueError, "FRESH_AUDITOR"):
            self.p.audit_context("FICTIONAL writer", "fresh")
        with self.assertRaisesRegex(ValueError, "LAB_CANNOT"):
            self.p.signoff("approve", "FICTIONAL writer", "test", True)
        cfg = revision(next(iter(self.p.latest("draft").values())))
        cfg["spans"][0]["audit_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "WRITER_CANNOT"):
            self.p.submit("draft", cfg)

    def test_sentence_revision_preserves_id_and_stales_audit(self):
        self.audited()
        old = next(iter(self.p.latest("draft").values()))
        c = revision(old)
        c["spans"][0]["text"] = c["spans"][0]["text"].replace("illustrate", "describe")
        new = self.p.submit("draft", c)["record"]
        self.assertEqual(new["spans"][0]["span_id"], old["spans"][0]["span_id"])
        self.assertNotEqual(new["spans"][0]["exact_text_hash"], old["spans"][0]["exact_text_hash"])
        self.assertIn("CURRENT_COMPLETE_INDEPENDENT_AUDIT_REQUIRED", self.p.final_blockers())
        self.assertEqual(len(self.p.data["audit_results"]), 1)

    def test_model_audit_separate_and_source_manifest(self):
        r = self.audited()
        self.assertTrue(r["complete"])
        self.assertFalse(r["human_approved"])
        self.assertTrue(self.p.data["audit_contexts"][0]["source_manifest"])
        self.assertTrue(self.p.structural()["valid"])
        self.assertFalse(self.p.completion(18)["allowed"])

    def test_partial_audit_and_projection_recovery(self):
        self.prepared()
        context = self.p.audit_context("FICTIONAL independent", "fresh")
        config = audit_config(context)
        config["span_reviews"] = {}
        r = self.p.audit_submit(context["audit_id"], config)
        self.assertFalse(r["complete"])
        (self.root / ".review/state.json").write_text("interrupted")
        from research_review_agent.cli import main
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["writing-recover", "--project", str(self.root)]), 0)
        self.assertTrue(json.loads(output.getvalue())["recovered"])
        p = WritingPipeline(self.root)
        self.assertTrue(p.recover()["recovered"])
        self.assertEqual(len(p.data["audit_results"]), 1)

    def test_bibliography_doi_duplicate_author_and_missing(self):
        self.prepared()
        path = self.root / "03_library/references.bib"
        original = path.read_text()
        path.write_text(original.replace("title =", "title ="))
        self.assertTrue(self.p.bibliography()["valid"])
        # Exact registered identity retained; deliberately corrupt only a test bibliography.
        key = next(iter(self.p.current_spans().values()))["citation_keys"][0]
        path.write_text(original + '\n@misc{' + key + ',title={WRONG},author={Wrong},year={1111},doi={10.9999/fictional}}')
        result = self.p.bibliography()
        codes = {f["type"] for f in result["findings"]}
        self.assertTrue({"DUPLICATE_BIBLIOGRAPHY_KEY", "TITLE_MISMATCH", "AUTHOR_MISMATCH", "YEAR_MISMATCH", "DOI_MISMATCH"} <= codes)
        path.write_text("")
        self.assertIn("MISSING_BIBLIOGRAPHY_ENTRY", {f["type"] for f in self.p.bibliography()["findings"]})

    def test_stale_bibliography(self):
        self.audited()
        path = self.root / "03_library/references.bib"
        path.write_text(path.read_text() + "\n% changed\n")
        self.assertIn("CURRENT_BIBLIOGRAPHY_RECONCILIATION_REQUIRED", self.p.final_blockers())

    def test_reverse_impact_and_evidence_change(self):
        v = self.prepared()
        eid = v["spans"][0]["evidence_ids"][0]
        self.assertEqual(self.p.impact(eid)["span_ids"], [v["spans"][0]["span_id"]])
        ev = copy.deepcopy(self.p.rp.latest("evidence")[eid])
        self.p.rp.submit("evidence", {**ev, "supersedes_revision": ev["revision_id"], "finding_argument_proposition": "FICTIONAL actual revised evidence"})
        self.p = WritingPipeline(self.root)
        self.assertTrue(self.p.span_errors(v["spans"][0]))
        self.assertFalse(self.p.validate()["valid"])

    def test_claim_change_stales_span(self):
        v = self.prepared()
        cid = v["spans"][0]["claim_ids"][0]
        old = self.p.sp.latest()[cid]
        self.p.sp.submit("claim", {**old, "supersedes_revision": old["revision_id"], "proposition": "FICTIONAL actual revised claim"})
        self.p = WritingPipeline(self.root)
        self.assertTrue(self.p.span_errors(v["spans"][0]))
        self.assertEqual(len(self.p.latest("draft")), 1)

    def test_cross_domain_no_fixed_chapters(self):
        for name in ("Archaeological interpretations", "Qualitative educational experiences", "Historical documentary argument"):
            cfg = outline(self.p)
            cfg["review_type"] = name
            validate("outline", cfg)
            self.assertNotIn("exposure", json.dumps(cfg).lower())

    def test_provisional_cannot_bypass_formal_claim_review(self):
        from unittest.mock import PropertyMock
        cid = next(iter(self.p.sp.latest("claim")))
        with patch.object(WritingPipeline, "lab", new_callable=PropertyMock, return_value=False):
            with self.assertRaisesRegex(ValueError, "UNAPPROVED_CLAIM"):
                self.p.source_bindings([cid])

    def test_audit_source_locator_and_coverage_enforced(self):
        self.prepared()
        c = self.p.audit_context("FICTIONAL auditor", "fresh")
        cfg = audit_config(c)
        next(iter(cfg["span_reviews"].values()))["source_references"][0]["document_id"] = "WRONG"
        with self.assertRaisesRegex(ValueError, "WRONG_SOURCE_LOCATOR"):
            self.p.audit_submit(c["audit_id"], cfg)

    def test_unsupported_source_and_duplicate_doi(self):
        self.prepared()
        key = next(iter(self.p.current_spans().values()))["citation_keys"][0]
        result = reconcile(self.root, {key}, set())
        self.assertIn("EXCLUDED_OR_UNSUPPORTED_SOURCE", {f["type"] for f in result["findings"]})
        path = self.root / "03_library/references.bib"
        path.write_text('@misc{A,title={One},doi={10.9999/fictional}}\n@misc{B,title={Two},doi={10.9999/fictional}}')
        result = reconcile(self.root, set(), set())
        self.assertIn("DUPLICATE_REFERENCE_DOI", {f["type"] for f in result["findings"]})

    def test_case_terms_not_in_writing_core(self):
        base = Path(__file__).resolve().parents[1] / "research_review_agent/writing"
        text = "\n".join(p.read_text() for p in base.glob("*.py")).lower()
        for term in ("social media", "political participation", "political efficacy", "university students", "tiktok", "instagram"):
            self.assertNotIn(term, text)


def finding_test(category):
    def test(self):
        result = self.audited(category)
        self.assertEqual(result["findings"][0]["finding_type"], category)
        self.assertIn("BLOCKING_OR_UNRESOLVED_SEMANTIC_FINDINGS", self.p.final_blockers())
        self.assertTrue(self.p.structural()["valid"])
    return test


for category in CHECKS:
    setattr(WritingTests, "test_recorded_semantic_finding_" + category, finding_test(category))


@unittest.skipUnless(synth.fixtures.HAS_PARSER, "Optional PDF extra required")
class WritingFormalFixtureTests(unittest.TestCase):
    def test_fictional_multi_paper_full_phase13_to18_and_human_history(self):
        from writing_fixtures import build_official
        from research_review_agent.workflow import evaluate_gates
        with tempfile.TemporaryDirectory() as name:
            temp = type("FixtureTemp", (), {"name": name})()
            root = build_official(temp)
            transition_phase(root, 13, "in_progress", allow_example_data=True)
            p = WritingPipeline(root)
            o = p.submit("outline", outline(p))["record"]
            self.assertFalse(p.completion(13)["allowed"])
            p.review(o["record_id"], "approve", "FICTIONAL human", "Test-only outline review", True)
            transition_phase(root, 13, "completed", allow_example_data=True)
            transition_phase(root, 14, "in_progress", allow_example_data=True)
            p = WritingPipeline(root)
            cfg = brief(p)
            bad = copy.deepcopy(cfg)
            bad["contradictory_evidence_ids"] = []
            with self.assertRaisesRegex(ValueError, "MISSING_CONTRADICTORY"):
                p.submit("brief", bad)
            b = p.submit("brief", cfg)["record"]
            p.review(b["record_id"], "defer", "FICTIONAL human", "Test-only request revision", True)
            p.review(b["record_id"], "approve", "FICTIONAL human", "Test-only brief review", True)
            self.assertEqual(len(p.data["reviews"]), 3)
            transition_phase(root, 14, "completed", allow_example_data=True)
            transition_phase(root, 15, "in_progress", allow_example_data=True)
            p = WritingPipeline(root)
            d = p.submit("draft", draft(p))["record"]
            with self.assertRaisesRegex(ValueError, "WRITER_CANNOT"):
                p.review(d["record_id"], "approve", "FICTIONAL writer", "Test", True)
            transition_phase(root, 15, "completed", allow_example_data=True)
            transition_phase(root, 16, "in_progress", allow_example_data=True)
            p = WritingPipeline(root)
            self.assertTrue(p.bibliography()["valid"])
            transition_phase(root, 16, "completed", allow_example_data=True)
            transition_phase(root, 17, "in_progress", allow_example_data=True)
            p = WritingPipeline(root)
            c = p.audit_context("FICTIONAL auditor", "fresh-fictional-audit")
            p.audit_submit(c["audit_id"], audit_config(c, "overclaim"))
            self.assertIn("BLOCKING_OR_UNRESOLVED_SEMANTIC_FINDINGS", p.final_blockers())
            # Test-only reevaluation, retained bad report; not an empirical model accuracy test.
            p.audit_submit(c["audit_id"], audit_config(c))
            transition_phase(root, 17, "completed", allow_example_data=True)
            transition_phase(root, 18, "in_progress", allow_example_data=True)
            p = WritingPipeline(root)
            self.assertFalse(p.completion(18)["allowed"])
            with self.assertRaisesRegex(ValueError, "WRITER_CANNOT"):
                p.signoff("approve", "FICTIONAL writer", "Test", True)
            p.signoff("defer", "FICTIONAL human", "Test-only pending decision", True)
            p.signoff("approve", "FICTIONAL human", "FICTIONAL FIXTURE ONLY; not real human evaluation", True)
            self.assertFalse(p.data["signoffs"][-1]["identity_authenticated"])
            transition_phase(root, 18, "completed", allow_example_data=True)
            p = WritingPipeline(root)
            self.assertTrue(p.completion(18)["allowed"])
            for phase, key in ((7, "gate-1-screening-before-reading"), (15, "gate-2-evidence-before-drafting"), (12, "gate-3-claims-before-gap")):
                self.assertEqual(evaluate_gates(root, phase, True)[key]["status"], "pass")
            p.signoff("reopen", "FICTIONAL human", "Test-only reopening retains approval history", True)
            self.assertFalse(p.completion(18)["allowed"])
            self.assertEqual(len(p.data["signoffs"]), 3)
