"""Replay explicitly authored pilot interpretations through the public CLI. No automatic reading.

Only an isolated reading lab is accepted. Quotes and judgments come from the input file;
the script does not invent, approve or score interpretations. Runtime inputs/outputs are logged.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from research_review_agent.state import write_json_atomic
from research_review_agent.reading.contracts import CONTENT_FIELDS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    args = ap.parse_args()
    root = args.project.resolve()
    marker = json.loads((root / "READING_LAB.json").read_text())
    assert marker["mode"] == "isolated_scientific_reading"
    config = json.loads(args.config.read_text())
    output = root / "pilot_execution"
    output.mkdir(exist_ok=False)
    logs = []

    def call(command, *options, expected=0):
        cmd = [sys.executable, "-m", "research_review_agent", command, "--project", str(root), *map(str, options)]
        r = subprocess.run(cmd, text=True, capture_output=True)
        logs.append({"command": cmd, "exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "expected_exit": expected})
        write_json_atomic(output / "commands.json", logs)
        if r.returncode != expected:
            raise RuntimeError(r.stdout + r.stderr)
        return json.loads(r.stdout)

    counts = []
    for paper in config["papers"]:
        pid = paper["paper_id"]
        did = marker["corpus"][pid]["document_id"]
        ctx = call("reading-context", "--paper-id", pid, "--document-id", did)
        anchors = {}
        for key, anchor in paper["anchors"].items():
            record = call("anchor-create", "--document-id", did, "--pdf-page", anchor["page"], "--quote", anchor["quote"])
            assert record["verification_status"] == "machine_located"
            anchors[key] = record["anchor_id"]
        content = {}
        for field in CONTENT_FIELDS:
            if field in paper["content"]:
                item = paper["content"][field]
                content[field] = {"status": "present", "text": item["text"], "epistemic_role": item["role"], "source_anchor_ids": [anchors[k] for k in item["anchors"]]}
            else:
                content[field] = paper["missing"][field]
        note = {"paper_id": pid, "document_id": did, "document_sha256": ctx["document"]["sha256"],
                "document_version": ctx["document"]["version_kind"], "generator": "Codex Round 2G provisional full-text interpretation",
                "reading_status": "completed", "unresolved_material": paper["unresolved_material"],
                "source_coverage": paper["source_coverage"], "content": content}
        path = output / (pid + "-note-input.json")
        write_json_atomic(path, note)
        note = call("reading-submit", "--config", path)
        call("reading-inspect", "--id", note["reading_note_id"])
        for i, authored in enumerate(paper["evidence"]):
            item = {**authored, "paper_id": pid, "document_id": did, "document_sha256": ctx["document"]["sha256"],
                    "reading_note_id": note["reading_note_id"], "research_question": marker["research_question"],
                    "source_basis": "full_text", "research_context": paper["research_context"],
                    "research_types": ["theoretical_conceptual"], "extension_json": {},
                    "extraction_run_id": config["run_id"], "generator": "Codex provisional interpretation",
                    "example_data": True, "source_anchor_ids": [anchors[k] for k in authored["anchors"]]}
            item.pop("anchors")
            for estimate in item.get("reported_values", []):
                estimate["anchor_id"] = anchors[estimate.pop("anchor_key")]
            path = output / f"{pid}-evidence-{i+1}-input.json"
            write_json_atomic(path, item)
            value = call("evidence-submit", "--config", path)
            call("evidence-inspect", "--id", value["evidence_id"])
        call("evidence-close", "--paper-id", pid, "--status", "incomplete", "--explanation", "Provisional bounded pilot; human semantic and completeness review unavailable, not an approved review corpus.")
        counts.append({"paper_id": pid, "evidence_items": len(paper["evidence"])})
    result = call("reading-validate")
    call("reading-queue")
    call("evidence-gate", expected=2)
    write_json_atomic(output / "result.json", {"counts": counts, "validation": result, "independent_reference_annotations": False,
                                               "human_approvals": 0, "accuracy_score": None, "source": str(args.config)})
    print(json.dumps({"counts": counts, "structural_validation": result["valid"], "human_approvals": 0}))


if __name__ == "__main__":
    main()
