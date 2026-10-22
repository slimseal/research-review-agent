"""Durable possible-send accounting for discovery and access probes, not approvals."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from ..state import utc_now, write_json_atomic
from .contracts import ProviderFailure
from .transport import HttpTransport, ProviderRequestError


SECRET_NAMES = {"api_key", "apikey", "key", "token", "access_token", "mailto", "email"}


def rate_headers(headers):
    """Persist useful throttling evidence without arbitrary header strings/secret echoes."""
    result = {}
    for name, value in headers.items():
        name, value = name.lower(), str(value)
        if name == "retry-after":
            try:
                if not re.fullmatch(r"\d+(\.\d+)?", value):
                    parsedate_to_datetime(value)
                result[name] = value
            except (ValueError, TypeError, OverflowError):
                pass
        elif name.startswith(("x-ratelimit-", "x-rate-limit-", "ratelimit-")) and re.fullmatch(r"[0-9. /;-]+", value):
            result[name] = value
    return result


def redact_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = [(k, "[redacted]" if k.casefold() in SECRET_NAMES else v)
             for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RecordedTransport:
    """A receipt is fsynced before sending. Unknown sends stop; never blind-retry.

    One owner per ledger, fixed total budget across reopens, no redirects.
    Search calls and metadata subrequests share this same transport.
    """
    def __init__(self, directory: Path, *, max_requests: int, max_attempts: int = 1,
                 opener=None, sleep=time.sleep, timeout: float = 15):
        if max_requests < 1 or max_attempts < 1 or max_attempts > max_requests:
            raise ValueError("INVALID_HTTP_BUDGET")
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "budget.json"
        self.lock = directory / "active.lock"
        self.max_requests, self.max_attempts = max_requests, max_attempts
        self.sleep = sleep
        self.http = HttpTransport(timeout=timeout, max_attempts=1, sleep=sleep,
                                  opener=opener or urllib.request.build_opener(NoRedirect()).open)
        if not self.path.exists():
            # Exclusive creation prevents a competing constructor resetting the budget.
            try:
                with self.path.open("x", encoding="utf-8") as handle:
                    json.dump({"max_requests": max_requests, "max_attempts": max_attempts, "receipts": []}, handle)
                    handle.flush(); os.fsync(handle.fileno())
            except FileExistsError:
                pass
        self._read()

    def _read(self):
        value = json.loads(self.path.read_text())
        if value["max_requests"] != self.max_requests or value["max_attempts"] != self.max_attempts:
            raise ValueError("HTTP_BUDGET_CONFLICT: new authorization needs a separate ledger")
        if len(value["receipts"]) > value["max_requests"] or any(
            r.get("sequence") != i for i, r in enumerate(value["receipts"], 1)):
            raise ValueError("HTTP_LEDGER_CORRUPT")
        if any(r["status"] in {"possible_send", "send_uncertain"} for r in value["receipts"]):
            raise ValueError("HTTP_SEND_UNCERTAIN: inspect receipt; do not blindly resend")
        return value

    def validate(self):
        state = json.loads(self.path.read_text())
        errors = []
        if len(state["receipts"]) > state["max_requests"]:
            errors.append("HTTP_BUDGET_EXCEEDED")
        for sequence, r in enumerate(state["receipts"], 1):
            if r.get("sequence") != sequence:
                errors.append("HTTP_RECEIPT_SEQUENCE_MISMATCH")
            if r.get("status") == "received":
                raw = (self.directory / r["raw_file"]).resolve()
                if raw.parent != self.directory.resolve() or not raw.is_file():
                    errors.append("HTTP_RAW_MISSING_OR_UNSAFE")
                elif hashlib.sha256(raw.read_bytes()).hexdigest() != r["sha256"]:
                    errors.append("HTTP_RAW_CHECKSUM_MISMATCH")
            elif r.get("status") in {"send_uncertain", "possible_send"}:
                errors.append("HTTP_SEND_UNCERTAIN")
            elif r.get("status") != "failed":
                errors.append("HTTP_RECEIPT_STATUS_INVALID")
        return errors

    @property
    def used(self):
        return len(json.loads(self.path.read_text())["receipts"])

    def get(self, *, provider, url, headers):
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError("HTTP_OPERATION_CONFLICT: inspect existing owner/receipt") from exc
        os.close(fd)
        try:
            state = self._read()
            for attempt in range(1, self.max_attempts + 1):
                if len(state["receipts"]) >= self.max_requests:
                    raise ProviderRequestError(ProviderFailure("REQUEST_BUDGET_EXHAUSTED", provider,
                        "No HTTP request sent: approved possible-send budget exhausted.", utc_now(), False, 0))
                receipt = {"sequence": len(state["receipts"]) + 1, "provider": provider,
                           "url": redact_url(url), "attempt": attempt, "started_at": utc_now(),
                           "status": "possible_send"}
                state["receipts"].append(receipt)
                write_json_atomic(self.path, state)
                # Conservative per-client pace; institutional NAT limits can be lower.
                self.sleep({"semantic_scholar": 1.05, "arxiv": 3.05, "openaire": 1.05, "eric": 1.05}.get(provider, 0.35))
                try:
                    response = self.http.get(provider=provider, url=url, headers=headers)
                except ProviderRequestError as exc:
                    f = exc.failure
                    uncertain = f.http_status is None
                    receipt.update(status="send_uncertain" if uncertain else "failed",
                                   http_status=f.http_status, error_code=f.code, completed_at=utc_now(),
                                   response_headers=rate_headers(f.details.get("response_headers", {})))
                    write_json_atomic(self.path, state)
                    # Never persist untrusted error messages (providers can echo secrets).
                    safe = replace(f, attempt=attempt, message=f"{f.code}: endpoint request did not succeed.",
                                   details={"provider_error_code": str(f.details.get("provider_error_code", ""))
                                            if str(f.details.get("provider_error_code", "")) in {
                                                "key_not_activated", "not_enough_credits", "quota_exceeded",
                                                "invalid_api_key", "insufficient_privileges"} else "",
                                            "response_headers": receipt["response_headers"]})
                    if not uncertain and f.retryable and attempt < self.max_attempts:
                        delay = self.http._retry_delay(f.details.get("response_headers", {}), attempt)
                        retry_after = receipt["response_headers"].get("retry-after")
                        if retry_after:
                            try:
                                required_delay = float(retry_after)
                            except ValueError:
                                required_delay = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                            # Pause instead of shortening a provider's mandatory wait.
                            if required_delay > 60:
                                raise ProviderRequestError(safe) from None
                            delay = max(0, required_delay)
                        self.sleep(delay)
                        continue
                    raise ProviderRequestError(safe) from None
                raw = response.body
                sensitive = [v for k, v in urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query)
                             if k.casefold() in SECRET_NAMES and v]
                sensitive += [v.removeprefix("Bearer ") for k, v in headers.items()
                              if k.lower() in {"authorization", "x-api-key", "x-apikey", "crossref-plus-api-token"}]
                if any(s.encode() in raw for s in sensitive):
                    receipt.update(status="failed", error_code="SENSITIVE_RESPONSE_REJECTED", completed_at=utc_now())
                    write_json_atomic(self.path, state)
                    raise ProviderRequestError(ProviderFailure("SENSITIVE_RESPONSE_REJECTED", provider,
                        "Response echoed private credentials; not stored or ingested.", utc_now(), False, attempt))
                raw_path = self.directory / f"response-{receipt['sequence']:06d}.bin"
                with raw_path.open("xb") as handle:
                    handle.write(raw); handle.flush(); os.fsync(handle.fileno())
                receipt.update(status="received", http_status=response.status, completed_at=utc_now(),
                               raw_file=raw_path.name, sha256=hashlib.sha256(raw).hexdigest(),
                               response_headers=rate_headers(response.headers))
                write_json_atomic(self.path, state)
                return response
            raise AssertionError("unreachable")
        finally:
            self.lock.unlink(missing_ok=True)
