from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

from ..state import utc_now
from .contracts import ProviderFailure, SearchRequest
from .transport import HttpResponse, HttpTransport, ProviderRequestError


OPENALEX_BASE_URL = "https://api.openalex.org/works"
CROSSREF_BASE_URL = "https://api.crossref.org/v1/works"


@dataclass(frozen=True)
class FetchedPage:
    provider: str
    body: bytes
    payload: dict[str, Any]
    records: list[dict[str, Any]]
    request_url_redacted: str
    request_parameters: dict[str, Any]
    http_status: int
    response_headers: dict[str, str]
    retrieved_at: str
    next_cursor: str | None


def _decode_payload(provider: str, response: HttpResponse) -> dict[str, Any]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderRequestError(
            ProviderFailure(
                code="MALFORMED_RESPONSE",
                provider=provider,
                message="Provider returned a non-JSON or malformed JSON response.",
                occurred_at=utc_now(),
                retryable=False,
                attempt=1,
                http_status=response.status,
            )
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderRequestError(
            ProviderFailure(
                code="MALFORMED_RESPONSE",
                provider=provider,
                message="Provider JSON response must be an object.",
                occurred_at=utc_now(),
                retryable=False,
                attempt=1,
                http_status=response.status,
            )
        )
    return payload


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    allowed = {
        "content-type",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-credits-used",
        "x-ratelimit-reset",
        "x-rate-limit-limit",
        "x-rate-limit-interval",
        "x-concurrency-limit",
        "x-api-pool",
    }
    return {key: value for key, value in headers.items() if key.lower() in allowed}


class OpenAlexAdapter:
    name = "openalex"

    def __init__(self, transport: HttpTransport | None = None, api_key: str | None = None) -> None:
        self.transport = transport or HttpTransport()
        self.api_key = api_key if api_key is not None else os.environ.get("OPENALEX_API_KEY")

    def fetch_search_page(self, request: SearchRequest, cursor: str | None) -> FetchedPage:
        active_cursor = cursor or "*"
        if active_cursor != "*" and not self.api_key:
            raise ProviderRequestError(
                ProviderFailure(
                    code="REQUIRES_API_KEY",
                    provider=self.name,
                    message="OpenAlex requires an API key to follow cursor pagination beyond the first page.",
                    occurred_at=utc_now(),
                    retryable=False,
                    attempt=1,
                    details={"environment_variable": "OPENALEX_API_KEY"},
                )
            )
        params: dict[str, str] = {
            "search": request.exact_query,
            "per_page": str(request.per_page),
            "cursor": active_cursor,
        }
        if request.filters:
            params["filter"] = ",".join(f"{key}:{value}" for key, value in request.filters.items())
        if request.sort:
            params["sort"] = request.sort
        url = f"{OPENALEX_BASE_URL}?{urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "ResearchReviewAgent/0.1.0.dev0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self.transport.get(provider=self.name, url=url, headers=headers)
        payload = _decode_payload(self.name, response)
        records = payload.get("results")
        meta = payload.get("meta", {})
        if not isinstance(records, list) or not isinstance(meta, dict):
            raise ProviderRequestError(
                ProviderFailure(
                    code="MALFORMED_RESPONSE",
                    provider=self.name,
                    message="OpenAlex response is missing a valid results list or meta object.",
                    occurred_at=utc_now(),
                    retryable=False,
                    attempt=1,
                    http_status=response.status,
                )
            )
        return FetchedPage(
            provider=self.name,
            body=response.body,
            payload=payload,
            records=[record for record in records if isinstance(record, dict)],
            request_url_redacted=url,
            request_parameters=dict(params),
            http_status=response.status,
            response_headers=_safe_headers(response.headers),
            retrieved_at=utc_now(),
            next_cursor=str(meta["next_cursor"]) if meta.get("next_cursor") is not None else None,
        )


class CrossrefAdapter:
    name = "crossref"

    def __init__(
        self,
        transport: HttpTransport | None = None,
        mailto: str | None = None,
        plus_token: str | None = None,
    ) -> None:
        self.transport = transport or HttpTransport()
        self.mailto = mailto if mailto is not None else os.environ.get("CROSSREF_MAILTO")
        self.plus_token = plus_token if plus_token is not None else os.environ.get("CROSSREF_PLUS_API_TOKEN")

    def _headers(self) -> dict[str, str]:
        agent = "ResearchReviewAgent/0.1.0.dev0"
        if self.mailto:
            agent += f" (mailto:{self.mailto})"
        headers = {"Accept": "application/json", "User-Agent": agent}
        if self.plus_token:
            headers["Crossref-Plus-API-Token"] = f"Bearer {self.plus_token}"
        return headers

    @staticmethod
    def _redacted_params(params: dict[str, str], mailto_configured: bool) -> dict[str, str]:
        redacted = dict(params)
        if "mailto" in redacted:
            redacted["mailto"] = "[configured]" if mailto_configured else "[not-configured]"
        return redacted

    def fetch_search_page(self, request: SearchRequest, cursor: str | None) -> FetchedPage:
        params: dict[str, str] = {
            "query.bibliographic": request.exact_query,
            "rows": str(request.per_page),
            "cursor": cursor or "*",
        }
        if request.filters:
            params["filter"] = ",".join(f"{key}:{value}" for key, value in request.filters.items())
        if request.sort:
            params["sort"] = request.sort
        if self.mailto:
            params["mailto"] = self.mailto
        url = f"{CROSSREF_BASE_URL}?{urlencode(params)}"
        response = self.transport.get(provider=self.name, url=url, headers=self._headers())
        payload = _decode_payload(self.name, response)
        message = payload.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("items"), list):
            raise ProviderRequestError(
                ProviderFailure(
                    code="MALFORMED_RESPONSE",
                    provider=self.name,
                    message="Crossref response is missing message.items.",
                    occurred_at=utc_now(),
                    retryable=False,
                    attempt=1,
                    http_status=response.status,
                )
            )
        redacted_params = self._redacted_params(params, bool(self.mailto))
        redacted_url = f"{CROSSREF_BASE_URL}?{urlencode(redacted_params)}"
        next_cursor = message.get("next-cursor")
        return FetchedPage(
            provider=self.name,
            body=response.body,
            payload=payload,
            records=[record for record in message["items"] if isinstance(record, dict)],
            request_url_redacted=redacted_url,
            request_parameters=redacted_params,
            http_status=response.status,
            response_headers=_safe_headers(response.headers),
            retrieved_at=utc_now(),
            next_cursor=str(next_cursor) if next_cursor is not None else None,
        )

    def fetch_doi(self, doi: str) -> FetchedPage:
        params: dict[str, str] = {}
        if self.mailto:
            params["mailto"] = self.mailto
        suffix = f"?{urlencode(params)}" if params else ""
        url = f"{CROSSREF_BASE_URL}/{quote(doi, safe='')}{suffix}"
        response = self.transport.get(provider=self.name, url=url, headers=self._headers())
        payload = _decode_payload(self.name, response)
        message = payload.get("message")
        if not isinstance(message, dict):
            raise ProviderRequestError(
                ProviderFailure(
                    code="MALFORMED_RESPONSE",
                    provider=self.name,
                    message="Crossref DOI response is missing a singleton message object.",
                    occurred_at=utc_now(),
                    retryable=False,
                    attempt=1,
                    http_status=response.status,
                )
            )
        redacted_params = self._redacted_params(params, bool(self.mailto))
        redacted_url = f"{CROSSREF_BASE_URL}/{quote(doi, safe='')}"
        if redacted_params:
            redacted_url += f"?{urlencode(redacted_params)}"
        return FetchedPage(
            provider=self.name,
            body=response.body,
            payload=payload,
            records=[message],
            request_url_redacted=redacted_url,
            request_parameters={"doi": doi, **redacted_params},
            http_status=response.status,
            response_headers=_safe_headers(response.headers),
            retrieved_at=utc_now(),
            next_cursor=None,
        )


def provider_configuration() -> dict[str, dict[str, Any]]:
    return {
        "opencitations": {
            "adapter_packaged": True,
            "network_required": True,
            "directions": ["backward", "forward"],
            "access_token_configured": bool(os.environ.get("OPENCITATIONS_ACCESS_TOKEN")),
            "access_token_environment_variable": "OPENCITATIONS_ACCESS_TOKEN",
            "token_required_by_adapter": False,
            "pagination": "unpaginated_index_v2",
        },
        "openalex": {
            "adapter_packaged": True,
            "network_required": True,
            "anonymous_first_page_supported": True,
            "cursor_pagination_requires_key": True,
            "api_key_configured": bool(os.environ.get("OPENALEX_API_KEY")),
            "api_key_environment_variable": "OPENALEX_API_KEY",
        },
        "crossref": {
            "adapter_packaged": True,
            "network_required": True,
            "public_access_supported": True,
            "mailto_configured": bool(os.environ.get("CROSSREF_MAILTO")),
            "mailto_environment_variable": "CROSSREF_MAILTO",
            "plus_token_configured": bool(os.environ.get("CROSSREF_PLUS_API_TOKEN")),
            "plus_token_environment_variable": "CROSSREF_PLUS_API_TOKEN",
        },
    }
