"""FICTIONAL engineering assertions, including fictional reviewers; NOT scientific gold standards."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_reading as fixtures
from research_review_agent.synthesis.pipeline import SynthesisPipeline, initialize_lab
from research_review_agent.synthesis.contracts import CHECKS, TEXT_FIELDS, validate_record, schema
from research_review_agent.reading.pipeline import ReadingPipeline
from research_review_agent.state import load_state, persist_state
from research_review_agent.workflow import transition_phase, evaluate_gates


def config(p, kind, **overrides):
    ids = p.corpus()["included_evidence_ids"]
    value = {k: "FICTIONAL bounded methodological comparison" for k in TEXT_FIELDS[kind]}
    value.update(research_question=p.corpus()["research_question"], evidence_ids=ids, record_refs=[],
                 uncertainty="FICTIONAL engineering data only", generator="FICTIONAL test", example_data=True)
    if kind in {"theme", "theory", "controversy"}:
        value.update(supporting_evidence_ids=ids, qualifying_evidence_ids=[], contradictory_evidence_ids=[])
    if kind == "theme":
        value["comparisons"] = [{"dimension": "concept definitions", "assessment": "FICTIONAL same term is not proof of commensurate measurement",
                                 "comparability": "uncertain", "evidence_ids": ids}]
    if kind == "theory":
        value["mechanism_status"] = "proposed"
    if kind == "controversy":
        value["positions"] = [{"proposition": "FICTIONAL position A", "evidence_ids": ids}, {"proposition": "FICTIONAL position B", "evidence_ids": ids}]
    if kind == "boundary":
        value.update(basis_level="cross_study_suggested", record_refs=list(p.latest("theme")))
    if kind == "claim":
        value.update(claim_type="theoretical", generalization="source_bounded",
                     evidence_decisions={e: {"relation": "supports", "rationale": "FICTIONAL test support"} for e in ids})
    if kind == "link":
        value.update(claim_id=next(iter(p.latest("claim"))), evidence_id=ids[0], evidence_ids=[ids[0]], relation="supports", directness="direct_source")
    if kind == "gap":
        value.update(gap_type="methodological_limitation", scope="reviewed_corpus", basis_kind="documented_design_limit",
                     derivation="Within the reviewed and retrieved corpus, the FICTIONAL design cannot discriminate the alternatives.",
                     record_refs=list(p.latest("claim")))
    value.update(overrides)
    return value


def semantic(v, outcome="supported"):
    return {"outcome": outcome, "reviewer": "FICTIONAL model assessment", "rationale": "Test-only review, not independent validation",
            "checks": {k: {"status": "pass", "reason": "FICTIONAL structural test assertion only"} for k in CHECKS},
            "evidence_checks": {e: "Fictional test evidence inspected by fixture, not scientific validation" for e in v["evidence_ids"]}}


def corpus_config(p):
    return {"evidence_decisions": {e: {"disposition": "include", "reason": "FICTIONAL test inclusion"} for e in p.rp.latest("evidence")},
            "coverage_limitations": "FICTIONAL corpus only", "search_coverage": "No real search executed", "selection_rationale": "Engineering validation"}


class SynthesisContractTests(unittest.TestCase):
    def test_contract_no_model_runtime(self):
        self.assertEqual(len(schema()["semantic_checks"]), 12)
        self.assertEqual(len(schema()["relations"]), 5)

    def test_empty_record_rejected(self):
        for kind in TEXT_FIELDS:
            with self.assertRaises(ValueError):
                validate_record(kind, {})

    def test_legacy_schema_fields_unchanged(self):
        from research_review_agent.constants import csv_fields_for_version
        self.assertEqual(csv_fields_for_version("1.0.0")["claim"], csv_fields_for_version("2.0.0")["claim"])


@unittest.skipUnless(fixtures.HAS_PARSER, "PDF extra needed for source-grounded fictional integrations")
class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.h = fixtures.ReadingTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.h.p.submit("evidence", self.h.ecfg)
        self.root = self.h.h.base / "synthesis"
        initialize_lab(self.root, self.h.root)
        self.p = SynthesisPipeline(self.root)
        self.p.create_corpus(corpus_config(self.p))

    def submit(self, kind, **changes):
        return self.p.submit(kind, config(self.p, kind, **changes))["record"]

    def reviewed(self, kind, **changes):
        v = self.submit(kind, **changes)
        self.p.assess(v["record_id"], semantic(v))
        self.p.review(v["record_id"], "approve", "FICTIONAL reviewer", "Test-only approval; never a real pilot")
        return v

    def assessment(self, kind):
        return self.reviewed("assessment", map_kind=kind, record_refs=list(self.p.latest(kind)),
                             disposition="populated" if self.p.latest(kind) else "none_warranted")

    def official(self):
        self.h.official()
        ev = self.h.p.submit("evidence", self.h.ecfg)
        self.h.p.review("evidence", ev["evidence_id"], "accept", "FICTIONAL reviewer", "Synthetic acceptance")
        self.h.p.close_extraction(self.h.pid, "complete", "Synthetic full extraction", "FICTIONAL reviewer")
        transition_phase(self.h.root, 8, "completed", allow_example_data=True)
        transition_phase(self.h.root, 9, "in_progress", allow_example_data=True)
        self.root = self.h.root
        self.p = SynthesisPipeline(self.root)
        c = self.p.create_corpus(corpus_config(self.p))
        self.p.review(c["corpus_id"], "approve", "FICTIONAL reviewer", "Synthetic corpus approval")

    def through_claims(self):
        self.official()
        self.reviewed("theme")
        self.reviewed("method")
        for kind in ("theme", "theory", "method", "controversy"):
            self.assessment(kind)
        transition_phase(self.root, 9, "completed", allow_example_data=True)
        transition_phase(self.root, 10, "in_progress", allow_example_data=True)
        self.p = SynthesisPipeline(self.root)
        self.reviewed("boundary")
        self.assessment("boundary")
        transition_phase(self.root, 10, "completed", allow_example_data=True)
        transition_phase(self.root, 11, "in_progress", allow_example_data=True)
        self.p = SynthesisPipeline(self.root)
        refs = [v["record_id"] for v in self.p.latest().values() if v["kind"] in {"theme", "method", "boundary"}]
        claim = self.reviewed("claim", record_refs=refs)
        self.reviewed("link", claim_id=claim["record_id"])
        self.assessment("claim")
        return claim

    def test_corpus_accounts_every_item(self):
        with self.assertRaisesRegex(ValueError, "EVERY_EVIDENCE"):
            self.p.create_corpus({**corpus_config(self.p), "evidence_decisions": {}})

    def test_corpus_coverage_required(self):
        with self.assertRaisesRegex(ValueError, "coverage_limitations"):
            self.p.create_corpus({**corpus_config(self.p), "coverage_limitations": ""})

    def test_unknown_evidence(self):
        with self.assertRaisesRegex(ValueError, "NOT_IN_SYNTHESIS_CORPUS"):
            self.submit("method", evidence_ids=["unknown"])

    def test_wrong_anchor_invalidates_trace(self):
        v = self.submit("method")
        p = ReadingPipeline(self.root)
        state = load_state(self.root)
        state["reading_data"]["evidence"][-1]["source_anchor_ids"] = ["wrong-anchor"]
        persist_state(self.root, state, "FICTIONAL_corruption_test")
        p = SynthesisPipeline(self.root)
        self.assertTrue(p.stale(v))
        self.assertFalse(p.validate()["valid"])

    def test_provisional_cannot_approve(self):
        v = self.submit("theme")
        self.p.assess(v["record_id"], semantic(v))
        with self.assertRaisesRegex(ValueError, "LAB_CANNOT"):
            self.p.review(v["record_id"], "approve", "not a human", "attempt")
        self.assertFalse(self.p.completion()["allowed"])

    def test_source_trace_contains_note_anchor_document(self):
        v = self.submit("method")
        result = self.p.inspect(v["record_id"])
        trace = result["trace"][0]
        self.assertTrue(trace["record"]["reading_note_id"])
        self.assertTrue(trace["record"]["document_sha256"])
        self.assertTrue(trace["anchors"])

    def test_all_four_maps_and_boundary(self):
        for kind in ("theme", "theory", "method", "controversy", "boundary"):
            self.submit(kind)
        self.assertTrue(self.p.validate()["valid"])

    def test_same_paper_not_independent_support(self):
        v = self.submit("claim", claims_consensus=True)
        self.assertIn("MULTIPLE_ITEMS_NOT_INDEPENDENT_STUDIES", self.p.wording_checks(v))

    def test_causal_overclaim_structurally_valid_not_approved(self):
        v = self.submit("claim", claim_type="causal")
        self.assertTrue(self.p.validate()["valid"])
        with self.assertRaisesRegex(ValueError, "OVERCLAIM"):
            self.p.assess(v["record_id"], semantic(v))

    def test_prediction_not_causal_proof(self):
        v = self.submit("claim", claim_type="causal", proposition="FICTIONAL prediction establishes cause")
        self.assertIn("CAUSAL_UPGRADE_NOT_SUPPORTED", self.p.wording_checks(v))

    def test_generalization_blocked(self):
        v = self.submit("claim", generalization="beyond_sources")
        self.assertTrue(self.p.wording_checks(v))

    def test_boundary_test_not_inferred_from_cross_study(self):
        self.submit("theme")
        v = self.submit("boundary", basis_level="explicitly_tested")
        self.assertIn("CROSS_STUDY_DIFFERENCE_IS_NOT_TESTED_MODERATION", self.p.wording_checks(v))

    def test_theory_proposed_not_tested(self):
        v = self.submit("theory", mechanism_status="empirically_tested")
        self.assertTrue(self.p.wording_checks(v))

    def test_secondary_not_primary(self):
        self.submit("claim")
        v = self.submit("link")
        # Mutation is only to the in-memory check input, not canonical evidence.
        ev = self.p.rp.latest("evidence", v["evidence_id"])
        ev["citation_basis"] = "secondary_report"
        self.assertIn("SECONDARY_REPORT_IS_NOT_PRIMARY_VERIFICATION", self.p.wording_checks(v))

    def test_uncertain_not_verified(self):
        v = self.submit("claim")
        self.p.rp.latest("evidence", v["evidence_ids"][0])["extraction_status"] = "uncertain"
        self.assertIn("UNCERTAIN_EVIDENCE_CANNOT_BE_VERIFIED_SUPPORT", self.p.wording_checks(v))

    def test_counterevidence_ledger_required(self):
        with self.assertRaisesRegex(ValueError, "COUNTEREVIDENCE"):
            self.submit("claim", evidence_decisions={})

    def test_unsupported_consensus_with_contradiction(self):
        eid = self.p.corpus()["included_evidence_ids"][0]
        v = self.submit("claim", claims_consensus=True, evidence_decisions={eid: {"relation": "contradicts", "rationale": "FICTIONAL counterexample"}})
        self.assertIn("CONSENSUS_WITH_UNRESOLVED_DISAGREEMENT", self.p.wording_checks(v))

    def test_semantic_null_omission_cannot_be_supported(self):
        v = self.submit("claim")
        cfg = semantic(v)
        cfg["checks"]["null_results"] = {"status": "fail", "reason": "FICTIONAL omitted null finding"}
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_SEMANTIC"):
            self.p.assess(v["record_id"], cfg)

    def test_semantic_measurement_comparison_not_automatic(self):
        v = self.submit("theme")
        self.assertEqual(v["comparisons"][0]["comparability"], "uncertain")
        self.assertIsNone(self.p.semantics_for(v))

    def test_research_question_mismatch(self):
        with self.assertRaisesRegex(ValueError, "RESEARCH_QUESTION_MISMATCH"):
            self.submit("method", research_question="Unrelated fictional question")

    def test_search_coverage_change_stales_corpus(self):
        from research_review_agent.state import write_json_atomic
        write_json_atomic(self.root / "01_search/FICTIONAL_NEW_SCOPE.json", {"notice": "Synthetic change"})
        self.assertIn("CORPUS_SEARCH_COVERAGE_CHANGED", self.p.corpus_errors())

    def test_map_change_stales_claim(self):
        theme = self.submit("theme")
        claim = self.submit("claim", record_refs=[theme["record_id"]])
        self.p.submit("theme", {**config(self.p, "theme"), "record_id": theme["record_id"], "supersedes_revision": theme["revision_id"], "definition": "FICTIONAL revision"})
        self.assertTrue(self.p.stale(claim))

    def test_empty_controversy_cannot_fabricate_positions(self):
        with self.assertRaisesRegex(ValueError, "TWO_DOCUMENTED"):
            self.submit("controversy", positions=[])

    def test_unknown_forward_reference(self):
        claim = self.submit("claim")
        with self.assertRaisesRegex(ValueError, "CYCLIC_OR_FORWARD"):
            self.submit("method", record_refs=[claim["record_id"]])

    def test_link_relation_must_match_claim(self):
        self.submit("claim")
        with self.assertRaisesRegex(ValueError, "DISPOSITION_MISMATCH"):
            self.submit("link", relation="contradicts")

    def test_multiple_claims_one_evidence_and_duplicate_link_guard(self):
        c1, c2 = self.submit("claim"), self.submit("claim", proposition="FICTIONAL second proposition")
        self.submit("link", claim_id=c1["record_id"])
        self.submit("link", claim_id=c2["record_id"])
        self.assertEqual(len(self.p.latest("link")), 2)
        with self.assertRaisesRegex(ValueError, "REVISE_EXISTING"):
            self.submit("link", claim_id=c1["record_id"])

    def test_unknown_claim(self):
        self.submit("claim")
        with self.assertRaisesRegex(ValueError, "UNKNOWN_CLAIM"):
            self.submit("link", claim_id="bad")

    def test_gap_without_claim_rejected(self):
        with self.assertRaisesRegex(ValueError, "GAP_CLAIM"):
            self.submit("gap")

    def test_coverage_shortfall_not_substantive_gap(self):
        self.submit("claim")
        with self.assertRaisesRegex(ValueError, "NOT_RESEARCH_GAP"):
            self.submit("gap", basis_kind="small_corpus")

    def test_field_wide_novelty_blocked(self):
        self.submit("claim")
        with self.assertRaisesRegex(ValueError, "NOVELTY"):
            self.submit("gap", scope="entire_field")

    def test_gap_wording_is_bounded(self):
        self.submit("claim")
        with self.assertRaisesRegex(ValueError, "BOUNDED_WORDING"):
            self.submit("gap", derivation="No previous study has ever investigated this")

    def test_claim_change_stales_link_and_gap(self):
        v = self.submit("claim")
        link = self.submit("link")
        gap = self.submit("gap")
        self.p.submit("claim", {**config(self.p, "claim"), "record_id": v["record_id"], "supersedes_revision": v["revision_id"], "scope": "FICTIONAL revised scope"})
        self.assertTrue(self.p.stale(link))
        self.assertTrue(self.p.stale(gap))

    def test_link_change_stales_gap(self):
        self.submit("claim")
        v = self.submit("link")
        gap = self.submit("gap")
        self.p.submit("link", {**config(self.p, "link"), "record_id": v["record_id"], "supersedes_revision": v["revision_id"], "rationale": "FICTIONAL revised rationale"})
        self.assertTrue(self.p.stale(gap))

    def test_evidence_change_stales_claim(self):
        v = self.submit("claim")
        rp = ReadingPipeline(self.root)
        ev = rp.latest("evidence", v["evidence_ids"][0])
        rp.submit("evidence", {**ev, "supersedes_revision": ev["revision_id"], "finding_argument_proposition": "FICTIONAL revised argument"})
        self.p = SynthesisPipeline(self.root)
        self.assertTrue(self.p.stale(v))
        self.assertIn("CORPUS_EVIDENCE_MATRIX_CHANGED", self.p.corpus_errors())

    def test_legacy_csv_archived_before_export(self):
        self.assertTrue((self.root / "08_argument/CLAIM_MAP.csv").exists())
        self.assertIn("supporting_evidence", (self.root / "08_argument/CLAIM_MAP.csv").read_text())

    def test_no_example_terms_in_core(self):
        package = Path(__file__).resolve().parents[1] / "research_review_agent/synthesis"
        for path in package.glob("*.py"):
            for term in ("political efficacy", "tiktok", "instagram", "social media", "political participation", "university students"):
                self.assertNotIn(term, path.read_text().lower())

    def test_semantics_is_not_automatic_entailment(self):
        v = self.submit("claim")
        s = semantic(v, "unsupported")
        s["checks"]["historical_inference"] = {"status": "fail", "reason": "FICTIONAL interpretation is not observation"}
        self.p.assess(v["record_id"], s)
        self.assertFalse(self.p.approved(v))
        self.assertFalse(self.p.validate()["semantic_accuracy_validated"])

    def test_recovery_preserves_versions_and_edits_need_preservation(self):
        v = self.submit("theme")
        path = self.root / "07_synthesis/THEME_MAP.md"
        path.write_text("FICTIONAL unexpected manual edit")
        self.assertFalse(self.p.validate()["valid"])
        # Explicitly preserve the user's edit before regenerating projections.
        path.with_suffix(".manual.txt").write_bytes(path.read_bytes())
        (self.root / ".review/state.json").write_text("broken")
        from research_review_agent.state import recover_state
        recover_state(self.root)
        self.p = SynthesisPipeline(self.root)
        self.assertTrue(self.p.recover()["valid"])
        self.assertEqual(self.p.latest("theme")[v["record_id"]]["revision_id"], v["revision_id"])

    def test_concurrent_stale_instance_rejected(self):
        other = SynthesisPipeline(self.root)
        self.submit("method")
        with self.assertRaisesRegex(ValueError, "RELOAD"):
            other.submit("method", config(other, "method"))

    def test_empty_assessment_does_not_invent_controversy(self):
        v = self.submit("assessment", map_kind="controversy", disposition="none_warranted")
        self.assertEqual(v["record_refs"], [])

    def test_gate3_positive_fictional_end_to_end_and_gap(self):
        self.through_claims()
        self.assertTrue(self.p.completion(11)["allowed"], self.p.completion(11))
        transition_phase(self.root, 11, "completed", allow_example_data=True)
        self.assertEqual(evaluate_gates(self.root, 12, True)["gate-3-claims-before-gap"]["status"], "pass")
        transition_phase(self.root, 12, "in_progress", allow_example_data=True)
        self.p = SynthesisPipeline(self.root)
        self.reviewed("gap")
        self.assessment("gap")
        transition_phase(self.root, 12, "completed", allow_example_data=True)

    def test_human_review_correction_history_and_reopen(self):
        self.official()
        v = self.reviewed("theme")
        self.p.review(v["record_id"], "reopen", "FICTIONAL reviewer", "Reconsider comparability")
        self.assertFalse(self.p.approved(v))
        changed = self.p.review(v["record_id"], "revise", "FICTIONAL reviewer", "Narrow scope", {"interpretation": "FICTIONAL narrowed interpretation"})["record"]
        self.assertEqual(changed["version"], 2)
        self.assertFalse(self.p.approved(changed))
        self.assertEqual(len(self.p.inspect(v["record_id"])["history"]), 2)

    def test_rejected_candidate_retained_but_not_usable_as_support(self):
        self.official()
        theme = self.submit("theme")
        self.p.review(theme["record_id"], "reject", "FICTIONAL reviewer", "Unsupported fictional grouping")
        self.assertTrue(self.p.retired(theme))
        self.assertIn(theme["record_id"], self.p.latest("theme"))
        with self.assertRaisesRegex(ValueError, "REJECTED_REFERENCE"):
            self.p.dependencies("claim", config(self.p, "claim", record_refs=[theme["record_id"]]))

    def test_semantic_update_revokes_previous_human_approval(self):
        self.official()
        v = self.reviewed("theme")
        self.assertTrue(self.p.approved(v))
        self.p.assess(v["record_id"], semantic(v, "uncertain"))
        self.assertFalse(self.p.approved(v))


    def test_header_and_unreviewed_claim_cannot_pass_gate3(self):
        self.submit("claim")
        blockers = self.p.completion(11)["blockers"]
        self.assertTrue(any("REVIEW_REQUIRED" in b for b in blockers))
        self.assertTrue(any("LINK_COVERAGE" in b for b in blockers))

    def test_six_research_type_combinations_not_forced_to_effect_sizes(self):
        combinations = [[x] for x in self.p.rp.context()["research_types"]]
        combinations.append(self.p.rp.context()["research_types"])
        self.assertEqual(len(combinations), 6)
        rp = ReadingPipeline(self.root)
        original = next(iter(rp.latest("evidence").values()))
        rows = []
        for types in combinations:
            cfg = {k: v for k, v in original.items() if k not in {"evidence_id", "revision_id"}}
            cfg.update(research_types=types, extension_json={}, finding_argument_proposition="FICTIONAL " + ",".join(types))
            rows.append(rp.submit("evidence", cfg))
        self.p = SynthesisPipeline(self.root)
        self.p.create_corpus(corpus_config(self.p))
        for row, types in zip(rows, combinations):
            v = self.submit("method", evidence_ids=[row["evidence_id"]], identification_applicability="Not applicable to this fictional interpretation")
            self.assertNotIn("effect_size", v)
            self.assertEqual(v["research_types"], sorted(types))


@unittest.skipUnless(fixtures.HAS_PARSER, "PDF extra needed for complete fictional CLI pilot")
class MultiPaperPilotTests(unittest.TestCase):
    def test_comparative_multi_paper_cli_pipeline(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "pilot"
            run = subprocess.run([sys.executable, str(repo / "scripts/run_synthesis_pilot.py"), "--project", str(root),
                "--plan", str(repo / "examples/round2h-synthesis/fictional-plan.json"),
                "--fixture", str(repo / "examples/round2h-synthesis/fictional-corpus.json")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            p = SynthesisPipeline(root)
            self.assertTrue(p.validate()["valid"])
            self.assertEqual(len(p.rp.latest("evidence")), 8)
            self.assertEqual(len({e["paper_id"] for e in p.rp.latest("evidence").values()}), 4)
            self.assertEqual(len(next(iter(p.latest("theme").values()))["contributing_paper_ids"]), 2)
            self.assertTrue({"null", "mixed", "negative", "uncertain"} <= {e["result_kind"] for e in p.rp.latest("evidence").values()})
            self.assertTrue({"supports", "contradicts", "qualifies", "context", "uncertain"} <= {e["relation"] for e in p.latest("link").values()})
            self.assertFalse(p.completion(12)["allowed"])
            self.assertTrue(any(p.semantics_for(c)["outcome"] == "unsupported" for c in p.latest("claim").values()))
