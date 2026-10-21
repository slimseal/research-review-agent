#!/usr/bin/env python3
"""Run a small, isolated metadata-connectivity pilot; never creates an approved review."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research_review_agent.scholarly.contracts import SearchRequest
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline
from research_review_agent.state import utc_now, write_json_atomic


DEFAULT_QUERY = '"urban green space" AND adolescent AND "mental health"'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Round 2C live metadata pilot in an isolated directory.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--crossref-limit", type=int, default=5)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.expanduser().resolve()
    if args.limit < 1 or args.limit > 20:
        raise ValueError("--limit must be between 1 and 20")
    if args.crossref_limit < 0 or args.crossref_limit > args.limit:
        raise ValueError("--crossref-limit must be between 0 and --limit")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Pilot output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "PILOT_NOTICE.md").write_text(
        "# Live Discovery Connectivity Pilot\n\n"
        "This directory is not an approved review project. It contains live bibliographic metadata "
        "and API provenance only. It contains no screening decisions, findings, evidence extraction, "
        "full texts, claims or literature-review conclusions.\n",
        encoding="utf-8",
    )
    project_id = f"PILOT-{uuid.uuid4().hex[:10].upper()}"
    pipeline = ScholarlyDiscoveryPipeline(output, enforce_workflow=False)
    openalex_request = SearchRequest(
        project_id=project_id,
        protocol_version="not-applicable-connectivity-pilot",
        search_strategy_version="round2c-pilot-v1",
        provider="openalex",
        exact_query=args.query,
        per_page=args.limit,
        max_pages=1,
        mode="connectivity_pilot",
    )
    openalex_run = pipeline.run_search(openalex_request)
    crossref_search_request = SearchRequest(
        project_id=project_id,
        protocol_version="not-applicable-connectivity-pilot",
        search_strategy_version="round2c-pilot-v1-crossref",
        provider="crossref",
        exact_query=args.query,
        per_page=args.limit,
        max_pages=1,
        mode="connectivity_pilot",
    )
    crossref_search_run = pipeline.run_search(crossref_search_request)
    crossref_runs = []
    identities_path = output / "03_library/PAPER_IDENTITIES.json"
    if identities_path.exists() and crossref_search_run.retrieval_status in {"complete", "complete_with_limit"}:
        identities = json.loads(identities_path.read_text(encoding="utf-8"))
        dois = [
            record["doi"]
            for record in identities.get("records", {}).values()
            if record.get("doi")
        ][: args.crossref_limit]
        for doi in dois:
            request = SearchRequest(
                project_id=project_id,
                protocol_version="not-applicable-connectivity-pilot",
                search_strategy_version="round2c-crossref-verification-v1",
                provider="crossref",
                exact_query=f"doi:{doi}",
                mode="connectivity_pilot",
            )
            crossref_runs.append(pipeline.resolve_crossref_doi(request, doi))
    manifest = {
        "pilot_mode": "connectivity_and_metadata_processing_only",
        "is_approved_research_project": False,
        "project_id": project_id,
        "topic": "Urban green space exposure and adolescent mental health",
        "exact_query": args.query,
        "executed_at": utc_now(),
        "openalex_run": openalex_run.to_dict(),
        "crossref_search_run": crossref_search_run.to_dict(),
        "crossref_doi_resolution_runs": [run.to_dict() for run in crossref_runs],
        "full_text_downloads": 0,
        "screening_decisions": 0,
        "findings_inferred": 0,
    }
    write_json_atomic(output / "PILOT_RUN_MANIFEST.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    all_statuses = [openalex_run.retrieval_status, crossref_search_run.retrieval_status, *(run.retrieval_status for run in crossref_runs)]
    return 0 if all(status in {"complete", "complete_empty", "complete_with_limit"} for status in all_statuses) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileExistsError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
