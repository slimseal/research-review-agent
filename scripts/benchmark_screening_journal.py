"""Offline benchmark. Checks are read-only; proposals require a fictional lab.

Select the implementation with PYTHONPATH (e.g. a preserved before-kit snapshot).
Run each implementation in a fresh process for comparable ru_maxrss readings.
No mocked approvals, network requests, or real-project proposal writes.
"""
import argparse
import json
import resource
import sys
import time
from pathlib import Path

import research_review_agent
from research_review_agent.screening.pipeline import ScreeningPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--operation", choices=["check", "proposal"], default="check")
    args = parser.parse_args()
    p = ScreeningPipeline(args.project)
    times = []
    if args.operation == "check":
        for _ in range(2):
            start = time.perf_counter()
            p.check_journal()
            times.append(time.perf_counter() - start)
        result = {"state_seq": p.state["seq"]}
    else:
        if p.context().get("mode") != "isolated_screening":
            raise ValueError("BENCHMARK_PROPOSALS_REQUIRE_FICTIONAL_ISOLATED_LAB")
        pid = p.current()["candidate_ids"][0]
        if p.latest(pid):
            raise ValueError("NEW_FICTIONAL_LAB_REQUIRED")
        start = time.perf_counter()
        packet = p.stage_context(pid, "title")
        decision = p.propose({
            "packet_id": packet["packet_id"], "decision": "uncertain", "review_role": None,
            "reason_codes": ["insufficient_information"],
            "explanation": "FICTIONAL PERFORMANCE TEST ONLY, not a research result.",
            "reviewer_id": "fictional-benchmark-model",
            "criteria_ids": list(p.rules_for(p.current(), pid, "title")),
            "source_facts": [{"location": "title", "quote": packet["basic_metadata"]["title"]}],
            "uncertainty_flags": ["fictional_test_only"],
        })
        times.append(time.perf_counter() - start)
        result = {"decision": {k: v for k, v in decision.items() if k not in {
            "decision_id", "review_timestamp", "project_id", "packet_id", "proposal_key",
        }}, "valid": p.validate()["valid"], "history_records": len(p.data["decisions"])}
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = int(rss if sys.platform == "darwin" else rss * 1024)
    print(json.dumps({
        "implementation": research_review_agent.__file__, "python": sys.version,
        "operation": args.operation, "seconds": times,
        "peak_rss_bytes_entire_worker": peak_bytes,
        "rss_measurement": "OS ru_maxrss; whole fresh worker, not tracemalloc",
        "journal_bytes": (args.project / ".review/events.jsonl").stat().st_size,
        "result": result,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
