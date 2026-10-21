"""Opt-in, fail-closed single-page citation budget. No model or network preflight.

Receipts supplement (never replace) the workflow journal. A reservation consumes
a *possible send* even if the process dies before opening a socket. There is no
automatic refund, retry, redirect, pagination or identity lookup.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import replace
from functools import wraps
from urllib.parse import quote, urlencode

from ..amendments import project_lock
from ..state import canonical_json, load_state, utc_now
from ..scholarly.transport import HttpResponse, HttpTransport, ProviderRequestError
from ..scholarly.providers import _safe_headers
from .providers import fail

POLICY = {
    "policy_id": "bounded_first_page_v1", "http_limit": 6,
    "relations_per_seed_direction": 20, "selection_method": "provider_order_first_n_v1",
    "identity_resolution": "local_only", "automatic_retries": 0,
    "automatic_pagination": False, "automatic_fallback": False,
}
PLAN = [{"provider": "crossref", "direction": "backward"},
        {"provider": "openalex", "direction": "forward"}]


def sha(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def fault(stage):
    """Test-only interruption seam. No environment/CLI bypass."""


def locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with project_lock(self.root):
            return method(self, *args, **kwargs)
    return call


def strict(seed):
    return bool(seed.get("budget_policy"))


def identity(records, ids):
    return json.loads(canonical_json({pid: {k: records[pid].get(k) for k in ("title", "doi", "provider_ids")} for pid in ids}))


def protocol_file_hash(pipeline):
    path = pipeline.root / "00_protocol/PROTOCOL.json"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def check_config_context(pipeline, config):
    if config.get("expected_protocol_sha256") != sha(pipeline.context()):
        raise ValueError("PROTOCOL_HASH_CONFLICT")
    if pipeline.context().get("mode") != "lab":
        if config.get("expected_project_id") != pipeline.context()["project_id"] or config.get("expected_protocol_file_sha256") != protocol_file_hash(pipeline):
            raise ValueError("PROJECT_OR_PROTOCOL_FILE_HASH_CONFLICT")


def validate_config(config, records):
    if config.get("budget_policy") != POLICY:
        raise ValueError("STRICT_BUDGET_POLICY_MISMATCH")
    ids = config["selected_paper_ids"]
    if not 1 <= len(ids) <= 3 or len(ids) != len(set(ids)):
        raise ValueError("STRICT_SEED_LIMIT")
    if config.get("provider_plan") != PLAN or config.get("expansion_depth_limit") != 1:
        raise ValueError("STRICT_PLAN_OR_DEPTH_MISMATCH")
    if config.get("max_requests") != 6 or config.get("max_candidates") != 120:
        raise ValueError("STRICT_LIMIT_MISMATCH")
    for pid in ids:
        record = records[pid]
        ids_oa = record.get("provider_ids", {}).get("openalex", [])
        import re
        if not record.get("doi") or len(ids_oa) != 1 or not re.fullmatch(r"(?:https://openalex.org/)?W\d+", ids_oa[0]):
            raise ValueError("LOCAL_SEED_IDENTITY_REQUIRED:" + pid)
    return requests(config, records)


def requests(seed, records):
    result = []
    for path in seed["provider_plan"]:
        for pid in seed["selected_paper_ids"]:
            record = records[pid]
            if path["provider"] == "crossref":
                params = {"doi": record["doi"]}
                url = "https://api.crossref.org/v1/works/" + quote(record["doi"], safe="")
            else:
                wid = record["provider_ids"]["openalex"][0].rsplit("/", 1)[-1]
                params = {"filter": "cites:" + wid, "per_page": "20", "cursor": "*"}
                url = "https://api.openalex.org/works?" + urlencode(params)
            result.append({**path, "seed_paper_id": pid, "url": url, "parameters": params,
                           "http_slots": 1, "processed_limit": 20})
    return result


def binding(seed):
    # Approval itself is not part of the reviewed plan checksum.
    return sha({k: v for k, v in seed.items() if k not in {"approval", "approval_status", "plan_sha256"}})


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def immutable_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())
    sync_dir(path.parent)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BudgetTransport:
    """Only this request boundary can send while the strict pipeline is active."""
    def __init__(self, pipeline, opener=None):
        self.p = pipeline
        self.root = pipeline.root
        self.directory = self.root / ".review/citation_http_budget"
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open
        self.active = None

    @contextmanager
    def scope(self, run, seed_id):
        if self.active is not None:
            raise ValueError("CONFLICTING_HTTP_SCOPE")
        expected = next(r for r in requests(self.p.seed(), self.p.registry.data["records"])
                        if (r["provider"], r["direction"], r["seed_paper_id"]) == (run["provider"], run["direction"], seed_id))
        self.active = (run, expected)
        try:
            yield
        finally:
            self.active = None

    def inspect(self):
        entries = []
        if not self.directory.exists():
            return entries
        for path in sorted(self.directory.iterdir()):
            if not path.is_dir():
                raise ValueError("BUDGET_LEDGER_UNEXPECTED_FILE")
            reservation = json.loads((path / "reservation.json").read_text())
            if reservation["plan_sha256"] != binding(self.p.seed()):
                raise ValueError("BUDGET_PLAN_VERSION_CONFLICT")
            if reservation["run_id"] not in self.p.data["runs"]:
                raise ValueError("BUDGET_ORPHAN_RESERVATION_RECOVER_JOURNAL")
            expected = next((r for r in requests(self.p.seed(), self.p.registry.data["records"])
                             if all(reservation.get(k) == r[k] for k in ("provider", "direction", "seed_paper_id"))), None)
            if expected is None or any(reservation.get(k) != v for k, v in expected.items()):
                raise ValueError("BUDGET_RESERVATION_PLAN_MISMATCH")
            if path.name != sha([reservation["provider"], reservation["direction"], reservation["seed_paper_id"]])[:24]:
                raise ValueError("BUDGET_RESERVATION_PATH_MISMATCH")
            result = {"reservation": reservation, "status": "send_unknown", "directory": path.name}
            receipt = path / "response.json"
            if receipt.exists():
                value = json.loads(receipt.read_text())
                if value["reservation_sha256"] != sha(reservation):
                    raise ValueError("BUDGET_RECEIPT_BINDING_MISMATCH")
                self.p.store.verify_raw_response(value["raw_response_path"], value["sha256"])
                result.update(status="response_saved", response=value)
            entries.append(result)
        if len(entries) > POLICY["http_limit"]:
            raise ValueError("HTTP_BUDGET_EXCEEDED")
        if len({e["reservation"]["budget_slot"] for e in entries}) != len(entries):
            raise ValueError("BUDGET_SLOT_COLLISION")
        return entries

    def _response(self, value, provider, url):
        body = self.p.store.verify_raw_response(value["raw_response_path"], value["sha256"])
        if not 200 <= value["http_status"] < 300:
            from ..scholarly.transport import _error_message
            message, code = _error_message(body, "Saved HTTP failure; automatic resend forbidden.")
            code, _ = HttpTransport._http_failure_code(value["http_status"], code, message)
            error = fail(code, message, provider)
            raise ProviderRequestError(replace(error.failure, http_status=value["http_status"]))
        return HttpResponse(value["http_status"], value["headers"], body, url)

    @locked
    def get(self, *, provider, url, headers):
        if self.active is None:
            raise fail("HTTP_SCOPE_REQUIRED", "No identity lookup or unscoped request is authorized.", provider)
        run, expected = self.active
        if url != expected["url"] or provider != expected["provider"]:
            raise fail("HTTP_REQUEST_NOT_AUTHORIZED", "No pagination, alternate source or DOI lookup is authorized.", provider)
        self.p.assert_current(run)
        if load_state(self.root)["seq"] != self.p.state["seq"]:
            raise ValueError("CITATION_STATE_VERSION_CONFLICT")
        key = sha([provider, run["direction"], expected["seed_paper_id"]])[:24]
        entries = self.inspect()
        if len(entries) < sum(r["request_count"] for r in self.p.data["runs"].values()):
            raise ValueError("BUDGET_LEDGER_MISSING_RESERVED_ATTEMPTS")
        existing = next((e for e in entries if e["directory"] == key), None)
        if existing:
            if existing["reservation"]["run_id"] != run["expansion_run_id"]:
                raise ValueError("REQUEST_ALREADY_BOUND_TO_OTHER_RUN")
            if existing["status"] != "response_saved":
                raise fail("REQUEST_SEND_UNKNOWN", "Reserved request may have been sent; stop, inspect, never blindly retry.", provider)
            return self._response(existing["response"], provider, url)
        if any(e["status"] == "send_unknown" for e in entries):
            raise fail("REQUEST_SEND_UNKNOWN", "An earlier request has uncertain send status; all new sends blocked.", provider)
        if len(entries) >= POLICY["http_limit"]:
            raise fail("REQUEST_LIMIT", "All six possible-send slots consumed.", provider)
        directory = self.directory / key
        directory.mkdir(parents=True, exist_ok=False)
        sync_dir(directory.parent)
        sync_dir(directory.parent.parent)
        reservation = {**expected, "run_id": run["expansion_run_id"], "plan_sha256": binding(self.p.seed()),
                       "project_id": self.p.context()["project_id"], "reserved_at": utc_now(),
                       "selection_method": POLICY["selection_method"], "attempt": 1,
                       "budget_slot": len(entries) + 1, "send_status": "possible_send_no_automatic_refund"}
        immutable_json(directory / "reservation.json", reservation)
        run["request_count"] += 1
        self.p.save("citation_http_attempt_reserved")
        fault("after_reservation")
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            response = self.opener(request, timeout=25)
            with response:
                body, status = response.read(), int(response.status)
                response_headers = dict(response.headers)
        except urllib.error.HTTPError as exc:
            body, status, response_headers = exc.read(), exc.code, dict(exc.headers or {})
        except (OSError, urllib.error.URLError) as exc:
            # Uncertain send; persist diagnostics but never refund or retry.
            immutable_json(directory / "uncertain.json", {"error_type": type(exc).__name__, "at": utc_now()})
            raise fail("REQUEST_SEND_UNKNOWN", "Network failure without a durable complete response; no resend authorized.", provider) from exc
        fault("after_wire_before_receipt")
        path, checksum = self.p.store.write_raw_response(provider, run["expansion_run_id"], reservation["budget_slot"], body)
        sync_dir((self.root / path).parent)
        value = {"reservation_sha256": sha(reservation), "raw_response_path": path, "sha256": checksum,
                 "http_status": status, "headers": _safe_headers(response_headers), "retrieved_at": utc_now(),
                 "url": url, "parameters": expected["parameters"]}
        immutable_json(directory / "response.json", value)
        fault("after_response_receipt")
        return self._response(value, provider, url)


def preflight(pipeline, config=None):
    seed = config or pipeline.seed()
    table = validate_config(seed, pipeline.registry.data["records"])
    if config:
        check_config_context(pipeline, config)
    registered = bool(pipeline.data["seeds"])
    approved = registered and pipeline.seed().get("approval_status") == "human_approved"
    receipts = BudgetTransport(pipeline).inspect() if registered and strict(pipeline.seed()) else []
    blockers = []
    if not registered:
        blockers.append("SEED_SET_NOT_REGISTERED")
    if not approved:
        blockers.append("ACTUAL_HUMAN_SEED_APPROVAL_REQUIRED")
    if pipeline.state["phases"]["4"]["status"] != "in_progress":
        blockers.append("PHASE4_NOT_IN_PROGRESS")
    if any(e["status"] == "send_unknown" for e in receipts):
        blockers.append("REQUEST_SEND_UNKNOWN")
    if registered:
        try:
            pipeline.assert_current()
        except (ValueError, OSError) as exc:
            blockers.append(str(exc))
    return {"read_only": True, "network_requests": 0, "config_valid": True,
            "config_sha256": sha(seed), "plan_sha256": binding(pipeline.seed()) if registered else None,
            "requests": table, "possible_send_limit": 6, "processed_observation_limit": 120,
            "registered_seed_set": registered, "human_approved": approved,
            "phase4_status": pipeline.state["phases"]["4"]["status"],
            "receipts": receipts, "blocked_by": blockers, "allowed_to_execute": not blockers,
            "note": "Preflight is not execution authorization or identity authentication."}
