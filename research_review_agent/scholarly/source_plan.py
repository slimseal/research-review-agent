"""Planning/reporting only. No implicit network, scientific screening or approval."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..state import utc_now
from .access import access_configuration, CATALOG, SEARCH_PROVIDERS
from .manual_scholar import manual_coverage


def source_plan(question, domain="", include=(), exclude=(), access_report=None):
    if not question.strip():
        raise ValueError("RESEARCH_QUESTION_REQUIRED")
    if set(include) & set(exclude):
        raise ValueError("SOURCE_SELECTION_CONFLICT")
    # This is a transparent starting heuristic, not an academic coverage judgment.
    biomedical = any(word in (domain + " " + question).casefold() for word in
                     ("health", "medical", "biolog", "clinical", "depress", "cancer", "医学", "健康", "抑郁", "生物"))
    recommended = list(dict.fromkeys(include)) if include else (
        ["pubmed", "europepmc", "crossref", "openalex"] if biomedical else
        ["crossref", "openalex", "semantic_scholar"])
    topic = (domain + " " + question).casefold()
    if not include:
        if any(w in topic for w in ("education", "school", "teaching", "教育", "教学")):
            recommended.insert(0, "eric")
        if any(w in topic for w in ("physics", "computer science", "machine learning", "物理", "计算机")):
            recommended.insert(0, "arxiv")
        recommended.append("openaire")
    recommended = [p for p in recommended if p not in exclude and p != "google_scholar"]
    config = access_configuration()
    observed = {}
    if access_report:
        for evidence in access_report.get("results", [access_report]):
            if evidence.get("operation") != "search":
                continue  # Quota endpoint results cannot classify search access.
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(evidence["checked_at"])).total_seconds()
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= age < 86400:
                observed[evidence.get("provider")] = evidence
    rationale = {
        "eric": "Education-specific indexing; reports and non-peer-reviewed items require separate screening.",
        "arxiv": "Preprint discovery for relevant physics/computing/mathematics topics; not peer-review certification.",
        "openaire": "Cross-repository Graph v3 metadata with heterogeneous research product types and versions.",
        "crossref": "DOI registration metadata complements topic indexing; abstracts may be absent.",
        "openalex": "Multidisciplinary metadata/citation index; anonymous first cursor page only in this adapter.",
        "pubmed": "Biomedical topic indexing and metadata/abstracts; not comprehensive outside biomedicine.",
        "europepmc": "Life-science coverage including preprints; substantial PubMed overlap, not an independent evidence vote.",
        "semantic_scholar": "Multidisciplinary relevance-ranked metadata; shared anonymous limits and a 1000-result relevance window.",
    }
    sources = []
    for name in recommended:
        item = config.get(name, {"status": "not_implemented", "adapter_packaged": False})
        evidence = observed.get(name)
        category = "Not implemented or not verified"
        if evidence and item.get("adapter_packaged"):
            item = {**item, "status": evidence.get("status", "not_verified"),
                    "verified": bool(evidence.get("verified")), "observation": evidence}
            if item["status"] == "available" and item["verified"]:
                category = "Recommended and available"
            elif item["status"] in {"key_missing", "key_invalid"}:
                category = "Available after free setup"
        if item.get("access_requirement") == "requires_institutional_access":
            category = "Requires institutional access"
        sources.append({"provider": name, "proposed": True, "selected": False,
                        "execution_status": "not_executed", "access": item,
                        "category": category,
                        "reason": rationale.get(name, "User-requested source; verify adapter and lawful access before execution."),
                        "availability_note": "Endpoint observation is time/context bounded, not a guarantee for the planned queries." if evidence else
                            ("No key required for an initial search; live availability unverified." if item.get("anonymous_search") else "Not available without further access/implementation review.")})
    return {"plan_version": 1, "created_at": utc_now(), "research_question": question, "domain": domain,
            "status": "draft_pending_source_and_budget_confirmation", "heuristic_requires_agent_review": True,
            "sources": sources, "explicit_exclusions": list(exclude),
            "categories": ["Recommended and available", "Available after free setup", "Requires institutional access",
                           "Manual supplementary search", "Not implemented or not verified"],
            "free_setup_options": [{"provider": p, "optional": True, "setup_url": CATALOG[p]["setup_url"],
                                     "key_configured": config[p]["key_configured"], "verified": False}
                                    for p in ("openalex", "pubmed", "semantic_scholar") if p in recommended],
            "institutional_gaps": [{"provider": p, "category": "Requires institutional access",
                                    "access_requirement": "requires_institutional_access", "status": "not_implemented",
                                    "execution_status": "not_executed"} for p in ("scopus", "web_of_science", "psycinfo") if p not in exclude],
            "manual_supplements": [{"provider": "google_scholar", "entry_url": "https://scholar.google.com",
                                    "category": "Manual supplementary search", "status": "not_performed",
                                    "proposed": "google_scholar" not in exclude and (not include or "google_scholar" in include),
                                    "suitability": "requires_agent_assessment",
                                    "reason": "Respect explicit source choices; Agent assesses supplementary value and authors 3–5 queries. No API, scraping or saturation claim."}],
            "budget": {"total_http_requests": None, "per_source": {}, "retries": 0,
                       "note": "Confirm exact queries, pages, records, probes and PubMed's two requests per nonempty page together."},
            "rules": ["Respect explicit choices/exclusions; do not auto-substitute.",
                      "Probe selected endpoints within the confirmed budget; update categories from actual evidence.",
                      "Unavailable optional sources do not block separately authorized sources.",
                      "One source-plan confirmation does not replace Protocol, screening or other human scientific Gates."]}


def coverage_report(project: Path, plan=None):
    run_files = sorted((project / "02_discovery/search_runs").glob("*.json"))
    all_runs = [json.loads(p.read_text()) for p in run_files]
    replays = [r for r in all_runs if r.get("replay_of")]
    runs = [r for r in all_runs if not r.get("replay_of")]
    live_ids = {r["search_run_id"] for r in runs if r.get("search_run_id")}
    replay_sources = {r["search_run_id"]: r["replay_of"] for r in replays}
    latest_processing = {r["search_run_id"]: r for r in runs if r.get("search_run_id")}
    for replay in sorted(replays, key=lambda r: r.get("execution_timestamp", "")):
        latest_processing[replay["replay_of"]] = replay
    path = project / "03_library/PAPER_IDENTITIES.json"
    records = json.loads(path.read_text()).get("records", {}) if path.exists() else {}
    by_provider = {}
    for provider in sorted({r["provider"] for r in runs}):
        selected_runs = [r for r in runs if r["provider"] == provider]
        ids = [pid for pid, r in records.items() if provider in r.get("provider_ids", {})]
        unique = [pid for pid in ids if len(records[pid].get("provider_ids", {})) == 1]
        by_provider[provider] = {
            "runs": [{**{k: r.get(k) for k in ("search_run_id", "exact_query", "filters", "retrieval_status",
                      "retrieved_count", "duplicate_count", "ambiguous_identity_count", "rejected_count", "pages_completed",
                      "http_attempts", "http_receipt_path", "errors", "coverage_limitations")},
                      "http_attempts": r.get("http_attempts") if r.get("http_receipt_path") else None,
                      "http_accounting_basis": r.get("http_receipt_path") or "unbound_or_legacy; inspect original request receipts",
                      "request_configuration": r.get("request_configuration", {}),
                      "latest_normalization": {k: latest_processing.get(r.get("search_run_id"), r).get(k)
                          for k in ("search_run_id", "replay_of", "retrieval_status", "parsed_count", "duplicate_count",
                                    "ambiguous_identity_count", "rejected_count", "warnings")},
                      "stop_reason": ("provider_error; no automatic substitution" if r.get("errors") else
                                      "authorized page/record boundary" if r.get("pagination_cursor") else "provider page exhausted"),
                      "successful_result_count": r.get("retrieved_count") if r["retrieval_status"].startswith("complete") else None}
                     for r in selected_runs],
            "canonical_paper_ids": ids, "provider_only_candidate_ids": unique,
            "raw_result_count": sum(r.get("retrieved_count", 0) for r in selected_runs),
            "unique_candidate_count": len(ids), "provider_only_candidate_count": len(unique),
            "relevance": "not_evaluated",
        }
        origins = [o for pid in ids for o in records[pid].get("provenance", []) if o.get("provider") == provider
                   and (not live_ids or replay_sources.get(o.get("search_run_id"), o.get("search_run_id")) in live_ids)]
        # Multiple normalizations of the same raw row are not independent observations.
        origins = list({(o.get("raw_response_path"), o.get("raw_record_index"), o.get("provider_record_id")): o
                        for o in origins}.values())
        by_provider[provider]["metadata_completeness"] = {
            "basis": "registered source observations; excludes rejected/unresolved rows",
            "source_observations": len(origins),
            "abstract_missing": sum(o.get("abstract_available") is False for o in origins),
            "abstract_availability_unknown_legacy": sum("abstract_available" not in o for o in origins),
            "canonical_doi_missing": sum(not records[pid].get("doi") for pid in ids),
            "pmid_missing": sum(not any(k.casefold() in {"pmid", "pubmed"} for k in o.get("source_ids", {})) for o in origins),
            "pmcid_missing": sum(not any(k.casefold() in {"pmcid", "pmc", "pubmedcentral"} for k in o.get("source_ids", {})) for o in origins),
            "note": "PMID/PMCID are not applicable to all disciplines; missing is not ineligible."}
    overlaps = []
    names = sorted(by_provider)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            shared = sorted(set(by_provider[left]["canonical_paper_ids"]) & set(by_provider[right]["canonical_paper_ids"]))
            overlaps.append({"providers": [left, right], "count": len(shared), "paper_ids": shared})
    skipped = []
    if plan:
        for item in plan.get("sources", []):
            if item["provider"] not in by_provider:
                skipped.append({"provider": item["provider"], "status": "not_executed", "result_count": None,
                                "reason": item.get("skip_reason") or "No recorded SearchRun; no inferred zero result."})
    return {"created_at": utc_now(), "canonical_paper_count": len(records), "providers": by_provider,
            "pairwise_overlaps": overlaps, "relevance": "not_evaluated",
            "offline_replay_runs_excluded_from_search_counts": [r["search_run_id"] for r in replays],
            "latest_normalization_totals": {k: sum(r.get(k, 0) for r in latest_processing.values())
                for k in ("parsed_count", "duplicate_count", "ambiguous_identity_count", "rejected_count")},
            "raw_result_count": sum(r.get("retrieved_count", 0) for r in runs),
            "http_requests_accounted": sum(r.get("http_attempts", 0) for r in runs if r.get("http_receipt_path")),
            "http_accounting_complete": all(r.get("http_receipt_path") for r in runs),
            "unexecuted_sources": skipped, "institutional_gaps": (plan or {}).get("institutional_gaps", []),
            "manual_supplements": [manual_coverage(project)],
            "manual_source_proposals": (plan or {}).get("manual_supplements", []),
            "coverage_judgment": "pending_human_review",
            "limitations": ["Counts and overlapping database hits cannot establish sufficient coverage.",
                            "Assess topic/design/language/date coverage, missing abstracts, missed known studies and specialist sources.",
                            "Unique Paper IDs are candidates, not included studies or independent cohorts."]}
