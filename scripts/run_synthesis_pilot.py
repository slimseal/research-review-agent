"""Apply explicitly authored demonstration judgments; never discover, infer or approve evidence.

Requires an isolated synthesis lab and JSON plan. Every public CLI input/output is saved.
The fixture builder creates labelled synthetic PDFs, not fake real papers or a benchmark.
"""
import argparse
import io
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from research_review_agent.state import write_json_atomic, utc_now
from research_review_agent.synthesis.contracts import CHECKS


def fictional_source(config, output):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    from research_review_agent.documents.store import initialize_lab as document_lab
    from research_review_agent.documents.pipeline import DocumentPipeline
    from research_review_agent.scholarly.registry import PaperRegistry
    from research_review_agent.scholarly.contracts import PaperCandidate
    from research_review_agent.reading.pipeline import initialize_lab, ReadingPipeline
    from research_review_agent.reading.contracts import CONTENT_FIELDS
    require_new(output)
    library = output / "library-source"
    registry = PaperRegistry(library)
    catalog, mappings = [], []
    for i, paper in enumerate(config["papers"]):
        raw = f"02_discovery/raw/fictional-{i}.json"
        write_json_atomic(library / raw, paper)
        candidate = PaperCandidate("fictional_fixture", paper["alias"], "FICTIONAL-NO-SEARCH", utc_now(), raw, 0,
                    paper["title"], ["Fictional fixture author"], 2099, "SYNTHETIC TEST ONLY", None, None,
                    "fixture", "version_of_record", None)
        pid = registry.register(candidate).paper_id
        catalog.append({"paper_id": pid, "title": paper["title"], "authors": ["Fictional fixture author"], "year": 2099, "identity_source": "explicit synthetic fixture"})
        mappings.append((paper, pid))
    # Library already contains canonical identities; marker creation requires a fresh folder.
    marker_root = output / "marker-source"
    marker = document_lab(marker_root, catalog)
    write_json_atomic(library / "DOCUMENT_LAB.json", marker)
    docs = []
    for paper, pid in mappings:
        text = paper["title"] + ". SYNTHETIC TEST ONLY. " + " ".join(e["source_text"] for e in paper["evidence"])
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        lines = textwrap.wrap(text, 85)
        if len(lines) > 48:
            raise ValueError("Fixture source exceeds one-page generator; do not silently truncate")
        content = "BT /F1 10 Tf 35 750 Td 14 TL\n"
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content += f"({escaped}) Tj T*\n"
        stream = DecodedStreamObject()
        stream.set_data((content + "ET").encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.add_metadata({"/Title": paper["title"], "/Subject": "Fictional software test; not scientific evidence"})
        buf = io.BytesIO()
        writer.write(buf)
        path = output / (paper["alias"] + ".pdf")
        path.write_bytes(buf.getvalue())
        result = DocumentPipeline(library).acquire(paper_id=pid, local=path, version_kind="version_of_record",
                   authorization={"access_basis": "researcher_asserted_authorized", "asserted_by": "synthetic fixture builder", "reason": "Newly generated fictional test PDF"})
        docs.append(result["document"]["document_id"])
    root = output / "reading-source"
    initialize_lab(root, library, config["question"], docs)
    aliases = {}
    for (paper, pid), did in zip(mappings, docs):
        p = ReadingPipeline(root)
        p.dp.parse(did)
        p = ReadingPipeline(root)
        context = p.reading_context(pid, did)
        anchor = p.dp.anchor(did, context["pages"][0]["text"], pdf_page=1)
        aid = anchor["anchor_id"]
        content = {k: {"status": "not_applicable", "reason": "Synthetic one-page engineering fixture; not an actual scientific report."} for k in CONTENT_FIELDS}
        content["research_problem"] = {"status": "present", "text": config["question"], "epistemic_role": "codex_inference", "source_anchor_ids": [aid]}
        note = p.submit("notes", {"paper_id": pid, "document_id": did, "document_sha256": context["document"]["sha256"],
            "document_version": "version_of_record", "generator": "FICTIONAL fixture builder", "reading_status": "completed", "unresolved_material": [],
            "content": content, "source_coverage": {"pages_read": [1], "visual_pages": [], "layout_assessment": "Generated single-column text fixture; no scientific figure or table.",
            "sections": [{"name": "entire synthetic source", "status": "read", "basis": "Explicit fixture text, not independently annotated research"}]}})
        for e in paper["evidence"]:
            ev = p.submit("evidence", {"paper_id": pid, "document_id": did, "document_sha256": context["document"]["sha256"],
                "reading_note_id": note["reading_note_id"], "source_anchor_ids": [aid], "research_question": config["question"],
                "source_basis": "full_text", "research_context": paper["context"], "evidence_type": "fictional_" + e["inference_class"],
                "research_types": e["research_types"], "extension_json": e.get("extension_json", {}),
                "finding_argument_proposition": e["source_text"], "limitations_uncertainty": paper["limitations"],
                "extraction_run_id": "FICTIONAL-2H", "generator": "FICTIONAL fixture builder", "example_data": True,
                "extraction_status": e.get("extraction_status", "supported"), "result_kind": e["result_kind"],
                "inference_class": e["inference_class"], "citation_basis": e.get("citation_basis", "primary_in_this_source"),
                "secondary_source_reference": e.get("secondary_source_reference", ""), "source_scope": "body_text",
                "support_boundaries": {"source_reports": e["source_text"], "author_interpretation": "FICTIONAL source statement only",
                    "codex_inference": "No real-world finding follows", "uncertainty": paper["limitations"], "cannot_support": "Actual scientific conclusions or real-world effects"}})
            aliases[e["alias"]] = ev["evidence_id"]
    write_json_atomic(output / "evidence-aliases.json", aliases)
    return root, aliases


def require_new(path):
    path.mkdir(parents=True, exist_ok=False)


def run(args):
    plan = json.loads(args.plan.read_text())
    if args.fixture:
        source, aliases = fictional_source(json.loads(args.fixture.read_text()), args.project.parent / (args.project.name + "-fixtures"))
    else:
        source, aliases = args.source, plan["evidence_aliases"]
    from research_review_agent.documents.parser import checksum
    before = {str(p.relative_to(source)): checksum(p) for p in source.rglob("*") if p.is_file()}
    if args.project.exists():
        raise ValueError("New pilot directory required")
    commands = []
    output = args.project.parent / (args.project.name + "-execution")
    require_new(output)
    def call(command, *parts, expected=0):
        cmd = [sys.executable, "-m", "research_review_agent", command, "--project", str(args.project), *map(str, parts)]
        result = subprocess.run(cmd, text=True, capture_output=True)
        commands.append({"command": cmd, "exit_code": result.returncode, "expected": expected, "stdout": result.stdout, "stderr": result.stderr})
        write_json_atomic(output / "commands.json", commands)
        if result.returncode != expected:
            raise RuntimeError(result.stdout + result.stderr)
        return json.loads(result.stdout)
    def input_call(command, name, value, *parts):
        path = output / (name + ".json")
        write_json_atomic(path, value)
        return call(command, *parts, "--config", path)
    call("synthesis-lab-init", "--source", source)
    context = call("synthesis-context")
    evidence = {v["evidence_id"]: v for v in context["evidence"]}
    ids = list(evidence)
    input_call("synthesis-corpus", "corpus", {"evidence_decisions": {e: {"disposition": "include", "reason": "Keep support, counterevidence and uncertainty visible in this provisional pilot"} for e in ids},
        "coverage_limitations": plan["coverage_limitations"], "search_coverage": plan["search_coverage"], "selection_rationale": plan["selection_rationale"]})
    def resolve(v):
        if isinstance(v, str):
            return aliases.get(v, v)
        if isinstance(v, list):
            return [resolve(x) for x in v]
        if isinstance(v, dict):
            return {aliases.get(k, k): resolve(x) for k, x in v.items()}
        return v
    records = []
    for spec in plan["records"]:
        authored = resolve(spec["content"])
        value = {"research_question": context["protocol"]["research_question"], "record_refs": [],
                 "generator": "Codex authored provisional Round 2H analysis", "example_data": True, **authored}
        if spec["kind"] == "claim":
            decisions = value["evidence_decisions"]
            for eid in ids:
                decisions.setdefault(eid, {"relation": "not_relevant", "rationale": plan["irrelevance_rationale"]})
            value["evidence_ids"] = [e for e, d in decisions.items() if d["relation"] != "not_relevant"]
        if spec["kind"] == "assessment":
            value["evidence_ids"] = ids
        record = input_call("synthesis-submit", spec["alias"], value, "--kind", spec["kind"])["record"]
        aliases[spec["alias"]] = record["record_id"]
        checks = {k: {"status": "pass", "reason": reason} for k, reason in plan["semantic_checks"].items()}
        checks.update(spec.get("semantic_check_overrides", {}))
        evidence_checks = {e: plan["evidence_assessments"][next(a for a, target in aliases.items() if target == e)] for e in record["evidence_ids"]}
        assessment = {"outcome": spec.get("semantic_outcome", "supported"), "reviewer": "Codex self-review, not independent human validation",
                      "rationale": spec["semantic_rationale"], "checks": checks, "evidence_checks": evidence_checks}
        input_call("synthesis-assess", spec["alias"] + "-semantic", assessment, "--id", record["record_id"])
        records.append(record)
    # Independent link rows are explicit authored judgments, not generated from a title match.
    result = call("synthesis-validate")
    gate = call("synthesis-completion", "--phase", 12, expected=2)
    after = {str(p.relative_to(source)): checksum(p) for p in source.rglob("*") if p.is_file()}
    report = {"structural_validation": result, "completion": gate, "source_unchanged": before == after,
              "source_checksums": before, "human_approvals": 0, "independent_semantic_validation": False,
              "aliases": aliases, "records": len(records), "notice": plan["coverage_limitations"]}
    write_json_atomic(output / "result.json", report)
    write_json_atomic(args.project / "SYNTHESIS_VALIDATION_REPORT.json", report)
    (args.project / "SYNTHESIS_VALIDATION_REPORT.md").write_text("# Provisional synthesis pilot\n\n" + plan["coverage_limitations"] +
        "\n\nStructure valid: " + str(result["valid"]) + ". Official completion blocked: " + str(not gate["allowed"]) +
        ". Original source unchanged: " + str(before == after) + ".\n\nZero human approvals; no independent semantic validation or accuracy score.\n", encoding="utf-8")
    print(json.dumps({"structural_validation": result["valid"], "source_unchanged": before == after, "records": len(records), "human_approvals": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", type=Path)
    group.add_argument("--fixture", type=Path)
    run(parser.parse_args())
