from __future__ import annotations

import csv
import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path

from ..constants import CSV_FIELDS
from ..state import canonical_json, load_state, new_state, persist_state, recover_state, utc_now, write_json_atomic
from ..scholarly.contracts import SearchRequest
from ..scholarly.normalization import normalize_doi, normalize_crossref_records, normalize_openalex_records
from ..scholarly.pipeline import ScholarlyDiscoveryPipeline
from ..scholarly.registry import PaperRegistry
from ..scholarly.store import DiscoveryStore
from ..scholarly.transport import ProviderRequestError
from .contracts import VERSION, SUPPORTED, COVERAGE, SeedSet, CitationExpansionRun, ExpansionCandidate, CitationEdge, record
from .providers import CitationProviders, parse_page, fail
from . import budget


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def initialize_lab(root):
    root = root.resolve()
    if root.exists():
        raise ValueError("LAB_REQUIRES_NEW_DIRECTORY")
    if any((parent / "00_protocol/PROTOCOL.json").exists() or (parent / "CITATION_LAB.json").exists() for parent in root.parents):
        raise ValueError("LAB_CANNOT_BE_NESTED_IN_REVIEW_OR_LAB")
    root.mkdir(parents=True)
    marker = {"project_id": "citation-lab-" + uuid.uuid4().hex, "purpose": "isolated infrastructure pilot; no workflow approval", "created_at": utc_now()}
    write_json_atomic(root / "CITATION_LAB.json", marker)
    persist_state(root, new_state(marker["project_id"], marker["purpose"], "infrastructure-lab"), "citation_lab_initialized")
    DiscoveryStore(root).ensure()
    return marker


