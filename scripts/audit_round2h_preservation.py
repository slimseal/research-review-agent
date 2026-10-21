"""Read-only checks of original pilots and pre-change archive; writes only a NEW audit report."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

from research_review_agent.documents.parser import checksum
from research_review_agent.screening.pipeline import ScreeningPipeline
from research_review_agent.reading.pipeline import ReadingPipeline
from research_review_agent.state import load_state, write_json_atomic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--round2f", type=Path, required=True)
    ap.add_argument("--round2g", type=Path, required=True)
    ap.add_argument("--round2h", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise ValueError("New report file required")
    repo = Path(__file__).resolve().parents[1]
    protected = ["research_review_agent/constants.py", "research_review_agent/project.py",
                 "research_review_agent/resources/schema_catalog.json", "research_review_agent/scholarly/registry.py",
                 "research_review_agent/documents/contracts.py", "research_review_agent/documents/parser.py",
                 "research_review_agent/citations/pipeline.py", "research_review_agent/screening/pipeline.py",
                 "research_review_agent/reading/pipeline.py", "research_review_agent/reading/contracts.py"]
    with tarfile.open(args.snapshot) as archive:
        checks = {name: hashlib.sha256(archive.extractfile("research-review-agent/" + name).read()).hexdigest() == checksum(repo / name) for name in protected}
        old = json.load(archive.extractfile("research-review-agent/workflow/phases.json"))
    new = json.loads((repo / "workflow/phases.json").read_text())
    unchanged = all({k: p[k] for k in ("phase_id", "prerequisites", "applicable_quality_gates", "next_phase")} ==
                    {k: q[k] for k in ("phase_id", "prerequisites", "applicable_quality_gates", "next_phase")}
                    for p, q in zip(old["phases"], new["phases"])) and len(new["phases"]) == 19
    frozen = json.loads((args.round2h / "SYNTHESIS_LAB.json").read_text())["source_checksums"]
    actual = {str(p.relative_to(args.round2g)): checksum(p) for p in args.round2g.rglob("*") if p.is_file()}
    previous = json.loads((args.round2g / "PILOT_VALIDATION.json").read_text())
    sp = ScreeningPipeline(args.round2f)
    gate1, coverage = sp.gate(), sp.coverage()
    rp = ReadingPipeline(args.round2g)
    gate2 = rp.completion()
    library = json.loads((args.round2g / "READING_LAB.json").read_text())["source_checksums"]
    result = {"protected_code_unchanged": checks, "phase_order_dependencies_and_gate_positions_unchanged": unchanged,
              "round2g_all_files_match_pre_synthesis_copy": frozen == actual,
              "round2f_library_hashes_match_round2g_baseline": all(checksum(args.round2f / p) == sha for p, sha in library.items()),
              "round2f_gate1_matches_round2g_record": gate1 == previous["original_round2f_gate1"],
              "round2f_coverage_matches_round2g_record": coverage == previous["original_round2f_coverage"],
              "round2f_gate1_allowed": gate1["allowed"], "round2g_gate2_allowed": gate2["allowed"],
              "round2g_evidence_count": len(rp.latest("evidence")),
              "round2g_uncertain_count": sum(e["extraction_status"] == "uncertain" for e in rp.latest("evidence").values()),
              "original_completed_phases": {name: [k for k, v in load_state(path)["phases"].items() if v["status"] == "completed"]
                  for name, path in (("round2f", args.round2f), ("round2g", args.round2g))},
              "no_project_skill_files": not list(repo.rglob("SKILL.md")),
              "hardcoded_personal_paths_in_new_core": [str(p.relative_to(repo)) for p in (repo / "research_review_agent/synthesis").glob("*.py") if "/Users/" in p.read_text() or ".codex/skills" in p.read_text()],
              "note": "2F verification compares stored baseline gate/coverage and library hashes, not a nonexistent full-directory pre-2H snapshot."}
    write_json_atomic(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
