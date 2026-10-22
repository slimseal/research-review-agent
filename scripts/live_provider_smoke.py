#!/usr/bin/env python3
"""Opt-in real, anonymous integration smoke test; no formal workflow approvals.

Creates a NEW isolated directory, at most 6 HTTP sends across 5 searches,
1 record/page/provider, no retries/redirects/second pages or PDF retrieval.
Never run against an existing project. Does not run during offline tests.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_review_agent.scholarly.access import SEARCH_PROVIDERS, failure_status
from research_review_agent.scholarly.contracts import SearchRequest, ProviderFailure
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline
from research_review_agent.scholarly.providers import make_adapters
from research_review_agent.scholarly.request_budget import RecordedTransport
from research_review_agent.scholarly.source_plan import coverage_report
from research_review_agent.state import write_json_atomic, utc_now
from research_review_agent.validation import validate_discovery_provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-network", action="store_true", required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() or any((p / ".review/state.json").exists() or (p / "00_protocol/PROTOCOL.json").exists() for p in root.parents):
        raise ValueError("NEW_ISOLATED_DIRECTORY_REQUIRED")
    root.mkdir(parents=True)
    write_json_atomic(root / "INTEGRATION_TEST.json", {"mode": "real_network_engineering_test",
        "created_at": utc_now(), "no_formal_approvals": True, "max_http_requests": 6,
        "query": "biodiversity", "records_per_page": 1, "pages": 1, "anonymous_only": True})
    results = []
    # Preserve this Batch 1 script's original six-request authorization as adapters grow.
    for provider in ("crossref", "openalex", "pubmed", "europepmc", "semantic_scholar"):
        transport = RecordedTransport(root / "02_discovery/http" / provider,
                                      max_requests=2 if provider == "pubmed" else 1)
        pipeline = ScholarlyDiscoveryPipeline(root, adapters=make_adapters(transport, anonymous=True), enforce_workflow=False)
        request = SearchRequest("LIVE-ENGINEERING-NOT-A-REVIEW", "unapproved", "smoke-v1", provider,
                                "biodiversity", per_page=1, max_pages=1, mode="integration_test")
        run = pipeline.run_search(request)
        status = "available" if run.retrieval_status.startswith("complete") else failure_status(
            ProviderFailure(**run.errors[-1]), key_configured=False)
        item = {"provider": provider, "status": status, "credential_mode": "anonymous",
                "verified": status == "available", "checked_at": utc_now(),
                "operation": "search", "search_run_id": run.search_run_id,
                "retrieval_status": run.retrieval_status, "retrieved_count": run.retrieved_count,
                "parsed_count": run.parsed_count, "http_attempts": transport.used,
                "receipt": str(transport.path.relative_to(root)), "errors": run.errors,
                "coverage_limitations": run.coverage_limitations}
        results.append(item)
        write_json_atomic(root / "LIVE_RESULTS.json", {"results": results, "complete": False})
        print(json.dumps(item), flush=True)
    issues = validate_discovery_provenance(root, require_runs=True)
    report = {"results": results, "complete": True, "total_http_attempts": sum(r["http_attempts"] for r in results),
              "provenance_issues": [i.to_dict() for i in issues], "formal_workflow_completed": False}
    write_json_atomic(root / "LIVE_RESULTS.json", report)
    write_json_atomic(root / "LITERATURE_COVERAGE_REPORT.json", coverage_report(root))
    print(json.dumps({"total_http_attempts": report["total_http_attempts"], "provenance_issues": report["provenance_issues"]}), flush=True)


if __name__ == "__main__":
    main()
