"""Check source preservation and pilot boundaries without modifying upstream projects."""
import argparse
import json
from pathlib import Path
from research_review_agent.reading.pipeline import ReadingPipeline
from research_review_agent.screening.pipeline import ScreeningPipeline
from research_review_agent.documents.parser import checksum
from research_review_agent.state import load_state, write_json_atomic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()
    p = ReadingPipeline(args.project)
    marker = p.context()
    checks = {relative: (args.source / relative).is_file() and checksum(args.source / relative) == sha
              for relative, sha in marker["source_checksums"].items()}
    items = [p.inspect("evidence", key) for key in p.latest("evidence")]
    upstream = ScreeningPipeline(args.source)
    gate = upstream.gate()
    value = {"original_source_files_unchanged": all(checks.values()), "source_file_checks": checks,
             "original_round2f_gate1": gate, "original_round2f_coverage": upstream.coverage(),
             "pilot_official_completed_phases": [k for k, v in load_state(args.project)["phases"].items() if v["status"] == "completed"],
             "validation": p.validate(), "pilot_gate2": p.completion(),
             "evidence_source_resolution": [{"evidence_id": i["record"]["evidence_id"], "status": i["effective_status"],
                                             "anchor_statuses": [a["effective_status"] for a in i["anchors"]],
                                             "human_review": i["record"]["review_status"]} for i in items],
             "independent_semantic_validation": False, "human_reference_annotations": False,
             "new_downloads": 0, "new_scholarly_requests": 0}
    write_json_atomic(args.project / "PILOT_VALIDATION.json", value)
    print(json.dumps({"source_files_unchanged": all(checks.values()), "source_files": len(checks),
                      "pilot_structural_valid": value["validation"]["valid"], "original_gate1": gate["status"], "pilot_gate2": value["pilot_gate2"]["status"]}))


if __name__ == "__main__":
    main()
