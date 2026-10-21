from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import Message
from typing import Callable

from ..state import utc_now
from .contracts import ProviderFailure


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    final_url: str


class ProviderRequestError(RuntimeError):
    def __init__(self, failure: ProviderFailure):
        super().__init__(f"{failure.code}: {failure.message}")
        self.failure = failure


def _headers_dict(headers: Message | dict[str, str] | None) -> dict[str, str]:
    if headers is None:
        return {}
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _error_message(body: bytes, fallback: str) -> tuple[str, str | None]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return fallback, None
    if not isinstance(payload, dict):
        return fallback, None
    provider_code = payload.get("error") or payload.get("status")
    message = payload.get("message") or payload.get("message-type") or fallback
    return str(message), str(provider_code) if provider_code else None


class HttpTransport:
    """Dependency-free GET transport with bounded retry and stable error codes."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[..., object] | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self.sleep = sleep
        self.opener = opener or urllib.request.urlopen

    def get(self, *, provider: str, url: str, headers: dict[str, str]) -> HttpResponse:
        last_failure: ProviderFailure | None = None
        for attempt in range(1, self.max_attempts + 1):
            request = urllib.request.Request(url, headers=headers, method="GET")
            try:
                response = self.opener(request, timeout=self.timeout)
                with response:  # type: ignore[attr-defined]
                    body = response.read()  # type: ignore[attr-defined]
                    status = int(getattr(response, "status", 200))
                    response_headers = _headers_dict(getattr(response, "headers", None))
                    final_url = str(getattr(response, "url", url))
                return HttpResponse(status=status, headers=response_headers, body=body, final_url=final_url)
            except urllib.error.HTTPError as exc:
                body = exc.read()
                response_headers = _headers_dict(exc.headers)
                message, provider_code = _error_message(body, str(exc.reason))
                code, retryable = self._http_failure_code(exc.code, provider_code, message)
                safe_error_headers = {
                    key: value
                    for key, value in response_headers.items()
                    if key.startswith("x-ratelimit-")
                    or key.startswith("x-rate-limit-")
                    or key in {"retry-after", "x-concurrency-limit", "x-api-pool"}
                }
                details: dict[str, object] = {}
                if provider_code:
                    details["provider_error_code"] = provider_code
                if safe_error_headers:
                    details["response_headers"] = safe_error_headers
                last_failure = ProviderFailure(
                    code=code,
                    provider=provider,
                    message=message,
                    occurred_at=utc_now(),
                    retryable=retryable,
                    attempt=attempt,
                    http_status=exc.code,
                    details=details,
                )
                if retryable and attempt < self.max_attempts:
                    self.sleep(self._retry_delay(response_headers, attempt))
                    continue
                raise ProviderRequestError(last_failure) from exc
            except (TimeoutError, socket.timeout) as exc:
                last_failure = ProviderFailure(
                    code="TIMEOUT",
                    provider=provider,
                    message="The provider request timed out.",
                    occurred_at=utc_now(),
                    retryable=True,
                    attempt=attempt,
                )
                if attempt < self.max_attempts:
                    self.sleep(2 ** (attempt - 1))
                    continue
                raise ProviderRequestError(last_failure) from exc
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", exc)
                is_timeout = isinstance(reason, (TimeoutError, socket.timeout))
                last_failure = ProviderFailure(
                    code="TIMEOUT" if is_timeout else "NETWORK_UNAVAILABLE",
                    provider=provider,
                    message="The provider request timed out." if is_timeout else f"Network request failed: {reason}",
                    occurred_at=utc_now(),
                    retryable=True,
                    attempt=attempt,
                )
                if attempt < self.max_attempts:
                    self.sleep(2 ** (attempt - 1))
                    continue
                raise ProviderRequestError(last_failure) from exc
            except OSError as exc:
                last_failure = ProviderFailure(
                    code="NETWORK_UNAVAILABLE",
                    provider=provider,
                    message=f"Network request failed: {exc}",
                    occurred_at=utc_now(),
                    retryable=True,
                    attempt=attempt,
                )
                if attempt < self.max_attempts:
                    self.sleep(2 ** (attempt - 1))
                    continue
                raise ProviderRequestError(last_failure) from exc
        assert last_failure is not None
        raise ProviderRequestError(last_failure)

    @staticmethod
    def _http_failure_code(status: int, provider_code: str | None, message: str = "") -> tuple[str, bool]:
        if status == 429:
            quota_text = f"{provider_code or ''} {message}".casefold()
            if any(marker in quota_text for marker in ("not_enough_credits", "quota_exceeded", "insufficient budget", "daily budget", "$0 remaining")):
                return "QUOTA_EXHAUSTED", False
            return "HTTP_RATE_LIMITED", True
        if status == 401:
            return "AUTHENTICATION_FAILED", False
        if status == 403:
            return "ACCESS_FORBIDDEN", False
        if status in {408, 504}:
            return "TIMEOUT", True
        if 500 <= status <= 599:
            return "HTTP_SERVER_ERROR", True
        if status == 404:
            return "IDENTIFIER_NOT_FOUND", False
        if status == 400:
            return "INVALID_REQUEST", False
        return "PROVIDER_HTTP_ERROR", False

    @staticmethod
    def _retry_delay(headers: dict[str, str], attempt: int) -> float:
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 60.0)
            except ValueError:
                pass
        return float(2 ** (attempt - 1))
