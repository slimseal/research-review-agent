"""Endpoint-scoped access policy. Configuration is never connectivity proof."""
from __future__ import annotations

import os
from typing import Any

from ..state import utc_now
from .contracts import SearchRequest
from .transport import ProviderRequestError


SEARCH_PROVIDERS = ("crossref", "openalex", "pubmed", "europepmc", "semantic_scholar", "eric", "arxiv", "openaire")
PAGE_LIMITS = dict(crossref=1000, openalex=100, pubmed=100, europepmc=1000, semantic_scholar=100,
                   eric=200, arxiv=2000, openaire=100)
CATALOG = {
    "eric": {"tier": "A", "key_env": None, "anonymous_search": True,
             "setup_url": "https://eric.ed.gov/?api"},
    "arxiv": {"tier": "A", "key_env": None, "anonymous_search": True,
              "setup_url": "https://info.arxiv.org/help/api/user-manual.html"},
    "openaire": {"tier": "A", "key_env": None, "anonymous_search": True,
                 "setup_url": "https://graph.openaire.eu/docs/apis/graph-api/overview/"},
    "core": {"tier": "A/B", "key_env": "CORE_API_KEY", "anonymous_search": True,
             "setup_url": "https://core.ac.uk/services/api"},
    "crossref": {"tier": "A", "key_env": "CROSSREF_PLUS_API_TOKEN", "anonymous_search": True,
                 "setup_url": "https://www.crossref.org/documentation/retrieve-metadata/rest-api/"},
    "openalex": {"tier": "A/B", "key_env": "OPENALEX_API_KEY", "anonymous_search": True,
                 "setup_url": "https://help.openalex.org/api/authentication/"},
    "pubmed": {"tier": "A/B", "key_env": "NCBI_API_KEY", "anonymous_search": True,
               "setup_url": "https://www.ncbi.nlm.nih.gov/books/NBK25497/"},
    "europepmc": {"tier": "A", "key_env": None, "anonymous_search": True,
                  "setup_url": "https://europepmc.org/RestfulWebService"},
    "semantic_scholar": {"tier": "A/B", "key_env": "SEMANTIC_SCHOLAR_API_KEY", "anonymous_search": True,
                         "setup_url": "https://www.semanticscholar.org/product/api"},
    "scopus": {"tier": "C", "key_env": "SCOPUS_API_KEY", "anonymous_search": False,
               "setup_url": "https://dev.elsevier.com/support.html"},
    "web_of_science": {"tier": "C", "key_env": "WOS_API_KEY", "anonymous_search": False,
                       "setup_url": "https://developer.clarivate.com/"},
    "psycinfo": {"tier": "C", "key_env": None, "anonymous_search": False,
                 "setup_url": "https://www.apa.org/pubs/psycinfoservices/request-form"},
    "cnki": {"tier": "C", "key_env": None, "anonymous_search": False,
             "setup_url": None},
}


def access_configuration() -> dict[str, dict[str, Any]]:
    result = {}
    for name, policy in CATALOG.items():
        implemented = name in SEARCH_PROVIDERS
        result[name] = {**policy, "adapter_packaged": implemented,
                        "key_configured": bool(os.environ.get(policy["key_env"])) if policy["key_env"] else False,
                        "status": "not_verified" if implemented else "not_implemented",
                        "verified": False, "network_requests": 0,
                        "access_requirement": "requires_institutional_access" if policy["tier"] == "C" else "public_or_optional_free_setup",
                        "operation": "metadata_search"}
    result["openalex"]["operations"] = {
        "search_first_page": "anonymous_or_key", "cursor_after_first": "key_required",
        "quota": "key_required; failure does not determine search availability"}
    return result


def failure_status(failure, *, key_configured: bool) -> str:
    code = failure.code
    detail = str(failure.details.get("provider_error_code", "")).casefold()
    if code == "REQUIRES_API_KEY":
        return "key_missing"
    if "key_not_activated" in detail or detail in {"invalid_api_key", "api_key_invalid"}:
        return "key_invalid"  # reason retains activation_pending, not permanent invalidity
    if code == "AUTHENTICATION_FAILED":
        return "key_invalid" if key_configured else "key_missing"
    if code == "ACCESS_FORBIDDEN":
        return "insufficient_entitlement"
    if code == "QUOTA_EXHAUSTED":
        return "quota_exhausted"
    if code == "HTTP_RATE_LIMITED":
        return "rate_limited"
    return "temporarily_unavailable"


def probe_provider(provider: str, transport, *, operation: str = "search", anonymous: bool = False) -> dict:
    """One explicitly authorized endpoint check; PubMed search includes metadata fetch."""
    from .providers import make_adapters, _decode_payload
    config = access_configuration().get(provider, {"status": "not_implemented", "adapter_packaged": False})
    result = {**config, "provider": provider, "operation": operation, "checked_at": utc_now(),
              "scope": "this endpoint and credential mode only", "verified": False}
    if provider not in SEARCH_PROVIDERS:
        return result
    key_env = CATALOG[provider]["key_env"]
    key = "" if anonymous else (os.environ.get(key_env, "") if key_env else "")
    result["credential_mode"] = "configured_key" if key else "anonymous"
    before = getattr(transport, "used", 0)
    try:
        if operation == "quota":
            if provider != "openalex":
                return {**result, "status": "not_implemented"}
            if not key:
                return {**result, "status": "key_missing", "network_requests": 0,
                        "reason": "Quota endpoint requires a key; anonymous search is independently supported."}
            response = transport.get(provider=provider, url="https://api.openalex.org/rate-limit",
                                     headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
            _decode_payload(provider, response)
        else:
            request = SearchRequest("ACCESS-PROBE", "none", "access-check", provider,
                                    "biodiversity", per_page=1, mode="access_probe")
            page = make_adapters(transport, anonymous=anonymous)[provider].fetch_search_page(request, "*")
            result["record_count"] = len(page.records)
        result.update(status="available", verified=True)
    except ProviderRequestError as exc:
        result.update(status=failure_status(exc.failure, key_configured=bool(key)),
                      error=exc.failure.to_dict())
    except (ValueError, KeyError, TypeError, UnicodeError):
        result.update(status="temporarily_unavailable", reason="Malformed or unsupported endpoint response; no availability claim.")
    result["network_requests"] = getattr(transport, "used", before) - before
    return result
