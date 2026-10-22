#!/usr/bin/env python3
"""Rebuild a NEW engineering corpus using existing checksummed raw responses.

No transport, approvals or source edits. Original runs/receipts are preserved;
separate replay runs describe re-normalization, not additional live retrieval.
Only accepts a source explicitly labeled by the Batch 2 engineering marker.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline
from research_review_agent.scholarly.source_plan import coverage_report
from research_review_agent.state import write_json_atomic, utc_now
from research_review_agent.validation import validate_discovery_provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    marker = json.loads((source / "INTEGRATION_TEST.json").read_text())
    if marker.get("mode") != "real_metadata_engineering_test_not_formal_research" or output.exists():
        raise ValueError("NEW_ENGINEERING_DESTINATION_REQUIRED")
    if source in output.parents or any((p / ".review/state.json").exists() for p in output.parents):
        raise ValueError("ISOLATED_DESTINATION_REQUIRED")
    live = json.loads((source / "LIVE_RESULTS.json").read_text())
    output.mkdir(parents=True)
    write_json_atomic(output / "INTEGRATION_TEST.json", {**marker, "rebuilt_at": utc_now(),
        "offline_rebuild": True, "original_directory_name": source.name, "additional_http_requests": 0,
        "reason": "PubMed primary ArticleIdList scope correction; original live artifacts retained unchanged."})
    reports = []
    for corpus in ("main", "arxiv_separate"):
        src, dest = source / corpus / "02_discovery", output / corpus / "02_discovery"
        dest.mkdir(parents=True)
        for name in ("raw", "http", "search_runs"):
            shutil.copytree(src / name, dest / name)
        for name in ("SEARCH_RUNS.jsonl", "PROVIDER_RESPONSES.jsonl"):
            shutil.copy2(src / name, dest / name)
        pipe = ScholarlyDiscoveryPipeline(output / corpus, adapters={}, enforce_workflow=False)
        for original in [r for r in live["results"] if r["corpus"] == corpus and r["retrieved_count"]]:
            replay = pipe.replay(original["search_run_id"])
            reports.append({"corpus": corpus, "original_search_run_id": original["search_run_id"], **replay.to_dict()})
        plan = {"sources": [{"provider": r["provider"]} for r in live["results"] if r["corpus"] == corpus]}
        if corpus == "main":
            plan["sources"] += [{"provider": "openalex", "skip_reason": "No new request allocated; previous quota limitation."},
                                {"provider": "core", "skip_reason": "Adapter contract not verified."}]
        write_json_atomic(output / corpus / "LITERATURE_COVERAGE_REPORT.json", coverage_report(output / corpus, plan))
        issues = [i.to_dict() for i in validate_discovery_provenance(output / corpus, require_runs=True)]
        write_json_atomic(output / corpus / "PROVENANCE_VALIDATION.json", {"issues": issues})
        print(json.dumps({"corpus": corpus, "unique": len(pipe.registry.data["records"]), "issues": issues}))
    shutil.copy2(source / "LIVE_RESULTS.json", output / "ORIGINAL_LIVE_RESULTS.json")
    write_json_atomic(output / "REBUILD_REPORT.json", {"additional_http_requests": 0, "replays": reports})


if __name__ == "__main__":
    main()