class CitationPipeline:
    def __init__(self, root, providers=None, *, budget_opener=None):
        self.root = Path(root).resolve()
        self.store = DiscoveryStore(self.root)
        self.registry = PaperRegistry(self.root, self.store)
        self.providers = providers or CitationProviders()
        self.state = load_state(self.root)
        self.data = self.state.setdefault("citation_data", {"contract_version": VERSION, "seeds": [], "runs": {}, "candidates": {}, "edges": {}, "reviews": []})
        self._budget_opener = budget_opener
        if budget_opener is not None and self.context().get("mode") != "lab":
            raise ValueError("TEST_OPENER_LAB_ONLY")
        if self.data["seeds"] and budget.strict(self.seed()):
            self._enable_budget()
        elif (self.root / ".review/citation_http_budget").exists():
            raise ValueError("BUDGET_LEDGER_REQUIRES_STRICT_SEED_RECOVERY")

    def _enable_budget(self):
        self.budget_transport = budget.BudgetTransport(self, self._budget_opener)
        self.providers.transport = self.budget_transport
        self.providers.crossref.transport = self.budget_transport

    def strict_budget(self):
        return bool(self.data["seeds"] and budget.strict(self.seed()))

    def context(self):
        marker = self.root / "CITATION_LAB.json"
        if marker.exists():
            if (self.root / "00_protocol/PROTOCOL.json").exists() or any((p / "00_protocol/PROTOCOL.json").exists() for p in self.root.parents):
                raise ValueError("LAB_CANNOT_BYPASS_OFFICIAL_WORKFLOW")
            lab = read_json(marker)
            return {"project_id": lab["project_id"], "protocol_version": "lab-only", "mode": "lab"}
        return read_json(self.root / "00_protocol/PROTOCOL.json")

    def authorize(self, validation=False):
        context = self.context()
        if context.get("mode") == "lab":
            return context
        from ..validation import validate_phase, validate_protocol
        issues = validate_protocol(self.root, require_approved=True, require_substantive=True) + validate_phase(self.root, 3)
        state = load_state(self.root)
        allowed = {"in_progress", "completed"} if validation else {"in_progress"}
        if any(i.severity == "error" for i in issues) or state["phases"]["3"]["status"] != "completed" or state["phases"]["4"]["status"] not in allowed:
            raise ValueError("PHASE4_AUTHORIZATION_REQUIRED: approved substantive Protocol, valid completed Phase 3, active Phase 4")
        return context

    def save(self, event):
        # Use the existing controller journal, not a second phase state machine.
        state = load_state(self.root)
        if self.strict_budget() and state["seq"] != self.state["seq"]:
            raise ValueError("CITATION_STATE_VERSION_CONFLICT")
        state["citation_data"] = self.data
        self.state = persist_state(self.root, state, event)

    def eligible(self):
        return [{"paper_id": pid, "title": r["title"], "doi": r["doi"], "verification_status": r["verification_status"]}
                for pid, r in self.registry.data["records"].items()
                if r.get("title") and r.get("provenance") and r.get("verification_status") != "conflict"]

    def lab_doi(self, doi):
        context = self.context()
        if context.get("mode") != "lab":
            raise ValueError("LAB_ONLY: use official Phase 3/5 resolve-doi")
        request = SearchRequest(context["project_id"], "lab-only", "pilot-seed-verification", "crossref", "doi:" + doi, mode="lab")
        return ScholarlyDiscoveryPipeline(self.root, enforce_workflow=False).resolve_crossref_doi(request, doi).to_dict()

    @budget.locked
    def register_seeds(self, config, by):
        context = self.authorize()
        if self.strict_budget() and not config.get("budget_policy"):
            raise ValueError("STRICT_BUDGET_DOWNGRADE_FORBIDDEN")
        if config.get("budget_policy"):
            budget.validate_config(config, self.registry.data["records"])
            if self.data["runs"] or (self.root / ".review/citation_http_budget").exists():
                raise ValueError("STRICT_BUDGET_PLAN_FROZEN_AFTER_RUN_START")
            budget.check_config_context(self, config)
        ids = config["selected_paper_ids"]
        reasons = config["selection_reason"]
        if not ids or len(ids) != len(set(ids)) or not set(ids) <= {r["paper_id"] for r in self.eligible()}:
            raise ValueError("INVALID_SEEDS: select distinct verified canonical Paper Registry identities")
        if not by.strip() or any(not str(reasons.get(pid, "")).strip() for pid in ids):
            raise ValueError("SEED_REASON_AND_SELECTOR_REQUIRED")
        plan = config["provider_plan"]
        if not plan or len({(p["provider"], p["direction"]) for p in plan}) != len(plan):
            raise ValueError("INVALID_PROVIDER_PLAN")
        for path in plan:
            if path["direction"] not in SUPPORTED.get(path["provider"], set()):
                raise ValueError("PROVIDER_UNSUPPORTED")
        depth, requests, candidates = (config.get(k, d) for k, d in [("expansion_depth_limit", 1), ("max_requests", 30), ("max_candidates", 100)])
        if not all(isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= bound for n, bound in [(depth, 10), (requests, 1000), (candidates, 10000)]):
            raise ValueError("INVALID_EXPANSION_LIMITS")
        snapshot = {pid: {k: self.registry.data["records"][pid].get(k) for k in ("title", "doi")} for pid in ids}
        seed = record(SeedSet("SS-" + uuid.uuid4().hex, len(self.data["seeds"]) + 1, context["protocol_version"], digest(context), ids,
                              reasons, by, utc_now(), "pending_human_review", depth, plan, requests, candidates, snapshot))
        if config.get("budget_policy"):
            seed["budget_policy"] = config["budget_policy"]
            seed["protocol_file_sha256"] = budget.protocol_file_hash(self)
            seed["strict_identity_snapshot"] = budget.identity(self.registry.data["records"], ids)
            seed["decision_source"] = config.get("decision_source", {})
            seed["plan_sha256"] = budget.binding(seed)
        self.data["seeds"].append(seed)
        self.save("citation_seed_set_registered")
        if self.strict_budget():
            self._enable_budget()
        self.export()
        return seed

    def seed(self):
        if not self.data["seeds"]:
            raise ValueError("SEED_SET_REQUIRED")
        return self.data["seeds"][-1]

    @budget.locked
    def approve_seeds(self, by, note, pilot=False, expected_version=None, expected_plan_sha256=None):
        context = self.authorize()
        if not by.strip() or not note.strip():
            raise ValueError("NAMED_REVIEW_AND_NOTE_REQUIRED")
        if pilot != (context.get("mode") == "lab"):
            raise ValueError("PILOT_SELECTION_IS_NOT_HUMAN_WORKFLOW_APPROVAL")
        seed = self.seed()
        if self.strict_budget():
            if expected_version != seed["seed_set_version"] or expected_plan_sha256 != budget.binding(seed) or seed["plan_sha256"] != budget.binding(seed):
                raise ValueError("SEED_APPROVAL_VERSION_OR_HASH_CONFLICT")
            if seed["strict_identity_snapshot"] != budget.identity(self.registry.data["records"], seed["selected_paper_ids"]):
                raise ValueError("STALE_SEED_IDENTITY")
        if seed["protocol_sha256"] != digest(context):
            raise ValueError("STALE_SEED_SET")
        seed["approval_status"] = "pilot_selected" if pilot else "human_approved"
        seed["approval"] = {"by": by, "note": note, "at": utc_now()}
        self.save("citation_seed_selection_reviewed")
        self.export()
        return seed

    def assert_current(self, run=None, validation=False):
        context = self.authorize(validation)
        seed = self.seed()
        if self.strict_budget():
            budget.validate_config(seed, self.registry.data["records"])
            if seed["protocol_file_sha256"] != budget.protocol_file_hash(self):
                raise ValueError("PROTOCOL_FILE_HASH_CONFLICT")
            if seed["plan_sha256"] != budget.binding(seed) or seed["strict_identity_snapshot"] != budget.identity(self.registry.data["records"], seed["selected_paper_ids"]):
                raise ValueError("STRICT_PLAN_OR_IDENTITY_CONFLICT")
            if run and run.get("budget_plan_sha256") != seed["plan_sha256"]:
                raise ValueError("STRICT_RUN_PLAN_CONFLICT")
        expected = "pilot_selected" if context.get("mode") == "lab" else "human_approved"
        if seed["approval_status"] != expected:
            raise ValueError("SEED_APPROVAL_REQUIRED")
        snapshot = {pid: {k: self.registry.data["records"].get(pid, {}).get(k) for k in ("title", "doi")} for pid in seed["selected_paper_ids"]}
        if seed["protocol_sha256"] != digest(context) or snapshot != seed["identity_snapshot"]:
            raise ValueError("STALE_SEED_SET: register and review a new version")
        if run and run["seed_set_version"] != seed["seed_set_version"]:
            raise ValueError("STALE_EXPANSION_RUN")
        return context, seed

    def round_usage(self, number):
        runs = [r for r in self.data["runs"].values() if r["expansion_round"] == number]
        return sum(r["request_count"] for r in runs), sum(r["discovered_count"] for r in runs)

    @budget.locked
    def start(self, provider, direction, number=1):
        context, seed = self.assert_current()
        if {"provider": provider, "direction": direction} not in seed["provider_plan"]:
            raise ValueError("OPERATION_NOT_IN_APPROVED_PLAN")
        if not 1 <= number <= seed["expansion_depth_limit"]:
            raise ValueError("DEPTH_LIMIT")
        if number > 1 and not any(r["expansion_round"] == number - 1 and r["status"] != "in_progress" for r in self.data["runs"].values()):
            raise ValueError("PREVIOUS_ROUND_REQUIRED")
        if self.strict_budget():
            existing = next((r for r in self.data["runs"].values() if (r["provider"], r["direction"], r["expansion_round"]) == (provider, direction, number)), None)
            if existing:
                return self.resume(existing["expansion_run_id"])
        run = record(CitationExpansionRun("CE-" + uuid.uuid4().hex, context["project_id"], context["protocol_version"], seed["seed_set_version"], number,
                                         direction, provider, {"seed_paper_ids": seed["selected_paper_ids"], "max_requests_per_round": seed["max_requests"], "max_candidates_per_round": seed["max_candidates"]}, utc_now()))
        run.update({"seed_index": 0, "pages": [], "metadata_pages": {}, "request_count": 0, "initial_paper_ids": list(self.registry.data["records"]),
                    "seed_snapshots": json.loads(canonical_json({pid: self.registry.data["records"][pid] for pid in seed["selected_paper_ids"]})), "seen_cursors": [],
                    "stop_reason": None, "error_history": [], "protocol_sha256": seed["protocol_sha256"], "mode": context.get("mode", "workflow")})
        self.data["runs"][run["expansion_run_id"]] = run
        if self.strict_budget():
            run["budget_plan_sha256"] = seed["plan_sha256"]
        self.save("citation_expansion_started")
        return self.resume(run["expansion_run_id"])

    def _fetch(self, run, call, provider, purpose):
        if self.strict_budget():
            if purpose != "citation_relations" or run["pagination_cursor"] is not None:
                raise fail("HTTP_REQUEST_NOT_AUTHORIZED", "Strict round forbids identity queries and pagination.", provider)
            seed_id = run["query_parameters"]["seed_paper_ids"][run["seed_index"]]
            try:
                with self.budget_transport.scope(run, seed_id):
                    call()
            except ProviderRequestError:
                # Error responses are sources too. Preserve their raw indexes;
                # never present them as an empty successful relation page.
                entries = self.budget_transport.inspect()
                run["request_count"] = sum(e["reservation"]["run_id"] == run["expansion_run_id"] for e in entries)
                for e in entries:
                    if e["reservation"]["run_id"] == run["expansion_run_id"] and e.get("response"):
                        raw = e["response"]
                        if raw["raw_response_path"] not in run["raw_response_reference"]:
                            run["raw_response_reference"].append(raw["raw_response_path"])
                            run["raw_response_sha256"].append(raw["sha256"])
                raise
            receipts = self.budget_transport.inspect()
            entry = next(e for e in receipts if e["reservation"]["run_id"] == run["expansion_run_id"] and e["reservation"]["seed_paper_id"] == seed_id)
            page = {**entry["response"], "purpose": purpose, "provider": provider}
            run["request_count"] = sum(e["reservation"]["run_id"] == run["expansion_run_id"] for e in receipts)
            if page["raw_response_path"] not in run["raw_response_reference"]:
                run["raw_response_reference"].append(page["raw_response_path"])
                run["raw_response_sha256"].append(page["sha256"])
            return page
        seed = self.seed()
        if self.round_usage(run["expansion_round"])[0] >= seed["max_requests"]:
            raise fail("REQUEST_LIMIT", "Researcher request cap reached; not saturation.", provider)
        run["request_count"] += 1
        self.save("citation_request_reserved")
        body, metadata = call()
        path, sha = self.store.write_raw_response(provider, run["expansion_run_id"], run["request_count"], body)
        page = {**metadata, "raw_response_path": path, "sha256": sha, "purpose": purpose, "provider": provider}
        run["raw_response_reference"].append(path)
        run["raw_response_sha256"].append(sha)
        return page

    def _metadata(self, run, doi):
        if doi not in run["metadata_pages"]:
            page = self._fetch(run, lambda: self.providers.metadata(doi), "crossref", "identity_metadata")
            run["metadata_pages"][doi] = page
            self.save("citation_metadata_raw_saved")
        page = run["metadata_pages"][doi]
        body = self.store.verify_raw_response(page["raw_response_path"], page["sha256"])
        try:
            value = json.loads(body)["message"]
            if normalize_doi(value.get("DOI")) != doi:
                raise ValueError("DOI mismatch")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise fail("MALFORMED_RESPONSE", "Crossref identity metadata: " + str(exc), "crossref")
        candidates = normalize_crossref_records([value], search_run_id=run["expansion_run_id"], retrieved_at=page["retrieved_at"], raw_response_path=page["raw_response_path"]).candidates
        return candidates[0] if candidates else None

    def _resolve(self, run, row, pointer, page):
        doi = row.get("doi")
        if row.get("identity_note") == "ambiguous_multiple_dois":
            return None, "ambiguous_multiple_dois", None
        known = self.registry.data["doi_index"].get(doi) if doi else None
        if known:
            return known, "exact_registered_doi", self.registry.data["records"][known]
        # Never overwrite or duplicate legacy/manual identities without reconciliation.
        path = self.root / "03_library/PAPER_REGISTRY.csv"
        if doi and path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                if any(normalize_doi(r.get("doi")) == doi for r in csv.DictReader(handle)):
                    return None, "legacy_identity_requires_review", None
        candidate = None
        if run["provider"] == "openalex" and isinstance(row.get("metadata"), dict):
            items = normalize_openalex_records([row["metadata"]], search_run_id=run["expansion_run_id"], retrieved_at=page["retrieved_at"], raw_response_path=page["raw_response_path"]).candidates
            candidate = replace(items[0], raw_record_index=pointer["record_index"]) if items else None
        elif doi:
            if self.strict_budget():
                return None, "unresolved_local_only_no_metadata_query", None
            try:
                candidate = self._metadata(run, doi)
            except ProviderRequestError as exc:
                if exc.failure.code == "REQUEST_LIMIT":
                    run["warnings"].append("METADATA_REQUEST_LIMIT:" + doi)
                    return None, "metadata_request_limit", None
                if exc.failure.code == "IDENTIFIER_NOT_FOUND":
                    run["warnings"].append("METADATA_MISSING:" + doi)
                    return None, "metadata_missing", None
                raise
        if not candidate:
            return None, row.get("identity_note", "unresolved_reference"), None
        # Prevent provider-ID reuse from merging two distinct DOIs.
        existing = self.registry.data["provider_index"].get(candidate.provider + ":" + candidate.provider_record_id)
        if existing and doi and self.registry.data["records"][existing].get("doi") not in (None, doi):
            return None, "provider_identity_conflict", None
        result = self.registry.register(candidate)
        return result.paper_id, result.identity_match.method if result.paper_id else "ambiguous_identity", candidate.to_dict()

    def _candidate(self, run, seed_id, row, page, index):
        pointer = {"path": page["raw_response_path"], "sha256": page["sha256"], "record_index": index}
        cid = "EC-" + digest([run["expansion_run_id"], pointer])[:24]
        if cid in self.data["candidates"]:
            return
        if self.strict_budget():
            count = sum(c["source_seed"] == seed_id and c["citation_direction"] == run["direction"] for c in self.data["candidates"].values())
            if index >= 20 or count >= 20 or len(self.data["candidates"]) >= 120:
                raise fail("CANDIDATE_LIMIT", "Hard seed-direction observation cap; no replacement sampling.", run["provider"])
        pid, status, metadata = self._resolve(run, row, pointer, page) if row["relation_valid"] else (None, "seed_relation_mismatch", None)
        prior = {c["paper_id"] for c in self.data["candidates"].values() if c["expansion_run_id"] == run["expansion_run_id"] and c["paper_id"]}
        duplicate = bool(pid and (pid in run["initial_paper_ids"] or pid in prior))
        if metadata is None and isinstance(row["raw"], dict):
            # Literal deposited fields only; do not invent an author/title from prose.
            raw = row["raw"]
            metadata = {"deposited_reference_fields": {k: raw[k] for k in ("article-title", "journal-title", "author", "year", "unstructured") if k in raw}, "parsing_status": "literal_fields_only_identity_unresolved"}
        c = record(ExpansionCandidate(cid, run["expansion_run_id"], seed_id, run["direction"], run["expansion_round"],
                                     {"provider": run["provider"], "id": row["provider_record_id"], "doi": row.get("doi"), "external_ids": row.get("external_ids", [])},
                                     metadata or {}, status, "duplicate" if duplicate else "new" if pid else "unresolved", pid, row["raw"], pointer))
        c["literal_parse"] = row.get("literal_parse", {})
        self.data["candidates"][cid] = c
        if pid:
            source = {"candidate_id": cid, "expansion_run_id": run["expansion_run_id"], "provider": run["provider"], "seed_paper_id": seed_id, "raw_response_pointer": pointer}
            lineage = self.registry.data["records"][pid].setdefault("citation_provenance", [])
            if source not in lineage:
                lineage.append(source)
                self.registry.save()
        if row["relation_valid"]:
            other = pid or ("external:doi:" + row["doi"] if row.get("doi") else "external:reference:" + digest(row["raw"])[:24])
            citing, cited = (seed_id, other) if run["direction"] == "backward" else (other, seed_id)
            eid = "EDGE-" + digest([citing, cited])[:24]
            provenance = {"candidate_id": cid, "expansion_run_id": run["expansion_run_id"], "seed_paper_id": seed_id, "direction": run["direction"], "provider": run["provider"], "provider_record_id": row["provider_record_id"], "raw_response_pointer": pointer, "retrieved_at": page["retrieved_at"]}
            if eid not in self.data["edges"]:
                self.data["edges"][eid] = record(CitationEdge(eid, citing, cited, seed_id, run["direction"], run["expansion_round"], run["provider"], row["provider_record_id"], pointer,
                                                             page["retrieved_at"], "provider_reported", status, "provider reference list" if run["provider"] == "crossref" else "provider directed citation index"))
            self.data["edges"][eid]["provenance"].append(provenance)
        else:
            run["warnings"].append("SEED_RELATION_MISMATCH:" + cid)
        self.count(run)
        self.save("citation_candidate_registered")

    def count(self, run):
        rows = [c for c in self.data["candidates"].values() if c["expansion_run_id"] == run["expansion_run_id"]]
        run["discovered_count"] = len(rows)
        run["resolved_count"] = sum(bool(c["paper_id"]) for c in rows)
        run["unresolved_count"] = len(rows) - run["resolved_count"]
        run["duplicate_count"] = sum(c["duplicate_status"] == "duplicate" for c in rows)
        run["unique_new_count"] = len({c["paper_id"] for c in rows if c["paper_id"] and c["paper_id"] not in run["initial_paper_ids"]})

    @budget.locked
    def resume(self, run_id):
        run = self.data["runs"][run_id]
        self.assert_current(run)
        self.replay(run_id)  # checksum/direction verification before making more requests
        if run["status"] in {"complete", "complete_empty", "complete_unavailable", "limited"}:
            return self.effective(run)
        run["error_history"].extend(run["errors"])
        run["errors"] = []
        run["status"] = "in_progress"
        ids = run["query_parameters"]["seed_paper_ids"]
        try:
            while run["seed_index"] < len(ids):
                pending = next((p for p in run["pages"] if not p["done"]), None)
                if pending is None and self.round_usage(run["expansion_round"])[1] >= self.seed()["max_candidates"]:
                    raise fail("CANDIDATE_LIMIT", "Shared round candidate cap reached before another provider request.", run["provider"])
                seed_id = ids[run["seed_index"]]
                seed = run["seed_snapshots"][seed_id]
                if run["provider"] == "openalex" and not seed.get("provider_ids", {}).get("openalex"):
                    if self.strict_budget():
                        raise fail("LOCAL_SEED_IDENTITY_REQUIRED", "No hidden lookup permitted.", "openalex")
                    doi = normalize_doi(seed.get("doi"))
                    if not doi:
                        raise fail("IDENTIFIER_MISSING", "OpenAlex requires a verified work ID or DOI lookup.", "openalex")
                    lookup = run.setdefault("seed_identity_pages", {}).get(seed_id)
                    if not lookup:
                        lookup = self._fetch(run, lambda: self.providers.openalex_identity(doi), "openalex", "seed_identity")
                        run["seed_identity_pages"][seed_id] = lookup
                        self.save("citation_seed_identity_raw_saved")
                    try:
                        value = json.loads(self.store.verify_raw_response(lookup["raw_response_path"], lookup["sha256"]))
                        if normalize_doi(value.get("doi")) != doi or not str(value.get("id", "")).startswith("https://openalex.org/W"):
                            raise ValueError("OpenAlex seed identity mismatch")
                        seed.setdefault("provider_ids", {})["openalex"] = [value["id"]]
                    except (ValueError, AttributeError, TypeError) as exc:
                        raise fail("MALFORMED_RESPONSE", str(exc), "openalex")
                page = next((p for p in run["pages"] if not p["done"]), None)
                if page is None:
                    page = self._fetch(run, lambda: self.providers.request(run["provider"], run["direction"], seed, run["pagination_cursor"], per_page=20 if self.strict_budget() else 25), run["provider"], "citation_relations")
                    page.update({"seed_paper_id": seed_id, "done": False, "input_cursor": run["pagination_cursor"], "next_record": 0})
                    run["pages"].append(page)
                    self.save("citation_relation_raw_saved")
                body = self.store.verify_raw_response(page["raw_response_path"], page["sha256"])
                rows, cursor, coverage = parse_page(run["provider"], run["direction"], body, seed)
                if coverage not in run["coverage_limitations"]:
                    run["coverage_limitations"].append(coverage)
                page["provider_row_count"] = len(rows)
                if self.strict_budget():
                    page.update(selection_method=budget.POLICY["selection_method"], selected_count=min(20, len(rows)),
                                unprocessed_count=max(0, len(rows) - 20), returned_next_cursor_unused=cursor,
                                processed_count=page["next_record"])
                    rows, cursor = rows[:20], None
                    self.save("citation_selection_rule_applied")
                while page["next_record"] < len(rows):
                    cid = "EC-" + digest([run["expansion_run_id"], {"path": page["raw_response_path"], "sha256": page["sha256"], "record_index": page["next_record"]}])[:24]
                    if cid not in self.data["candidates"] and self.round_usage(run["expansion_round"])[1] >= self.seed()["max_candidates"]:
                        raise fail("CANDIDATE_LIMIT", "Researcher candidate cap reached; remaining raw records retained.", run["provider"])
                    index = page["next_record"]
                    self._candidate(run, seed_id, rows[index], page, index)
                    page["next_record"] += 1
                    if self.strict_budget():
                        page["processed_count"] = page["next_record"]
                    self.save("citation_record_checkpoint")
                if cursor and rows:
                    if str(cursor) == str(page["input_cursor"]) or [seed_id, str(cursor)] in run["seen_cursors"]:
                        raise fail("CURSOR_STALLED", "Provider repeated a cursor; partial records retained.", run["provider"])
                    run["seen_cursors"].append([seed_id, str(cursor)])
                    run["pagination_cursor"] = str(cursor)
                else:
                    run["seed_index"] += 1
                    run["pagination_cursor"] = None
                page["done"] = True
                self.save("citation_page_checkpoint")
            run["status"] = "complete" if run["discovered_count"] else "complete_empty"
            run["stop_reason"] = "planned_seed_paths_executed"
            if not run["discovered_count"] and "REFERENCE_LIST_UNAVAILABLE" in run["coverage_limitations"]:
                run["status"], run["stop_reason"] = "complete_unavailable", "coverage_missing"
            if any(w.startswith("METADATA_REQUEST_LIMIT:") for w in run["warnings"]):
                run["status"], run["stop_reason"] = "limited", "REQUEST_LIMIT"
        except ProviderRequestError as exc:
            run["errors"].append(exc.failure.to_dict())
            run["status"] = "limited" if exc.failure.code in {"REQUEST_LIMIT", "CANDIDATE_LIMIT"} else "partial_failure" if run["pages"] else "failed"
            run["stop_reason"] = exc.failure.code
        run["completed_at"] = utc_now()
        self.count(run)
        self.save("citation_expansion_checkpoint")
        self.export()
        return self.effective(run)

    def effective(self, run):
        seed = self.seed()
        identity = {pid: {k: self.registry.data["records"].get(pid, {}).get(k) for k in ("title", "doi")} for pid in seed["selected_paper_ids"]}
        stale = run["seed_set_version"] != seed["seed_set_version"] or run["protocol_sha256"] != digest(self.context()) or identity != seed["identity_snapshot"]
        return {**run, "effective_status": "stale" if stale else run["status"]}

    def replay(self, run_id):
        """Read-only replay verifies source rows/directions. Never calls an API."""
        run = self.data["runs"][run_id]
        for path, sha in zip(run["raw_response_reference"], run["raw_response_sha256"]):
            self.store.verify_raw_response(path, sha)
        if len(run["raw_response_reference"]) != len(run["raw_response_sha256"]):
            raise ValueError("RAW_INDEX_MISMATCH")
        checked = 0
        for page in run["pages"]:
            body = self.store.verify_raw_response(page["raw_response_path"], page["sha256"])
            try:
                rows, _, _ = parse_page(run["provider"], run["direction"], body, run["seed_snapshots"][page["seed_paper_id"]])
            except ProviderRequestError:
                if not any(c["raw_response_pointer"]["path"] == page["raw_response_path"] for c in self.data["candidates"].values()):
                    continue  # malformed response is preserved as a failed operation, not evidence
                raise
            for c in self.data["candidates"].values():
                if c["expansion_run_id"] != run_id or c["raw_response_pointer"]["path"] != page["raw_response_path"]:
                    continue
                index = c["raw_response_pointer"]["record_index"]
                if index >= len(rows) or rows[index]["raw"] != c["raw_reference"] or c["source_seed"] != page["seed_paper_id"] or c["citation_direction"] != run["direction"]:
                    raise ValueError("CANDIDATE_SOURCE_MISMATCH")
                if c["raw_response_pointer"]["sha256"] != page["sha256"] or c["provider_identifiers"].get("doi") != rows[index].get("doi") or c["provider_identifiers"]["id"] != rows[index]["provider_record_id"]:
                    raise ValueError("CANDIDATE_IDENTIFIER_OR_HASH_MISMATCH")
                checked += 1
        return {"status": "replayed_readonly", "run_id": run_id, "source_records_verified": checked}

    def validate(self):
        errors, stale = [], []
        if self.strict_budget():
            try:
                self.assert_current(validation=True)
                entries = self.budget_transport.inspect()
                if any(e["status"] == "send_unknown" for e in entries):
                    errors.append("REQUEST_SEND_UNKNOWN: no resend or completion allowed")
                for run in self.data["runs"].values():
                    if run["request_count"] != sum(e["reservation"]["run_id"] == run["expansion_run_id"] for e in entries):
                        errors.append("HTTP_COUNT_RECEIPT_MISMATCH")
                counts = {}
                for c in self.data["candidates"].values():
                    key = (c["source_seed"], c["citation_direction"])
                    counts[key] = counts.get(key, 0) + 1
                    if c["raw_response_pointer"]["record_index"] >= 20:
                        errors.append("SELECTION_INDEX_LIMIT")
                if any(n > 20 for n in counts.values()) or sum(counts.values()) > 120:
                    errors.append("OBSERVATION_LIMIT")
            except (ValueError, RuntimeError, OSError, KeyError) as exc:
                errors.append(str(exc))
        parsed = {}
        for rid, run in self.data["runs"].items():
            try:
                self.replay(rid)
                if self.effective(run)["effective_status"] == "stale":
                    stale.append(rid)
            except (ValueError, RuntimeError, OSError, KeyError) as exc:
                errors.append(str(exc))
        for edge in self.data["edges"].values():
            for p in edge["provenance"]:
                c = self.data["candidates"].get(p["candidate_id"])
                if not c:
                    errors.append("EDGE_CANDIDATE_MISSING")
                    continue
                run = self.data["runs"][c["expansion_run_id"]]
                page = next(x for x in run["pages"] if x["raw_response_path"] == c["raw_response_pointer"]["path"])
                try:
                    key = (run["expansion_run_id"], page["raw_response_path"])
                    if key not in parsed:
                        parsed[key] = parse_page(run["provider"], run["direction"], self.store.verify_raw_response(page["raw_response_path"], page["sha256"]), run["seed_snapshots"][c["source_seed"]])[0]
                    rows = parsed[key]
                    row = rows[c["raw_response_pointer"]["record_index"]]
                    if not row["relation_valid"]:
                        errors.append("UNVERIFIED_RELATION_HAS_EDGE")
                    if c["paper_id"]:
                        paper = self.registry.data["records"].get(c["paper_id"])
                        if not paper or (row.get("doi") and normalize_doi(paper.get("doi")) != row["doi"]):
                            errors.append("EDGE_PAPER_IDENTITY_MISMATCH")
                except (ValueError, RuntimeError, OSError, KeyError, IndexError) as exc:
                    errors.append("EDGE_SOURCE_INVALID:" + str(exc))
                other = c["paper_id"] or ("external:doi:" + c["provider_identifiers"]["doi"] if c["provider_identifiers"].get("doi") else "external:reference:" + digest(c["raw_reference"])[:24])
                expected = (c["source_seed"], other) if c["citation_direction"] == "backward" else (other, c["source_seed"])
                if expected != (edge["citing_identity"], edge["cited_identity"]) or p["raw_response_pointer"] != c["raw_response_pointer"]:
                    errors.append("EDGE_DIRECTION_OR_PROVENANCE_MISMATCH")
        exported = self.state.get("citation_exports", {})
        for relative, sha in exported.get("files", {}).items():
            path = self.store.resolve_relative(relative)
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                errors.append("STALE_OR_MODIFIED_CITATION_EXPORT:" + relative)
        if exported and exported.get("data_sha256") != digest(self.data):
            errors.append("CITATION_EXPORTS_NEED_REGENERATION")
        return {"valid": not errors, "errors": sorted(set(errors)), "stale_run_ids": stale, "edge_count": len(self.data["edges"]), "candidate_count": len(self.data["candidates"])}

    def review_digest(self):
        return digest({"seed": self.seed(), "runs": self.data["runs"], "candidates": self.data["candidates"], "edges": self.data["edges"]})

    def review(self, by, note, limitations, reason):
        self.assert_current()
        if self.context().get("mode") == "lab":
            raise ValueError("LAB_CANNOT_APPROVE_PHASE4")
        if not all(str(x).strip() for x in (by, note, limitations)) or reason not in {"low_yield_suggested", "quota_exhausted", "coverage_missing", "user_limit", "human_stop", "planned_paths_executed"}:
            raise ValueError("NAMED_STOPPING_AND_COVERAGE_REVIEW_REQUIRED")
        value = {"reviewed_by": by, "review_note": note, "accepted_limitations": limitations, "stopping_reason": reason,
                 "reviewed_at": utc_now(), "snapshot_sha256": self.review_digest(), "seed_set_version": self.seed()["seed_set_version"]}
        self.data["reviews"].append(value)
        self.save("citation_human_review_recorded")
        self.export()
        return self.completion()

    def completion(self):
        issues = []
        try:
            self.assert_current(validation=True)
        except (ValueError, OSError) as exc:
            issues.append(str(exc))
        if not self.data["seeds"]:
            return {"valid": False, "issues": issues + ["SEED_SET_REQUIRED"]}
        if self.context().get("mode") == "lab":
            issues.append("LAB_NOT_OFFICIAL_PHASE4")
        seed = self.seed()
        runs = [r for r in self.data["runs"].values() if r["seed_set_version"] == seed["seed_set_version"]]
        for path in seed["provider_plan"]:
            if not any(r["provider"] == path["provider"] and r["direction"] == path["direction"] and r["status"] in {"complete", "complete_empty", "complete_unavailable", "limited", "partial_failure", "failed"} for r in runs):
                issues.append("PLAN_PATH_NOT_ATTEMPTED:" + canonical_json(path))
        if self.strict_budget():
            try:
                receipts = self.budget_transport.inspect()
                for request in budget.requests(seed, self.registry.data["records"]):
                    if not any(all(e["reservation"][k] == request[k] for k in ("provider", "direction", "seed_paper_id")) for e in receipts):
                        issues.append("SEED_DIRECTION_NOT_ATTEMPTED:" + canonical_json(request))
            except (ValueError, RuntimeError, OSError) as exc:
                issues.append(str(exc))
        if any(r["status"] == "in_progress" for r in runs):
            issues.append("EXPANSION_IN_PROGRESS")
        integrity = self.validate()
        issues += integrity["errors"]
        reviews = self.data["reviews"]
        if not reviews or reviews[-1]["snapshot_sha256"] != self.review_digest():
            issues.append("CURRENT_HUMAN_REVIEW_REQUIRED")
        return {"valid": not issues, "issues": issues, "phase": 4, "automatically_completed": False,
                "unresolved_count": sum(r["unresolved_count"] for r in runs), "limited_operations": [r["expansion_run_id"] for r in runs if r["status"] not in {"complete", "complete_empty"}]}

    def recover(self):
        recover_state(self.root)
        self.__init__(self.root, self.providers, budget_opener=self._budget_opener)
        self.export()
        return {"status": "recovered", "validation": self.validate()}

    def export(self):
        out = self.root / "02_discovery"
        out.mkdir(parents=True, exist_ok=True)
        if self.data["seeds"]:
            write_json_atomic(out / "SEED_SET.json", self.seed())
        for seed in self.data["seeds"]:
            write_json_atomic(out / "seed_sets" / f"seed-{seed['seed_set_version']:04d}.json", seed)
        for rid, run in self.data["runs"].items():
            write_json_atomic(out / "citation_runs" / (rid + ".json"), self.effective(run))
        candidates = list(self.data["candidates"].values())
        write_json_atomic(out / "EXPANSION_CANDIDATES.json", candidates)
        write_json_atomic(out / "CITATION_GRAPH.json", list(self.data["edges"].values()))
        if self.data["reviews"]:
            write_json_atomic(out / "CITATION_REVIEW.json", self.data["reviews"][-1])
        for name, rows in [("CITATION_EDGES.csv", list(self.data["edges"].values())), ("CITATION_EXPANSION_LOG.csv", [self.effective(r) for r in self.data["runs"].values()])]:
            fields = list(rows[0]) if rows else (["citation_edge_id", "citing_identity", "cited_identity", "provenance"] if name.startswith("CITATION_EDGES") else ["expansion_run_id", "status"])
            PaperRegistry._write_csv_atomic(out / name, fields, [{k: canonical_json(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows])
        for direction, filename in [("backward", "BACKWARD_CITATIONS.csv"), ("forward", "FORWARD_CITATIONS.csv"), (None, "DISCOVERY_MASTER.csv")]:
            path = out / filename
            existing = []
            fields = list(CSV_FIELDS["discovery"])
            if path.exists():
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    fields += [f for f in reader.fieldnames or [] if f not in fields]
                    existing = [r for r in reader if r.get("discovery_source") != "rra_citation_expansion"]
            for c in candidates:
                if direction and c["citation_direction"] != direction:
                    continue
                m = c["bibliographic_metadata"]
                existing.append({"paper_id": c["paper_id"] or "", "title": m.get("title", ""), "authors": "; ".join(m.get("authors", [])), "year": m.get("publication_year") or "", "doi": c["provider_identifiers"].get("doi") or "", "journal": m.get("source_title") or "", "paper_type": m.get("work_type") or "", "theme": "", "why_relevant": "", "discovery_source": "rra_citation_expansion", "source_identifier": c["candidate_id"], "abstract_basis": "metadata_only", "example_data": "false", "extension_json": canonical_json(c)})
            PaperRegistry._write_csv_atomic(path, fields, existing)
        related = out / "RELATED_PAPERS.csv"
        if not related.exists():
            PaperRegistry._write_csv_atomic(related, CSV_FIELDS["discovery"], [])
        lines = ["# Citation expansion rounds", "", COVERAGE, "", "Counts are candidate observations; unique_new is distinct IDs absent at run start. Requests include failures and metadata lookups.", ""]
        for number in sorted({r["expansion_round"] for r in self.data["runs"].values()}):
            runs = [r for r in self.data["runs"].values() if r["expansion_round"] == number]
            new_ids = {c["paper_id"] for r in runs for c in candidates if c["expansion_run_id"] == r["expansion_run_id"] and c["paper_id"] and c["paper_id"] not in r["initial_paper_ids"]}
            lines += [f"## Round {number}", "", f"Distinct newly registered IDs across runs: {len(new_ids)}. No automatic seed promotion.", ""]
            for r in runs:
                n = r["discovered_count"]
                lines.append(f"- {r['expansion_run_id']} {r['provider']}/{r['direction']}: {self.effective(r)['effective_status']}; discovered={n}, resolved={r['resolved_count']}, unresolved={r['unresolved_count']}, duplicates={r['duplicate_count']}, new={r['unique_new_count']}, duplicate proportion={r['duplicate_count']/n if n else 0:.3f}; stop={r['stop_reason']}")
                lines.append("  Coverage: " + "; ".join(r["coverage_limitations"]))
        lines += ["", "Low yield may suggest a stopping proposal, but never establishes saturation. Quota, coverage gaps and imposed caps are separate causes. Human review is required.", ""]
        PaperRegistry._write_text_atomic(out / "EXPANSION_ROUND_REPORT.md", "\n".join(lines))
        PaperRegistry._write_text_atomic(out / "CITATION_COVERAGE_REPORT.md", "# Citation coverage and stopping\n\n" + "\n".join(lines[2:]) + "\nRelated recommendations: not implemented; no citation edges inferred. Humanities/non-DOI sources may be underrepresented.\n")
        names = ["BACKWARD_CITATIONS.csv", "FORWARD_CITATIONS.csv", "CITATION_EDGES.csv", "CITATION_EXPANSION_LOG.csv", "SEED_SET.json", "EXPANSION_CANDIDATES.json", "CITATION_GRAPH.json", "EXPANSION_ROUND_REPORT.md", "CITATION_COVERAGE_REPORT.md"]
        if self.data["reviews"]:
            names.append("CITATION_REVIEW.json")
        files = {"02_discovery/" + name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in names if (out / name).exists()}
        state = load_state(self.root)
        state["citation_exports"] = {"files": files, "data_sha256": digest(self.data)}
        self.state = persist_state(self.root, state, "citation_artifacts_exported")
        return {"status": "exported", "runs": len(self.data["runs"]), "candidates": len(candidates), "edges": len(self.data["edges"])}
