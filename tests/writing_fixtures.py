"""Explicitly FICTIONAL multi-paper, HUMAN-APPROVAL TEST FIXTURE. Never real research."""
from pathlib import Path
import json
from dataclasses import replace
from unittest.mock import patch
import test_citations as citations
import test_screening as screening
import test_reading as reading
import test_synthesis as synthesis
from research_review_agent.documents.pipeline import DocumentPipeline
from research_review_agent.reading.pipeline import ReadingPipeline
from research_review_agent.screening.pipeline import ScreeningPipeline
from research_review_agent.synthesis.pipeline import SynthesisPipeline
from research_review_agent.state import write_json_atomic
from research_review_agent.workflow import transition_phase
from tests.pdf_fixtures import pdf_bytes


def build_official(temp):
    """Exercise actual APIs; no hand-written phase flags or approval state."""
    helper = citations.CitationTests()
    helper.temp = temp
    # Dedicated ASCII metadata fixture: the minimal synthetic PDF font is not CJK-capable.
    page = citations.fetched_page("openalex", "page1.json")
    payload = json.loads(page.body)
    payload["results"][1]["display_name"] = "Fictional contrasting coordination account"
    payload["results"][1]["authorships"] = [{"author": {"display_name": "Fictional Fixture Author"}}]
    payload["results"][1]["type"] = "article"
    payload["results"][1]["primary_location"]["version"] = "publishedVersion"
    page = replace(page, body=json.dumps(payload).encode(), payload=payload, records=payload["results"])
    with patch.object(citations, "fetched_page", return_value=page):
        cp = helper.official()
    root = cp.root
    cp.start("crossref", "backward")
    cp.review("FICTIONAL reviewer", "Test-only stop", "Fictional bounded corpus", "human_stop")
    transition_phase(root, 4, "completed")
    transition_phase(root, 5, "in_progress")
    p = ScreeningPipeline(root)
    docs, texts = {}, {}
    for i, (pid, record) in enumerate(p.registry.data["records"].items()):
        text = ("FICTIONAL TEST ONLY. " + (record.get("doi") or "") + " " + record["title"] + ". " +
                ("Case A describes improved coordination under local support. " if i == 0 else
                 "Case B describes reduced coordination; a second observation shows no change. ") +
                "Synthetic qualitative account, no causal identification or field-wide inference. Version of record.")
        path = Path(temp.name) / (pid + ".pdf")
        path.write_bytes(pdf_bytes(text=text))
        acquired = DocumentPipeline(root).acquire(paper_id=pid, local=path, version_kind="version_of_record",
                    authorization={"access_basis": "researcher_asserted_authorized", "asserted_by": "FICTIONAL builder", "reason": "Synthetic PDF created for offline test"})
        docs[pid], texts[pid] = acquired["document"]["document_id"], text
    write_json_atomic(root / "03_library/ACQUISITION_REVIEW.json", {"reviewed_by": "FICTIONAL reviewer", "reviewed_at": "2099-01-01",
                       "papers": {pid: {"status": "acquired", "document_id": did, "basis": "Synthetic PDF"} for pid, did in docs.items()}})
    transition_phase(root, 5, "completed")
    transition_phase(root, 6, "in_progress")
    p = ScreeningPipeline(root)
    p.register(screening.config(p), "FICTIONAL protocol mapping")
    p.approve_criteria("FICTIONAL reviewer", "Test-only explicit criteria approval")
    for pid, did in docs.items():
        for stage in ("title", "abstract", "fulltext_eligibility"):
            packet = p.stage_context(pid, stage, did if stage == "fulltext_eligibility" else None, [1] if stage == "fulltext_eligibility" else None)
            facts = [{"location": "1", "quote": packet["pages"][0]["text"], "purpose": purpose} for purpose in ("identity", "eligibility", "version")] if stage == "fulltext_eligibility" else None
            v = p.propose(screening.proposal(p, packet, "defer" if stage == "abstract" else "include", facts=facts))
            p.review(v["decision_id"], "approve", "FICTIONAL reviewer", "Test-only eligibility approval")
    transition_phase(root, 6, "completed")
    transition_phase(root, 7, "in_progress")
    notes = []
    for pid, did in docs.items():
        p = ReadingPipeline(root)
        p.dp.parse(did)
        p = ReadingPipeline(root)
        context = p.reading_context(pid, did)
        anchor = p.dp.anchor(did, context["pages"][0]["text"], pdf_page=1)
        note = p.submit("notes", reading.note_config(p, pid, did, anchor["anchor_id"]))
        p.review("notes", note["reading_note_id"], "accept", "FICTIONAL reviewer", "Test-only source reading")
        notes.append(note)
    transition_phase(root, 7, "completed")
    transition_phase(root, 8, "in_progress")
    evs = []
    for i, note in enumerate(notes):
        p = ReadingPipeline(root)
        for kind in (["positive"] if i == 0 else ["contradictory", "null"]):
            cfg = reading.evidence_config(p, note, kind)
            cfg.update(research_types=["qualitative_empirical"], inference_class="interpretive",
                       finding_argument_proposition="FICTIONAL " + kind + " account; " + texts[note["paper_id"]],
                       extension_json={"participants_or_cases": "Synthetic cases", "data_collection": "Fictional accounts", "analytic_approach": "Test-only comparison"})
            ev = p.submit("evidence", cfg)
            p.review("evidence", ev["evidence_id"], "accept", "FICTIONAL reviewer", "Synthetic extraction approval")
            evs.append(ev)
        p.close_extraction(note["paper_id"], "complete", "Test-only complete extraction", "FICTIONAL reviewer")
    transition_phase(root, 8, "completed", allow_example_data=True)
    transition_phase(root, 9, "in_progress", allow_example_data=True)
    p = SynthesisPipeline(root)
    c = p.create_corpus(synthesis.corpus_config(p))
    p.review(c["corpus_id"], "approve", "FICTIONAL reviewer", "Synthetic corpus approval")
    def reviewed(kind, **changes):
        v = p.submit(kind, synthesis.config(p, kind, **changes))["record"]
        p.assess(v["record_id"], synthesis.semantic(v))
        p.review(v["record_id"], "approve", "FICTIONAL reviewer", "Test-only academic judgment assertion")
        return v
    def assess(kind):
        return reviewed("assessment", map_kind=kind, record_refs=list(p.latest(kind)), disposition="populated" if p.latest(kind) else "none_warranted")
    reviewed("theme")
    reviewed("method")
    for kind in ("theme", "theory", "method", "controversy"):
        assess(kind)
    transition_phase(root, 9, "completed", allow_example_data=True)
    transition_phase(root, 10, "in_progress", allow_example_data=True)
    p = SynthesisPipeline(root)
    reviewed("boundary")
    assess("boundary")
    transition_phase(root, 10, "completed", allow_example_data=True)
    transition_phase(root, 11, "in_progress", allow_example_data=True)
    p = SynthesisPipeline(root)
    decisions = {e["evidence_id"]: {"relation": "supports" if e["result_kind"] == "positive" else "contradicts" if e["result_kind"] == "contradictory" else "qualifies", "rationale": "FICTIONAL contrasting/null account retained"} for e in evs}
    claim = reviewed("claim", claim_type="interpretive", proposition="Within the fictional cases, favorable accounts are not universal; adverse and no-change accounts qualify them.",
                     record_refs=[v["record_id"] for v in p.latest().values() if v["kind"] in {"theme", "method", "boundary"}], evidence_decisions=decisions)
    for eid, decision in decisions.items():
        reviewed("link", claim_id=claim["record_id"], evidence_id=eid, evidence_ids=[eid], relation=decision["relation"])
    assess("claim")
    transition_phase(root, 11, "completed", allow_example_data=True)
    transition_phase(root, 12, "in_progress", allow_example_data=True)
    p = SynthesisPipeline(root)
    reviewed("gap")
    assess("gap")
    transition_phase(root, 12, "completed", allow_example_data=True)
    return root
