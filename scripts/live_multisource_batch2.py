#!/usr/bin/env python3
"""Opt-in, anonymous, NEW isolated integration corpora. Eight possible HTTP sends.

No retries, redirects, extra pages, PDFs or research approvals. New providers each
receive one request (below the Batch 2 maximum of two); <=10 records per page.
The arXiv computing RQ is separate from the school/health research corpus.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_review_agent.scholarly.access import failure_status
from research_review_agent.scholarly.contracts import SearchRequest, ProviderFailure
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline
from research_review_agent.scholarly.providers import make_adapters
from research_review_agent.scholarly.request_budget import RecordedTransport
from research_review_agent.scholarly.source_plan import coverage_report
from research_review_agent.state import write_json_atomic, utc_now
from research_review_agent.validation import validate_discovery_provenance

RQ = "How is physical activity associated with academic performance in school-aged children?"
QUERIES = [
    ("main", "crossref", "physical activity academic performance school children", 1),
    ("main", "pubmed", '("physical activity"[Title/Abstract]) AND ("academic performance"[Title/Abstract]) AND (children[Title/Abstract] OR school[Title/Abstract])', 2),
    ("main", "europepmc", 'TITLE_ABS:"physical activity" AND TITLE_ABS:"academic performance" AND (TITLE_ABS:children OR TITLE_ABS:school)', 1),
    ("main", "eric", '"physical activity" AND ("academic performance" OR "academic achievement")', 1),
    ("main", "openaire", '"physical activity" AND "academic performance"', 1),
    ("main", "semantic_scholar", "physical activity academic performance school children", 1),
    ("arxiv_separate", "arxiv", 'ti:"knowledge tracing"', 1),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-network", action="store_true", required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() or any((p / ".review/state.json").exists() or (p / "00_protocol/PROTOCOL.json").exists() for p in root.parents):
        raise ValueError("NEW_ISOLATED_DIRECTORY_REQUIRED; no automatic restart/retry")
    root.mkdir(parents=True)
    write_json_atomic(root / "INTEGRATION_TEST.json", {
        "mode": "real_metadata_engineering_test_not_formal_research", "created_at": utc_now(),
        "questions": {"main": RQ, "arxiv_separate": "How do knowledge-tracing models represent student learning?"},
        "planned_queries": [dict(corpus=c, provider=p, exact_query=q, http_budget=b) for c, p, q, b in QUERIES],
        "max_total_http_requests": 8, "max_new_provider_requests": 1, "per_page": 10,
        "pages": 1, "attempts": 1, "anonymous_only": True, "formal_approvals": False,
        "unexecuted": {"openalex": "Existing quota limitation; no new request allocated.",
                       "core": "Official API reference inaccessible during contract verification; not implemented."}})
    results = []
    for corpus, provider, query, budget in QUERIES:
        project = root / corpus
        transport = RecordedTransport(project / "02_discovery/http" / provider, max_requests=budget)
        pipe = ScholarlyDiscoveryPipeline(project, adapters=make_adapters(transport, anonymous=True), enforce_workflow=False)
        request = SearchRequest("BATCH2-ENGINEERING-" + corpus, "unapproved", "batch2-native-queries-v1",
            provider, query, per_page=10, max_pages=1, max_requests=budget, max_attempts=1, mode="integration_test")
        run = pipe.run_search(request)
        status = "available" if run.retrieval_status.startswith("complete") else (
            failure_status(ProviderFailure(**run.errors[-1]), key_configured=False) if run.errors else "temporarily_unavailable")
        item = {"corpus": corpus, "provider": provider, "status": status, "operation": "search",
            "checked_at": utc_now(), "verified": status == "available", "credential_mode": "anonymous",
            "search_run_id": run.search_run_id, "retrieval_status": run.retrieval_status,
            "retrieved_count": run.retrieved_count, "parsed_count": run.parsed_count,
            "duplicate_count": run.duplicate_count, "ambiguous_count": run.ambiguous_identity_count,
            "http_attempts": transport.used, "receipt": str(transport.path.relative_to(root)),
            "errors": run.errors, "provenance_issues": [i.to_dict() for i in validate_discovery_provenance(project, require_runs=True)]}
        results.append(item)
        write_json_atomic(root / "LIVE_RESULTS.json", {"complete": False, "results": results})
        print(json.dumps(item), flush=True)
    for corpus in ("main", "arxiv_separate"):
        plan = {"sources": [{"provider": p} for c, p, _, _ in QUERIES if c == corpus]}
        if corpus == "main":
            plan["sources"] += [{"provider": "openalex", "skip_reason": "No new request allocated; previous quota restriction."},
                                {"provider": "core", "skip_reason": "Contract not verified; adapter not implemented."}]
        write_json_atomic(root / corpus / "LITERATURE_COVERAGE_REPORT.json", coverage_report(root / corpus, plan))
    write_json_atomic(root / "LIVE_RESULTS.json", {"complete": True, "results": results,
        "total_http_attempts": sum(r["http_attempts"] for r in results), "formal_workflow_completed": False})


if __name__ == "__main__":
    main()
