"""Execute explicitly authored evaluation plans; no autonomous science or real approvals.

Fictional mode alone imports TEST fixtures with fictional review assertions. Real mode
is an isolated provisional lab; every CLI call and input is retained in a new directory.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from research_review_agent.state import write_json_atomic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["real", "fictional"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("NEW_PILOT_DIRECTORY_REQUIRED")
    root = args.output / "project"
    log = args.output / "execution"
    log.mkdir(parents=True)
    calls = []
    def cli(command, config=None, extra=(), expected=0):
        argv = [sys.executable, "-m", "research_review_agent", command, "--project", str(root), *extra]
        if config is not None:
            path = log / (f"{len(calls):03d}-input.json")
            write_json_atomic(path, config)
            argv += ["--config", str(path)]
        result = subprocess.run(argv, text=True, capture_output=True)
        calls.append({"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        write_json_atomic(log / "commands.json", calls)
        if result.returncode != expected:
            raise ValueError(result.stderr or result.stdout)
        return json.loads(result.stdout)
    if args.mode == "real":
        from research_review_agent.writing.pipeline import WritingPipeline
        cli("writing-lab-init", extra=("--source", str(args.source)))
        plan = json.loads(args.plan.read_text())
        sections = plan["sections"]
        outline = {"review_type": "Source-bounded paragraph evaluation, not a literature synthesis", "target_word_count": 350,
                   "argument_progression": "Separate design rationale, secondary definition, configuration and limitations",
                   "coverage_limitations": "Two software-description papers; no comparative efficacy corpus or coherent field-wide review",
                   "gap_connection": "No research gap asserted; synthesis gap assessment remains deferred",
                   "duplication_policy": "Each source-limited claim once, plus explicitly labeled adversarial audit probes",
                   "generator": "Codex Round2I writer", "example_data": False,
                   "section_structure": [{"section_id": s["section_id"], "title": s["title"], "purpose": s["purpose"],
                      "argument_progression": s["purpose"], "planned_counterarguments": "Preserve source limitations; do not invent contradiction between unrelated toolkits",
                      "claim_ids": [c["id"] for c in s["claims"]], "gap_ids": []} for s in sections]}
        cli("writing-submit", outline, ("--kind", "outline"))
        for s in sections:
            p = WritingPipeline(root)
            ids = [c["id"] for c in s["claims"]]
            links = p.links(ids)
            evs = p.rp.latest("evidence")
            brief = {"section_id": s["section_id"], "purpose": s["purpose"], "central_argument": s["purpose"],
                     "required_claim_ids": ids, "supporting_evidence_ids": [l["evidence_id"] for l in links if l["relation"] == "supports"],
                     "contradictory_evidence_ids": [], "qualifying_evidence_ids": [], "boundary_conditions": "Inspected historical paper descriptions only",
                     "methodological_issues": "Software descriptions do not estimate comparative effects; a cited original is not inspected",
                     "relevant_theories": "No tested theory inferred", "planned_citations": sorted({evs[l["evidence_id"]]["paper_id"] for l in links}),
                     "unresolved_questions": ["No independent human semantic evaluation; no full-review approval"],
                     "suggested_argument_progression": s["purpose"], "cannot_claim": "Causal effects, universal performance, field consensus or a genuine research gap",
                     "generator": "Codex Round2I writer", "example_data": False}
            cli("writing-submit", brief, ("--kind", "brief"))
            spans = []
            for c in s["claims"]:
                claim = p.sp.latest()[c["id"]]
                eids = claim["evidence_ids"]
                keys = sorted({evs[e]["paper_id"] for e in eids})
                for key in ("text", "challenge"):
                    spans.append({"text": c[key], "classification": "substantive", "claim_ids": [c["id"]], "evidence_ids": eids, "citation_keys": keys,
                                  "evaluation_role": "adversarial_not_a_finding" if key == "challenge" else "source_bounded_candidate"})
            cli("writing-submit", {"section_id": s["section_id"], "writer": "Codex Round2I writer", "writer_context_id": "round2i-primary-writer",
                                    "example_data": True, "spans": spans}, ("--kind", "draft"))
        cli("writing-bibliography")
        cli("writing-validate")
        context = cli("writing-audit-context", extra=("--auditor", "Codex fresh-context auditor", "--context-id", "round2i-source-audit-1"))
        write_json_atomic(args.output / "audit-request.json", context)
        cli("writing-completion", extra=("--phase", "18"), expected=2)
    else:
        # Explicit test fixtures; never callable as part of the installed research workflow.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from writing_fixtures import build_official
        from test_writing import outline, brief, draft, audit_config
        from research_review_agent.writing.pipeline import WritingPipeline
        with tempfile.TemporaryDirectory() as name:
            source = build_official(type("FixtureTemp", (), {"name": name})())
            shutil.copytree(source, root)
        write_json_atomic(root / "FICTIONAL_ENGINEERING_PILOT.json", {"example_data": True, "notice": "All papers, evidence and human approvals are fictional software fixtures; no scientific validation."})
        def advance(phase, status):
            return cli("advance", extra=("--phase", str(phase), "--status", status, "--allow-example-data"))
        for kind, phase, generator in (("outline", 13, outline), ("brief", 14, brief), ("draft", 15, draft)):
            advance(phase, "in_progress")
            pipe = WritingPipeline(root)
            config = generator(pipe)
            if kind == "outline":
                config["section_structure"][0]["gap_ids"] = list(pipe.sp.latest("gap"))
                config["gap_connection"] = "End with the reviewed fictional corpus's design limitation, not a field-level novelty claim."
            if kind == "brief":
                config["central_argument"] = "FICTIONAL favorable, adverse and no-change accounts differ; no causal or universal benefit follows."
            if kind == "draft":
                keys = config["spans"][0]["citation_keys"]
                config["spans"][0]["text"] = ("In this explicitly fictional corpus, one account describes improved coordination under local support, while another describes reduced coordination and a no-change observation. "
                    "These qualitative accounts do not establish a universal benefit or causal effect. Within this fictional retrieved corpus, the design cannot distinguish causal explanations; this bounded limitation does not establish field-wide novelty "
                    + " ".join("[@" + k + "]" for k in keys) + ".")
            value = cli("writing-submit", config, ("--kind", kind))["record"]
            if kind != "draft":
                cli("writing-review", extra=("--id", value["record_id"], "--action", "approve", "--by", "FICTIONAL human fixture", "--rationale", "TEST ONLY, NOT ACTUAL HUMAN REVIEW", "--human-attestation"))
            advance(phase, "completed")
        advance(16, "in_progress")
        cli("writing-bibliography")
        advance(16, "completed")
        advance(17, "in_progress")
        context = cli("writing-audit-context", extra=("--auditor", "FICTIONAL model auditor", "--context-id", "FICTIONAL independent context"))
        cli("writing-audit-submit", audit_config(context, "cherry_picking"), ("--id", context["audit_id"]))
        cli("writing-completion", extra=("--phase", "18"), expected=2)
        cli("writing-audit-submit", audit_config(context), ("--id", context["audit_id"]))
        advance(17, "completed")
        advance(18, "in_progress")
        cli("writing-qc", extra=("--action", "approve", "--by", "FICTIONAL human fixture", "--rationale", "TEST ONLY, NOT ACTUAL HUMAN REVIEW", "--human-attestation"))
        advance(18, "completed")
        cli("writing-completion", extra=("--phase", "18"))
    write_json_atomic(args.output / "result.json", {"mode": args.mode, "project": str(root), "cli_calls": len(calls), "real_human_validation": False})
    print(json.dumps({"project": str(root), "cli_calls": len(calls)}))


if __name__ == "__main__":
    main()
