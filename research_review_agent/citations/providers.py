from __future__ import annotations

import json
import os
import re
from urllib.parse import quote, urlencode

from ..scholarly.normalization import normalize_doi
from ..scholarly.providers import CrossrefAdapter, OPENALEX_BASE_URL, _safe_headers
from ..scholarly.transport import HttpTransport, ProviderRequestError
from ..scholarly.contracts import ProviderFailure
from ..state import utc_now
from .contracts import SUPPORTED


def fail(code, message, provider):
    return ProviderRequestError(ProviderFailure(code, provider, message, utc_now(), False, 1))


def doi_tokens(value):
    # Multiple PIDs/DOIs are not collapsed: OC sometimes groups different versions.
    return sorted({d for token in re.findall(r"doi:(10\.\d{4,9}/[^\s;]+)", str(value), re.I)
                   if (d := normalize_doi(token))})


def reference_parts(ref, index):
    text = ref.get("unstructured", "") if isinstance(ref, dict) else str(ref)
    doi = normalize_doi(ref.get("DOI")) if isinstance(ref, dict) else None
    tokens = sorted({d for token in re.findall(r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/[^\s<>]+)", str(text), re.I)
                     if (d := normalize_doi(token))})
    if not doi and len(tokens) == 1:
        doi = tokens[0]
    valid = (isinstance(ref, str) and bool(ref.strip())) or (isinstance(ref, dict) and any(ref.get(k) for k in ("DOI", "unstructured", "article-title", "journal-title", "author", "volume-title", "series-title", "ISBN", "ISSN")))
    return {"raw": ref, "doi": doi, "provider_record_id": str(ref.get("key", index)) if isinstance(ref, dict) else str(index),
            "relation_valid": bool(valid), "metadata": None,
            "literal_parse": {"doi_tokens": tokens, "year_tokens": sorted(set(re.findall(r"\b(?:1[5-9]|20)\d{2}\b", str(text)))),
                              "note": "Literal tokens only; year candidates are not verified publication dates."}}


class CitationProviders:
    """One transport attempt per budget unit. No automatic provider fallback."""
    def __init__(self, transport=None):
        self.transport = transport or HttpTransport(timeout=25, max_attempts=1)
        self.crossref = CrossrefAdapter(transport=self.transport)

    def request(self, provider, direction, seed, cursor=None, per_page=25):
        if direction not in SUPPORTED.get(provider, set()):
            raise fail("PROVIDER_UNSUPPORTED", f"Unsupported {provider}/{direction}", provider)
        doi = normalize_doi(seed.get("doi"))
        headers = {"Accept": "application/json", "User-Agent": "ResearchReviewAgent/0.1.0.dev0"}
        if provider == "crossref":
            if not doi:
                raise fail("IDENTIFIER_MISSING", "Crossref references require a DOI.", provider)
            # Fetch bytes before parsing so malformed responses are also preserved.
            url = "https://api.crossref.org/v1/works/" + quote(doi, safe="")
            headers = self.crossref._headers()
            params = {"doi": doi}
        elif provider == "opencitations":
            if not doi:
                raise fail("IDENTIFIER_MISSING", "This OC adapter requires a DOI; other PIDs remain unresolved.", provider)
            op = "references" if direction == "backward" else "citations"
            url = "https://api.opencitations.net/index/v2/" + op + "/doi:" + quote(doi, safe="")
            params = {"doi": doi, "operation": op}
            if os.environ.get("OPENCITATIONS_ACCESS_TOKEN"):
                headers["authorization"] = os.environ["OPENCITATIONS_ACCESS_TOKEN"]
        else:
            key = os.environ.get("OPENALEX_API_KEY")
            if cursor and cursor != "*" and not key:
                raise fail("REQUIRES_API_KEY", "OpenAlex cursor continuation requires OPENALEX_API_KEY.", provider)
            ids = seed.get("provider_ids", {}).get("openalex", [])
            identifier = ids[0].rsplit("/", 1)[-1] if ids else ("https://doi.org/" + doi if doi else None)
            if not identifier:
                raise fail("IDENTIFIER_MISSING", "OpenAlex needs a work ID or DOI.", provider)
            params = {"filter": "cites:" + identifier, "per_page": str(per_page), "cursor": cursor or "*"}
            url = OPENALEX_BASE_URL + "?" + urlencode(params)
            if key:
                headers["Authorization"] = "Bearer " + key
        response = self.transport.get(provider=provider, url=url, headers=headers)
        return response.body, {"url": url, "parameters": params, "http_status": response.status,
                               "headers": _safe_headers(response.headers), "retrieved_at": utc_now()}

    def metadata(self, doi):
        url = "https://api.crossref.org/v1/works/" + quote(doi, safe="")
        response = self.transport.get(provider="crossref", url=url, headers=self.crossref._headers())
        return response.body, {"url": url, "parameters": {"doi": doi}, "http_status": response.status,
                               "headers": _safe_headers(response.headers), "retrieved_at": utc_now()}

    def openalex_identity(self, doi):
        url = OPENALEX_BASE_URL + "/" + quote("https://doi.org/" + doi, safe="")
        headers = {"Accept": "application/json", "User-Agent": "ResearchReviewAgent/0.1.0.dev0"}
        if os.environ.get("OPENALEX_API_KEY"):
            headers["Authorization"] = "Bearer " + os.environ["OPENALEX_API_KEY"]
        response = self.transport.get(provider="openalex", url=url, headers=headers)
        return response.body, {"url": url, "parameters": {"doi": doi}, "http_status": response.status,
                               "headers": _safe_headers(response.headers), "retrieved_at": utc_now()}


def parse_page(provider, direction, body, seed):
    """Return relations, next cursor, coverage. Never infer incoming from outgoing."""
    try:
        data = json.loads(body)
        if provider == "crossref":
            work = data["message"]
            if normalize_doi(work.get("DOI")) != normalize_doi(seed.get("doi")):
                raise ValueError("Seed DOI does not match response")
            if "reference" not in work:
                return [], None, "REFERENCE_LIST_UNAVAILABLE"
            refs = work["reference"]
            if not isinstance(refs, list):
                raise ValueError("reference must be a list")
            rows = [reference_parts(ref, index) for index, ref in enumerate(refs)]
            return rows, None, "DEPOSITED_REFERENCES_ONLY" if rows else "SUCCESS_EMPTY_INDEX_RESULT"
        if provider == "openalex":
            refs, meta = data["results"], data["meta"]
            if not isinstance(refs, list) or not isinstance(meta, dict):
                raise ValueError("Invalid results/meta")
            rows = [{"raw": ref, "doi": normalize_doi(ref.get("doi")) if isinstance(ref, dict) else None,
                     "provider_record_id": str(ref.get("id", index)) if isinstance(ref, dict) else str(index),
                     "relation_valid": isinstance(ref, dict) and bool(ref.get("id")), "metadata": ref}
                    for index, ref in enumerate(refs)]
            return rows, meta.get("next_cursor"), "FILTER_CITES_INDEX_ONLY" if rows else "SUCCESS_EMPTY_INDEX_RESULT"
        if not isinstance(data, list):
            raise ValueError("OpenCitations must return a list")
        rows = []
        for index, ref in enumerate(data):
            other = "cited" if direction == "backward" else "citing"
            origin = "citing" if direction == "backward" else "cited"
            dois = doi_tokens(ref.get(other, "")) if isinstance(ref, dict) else []
            valid = isinstance(ref, dict) and bool(str(ref.get(other) or "").strip()) and normalize_doi(seed.get("doi")) in doi_tokens(ref.get(origin, ""))
            rows.append({"raw": ref, "doi": dois[0] if len(dois) == 1 else None,
                         "provider_record_id": str(ref.get("oci", index)) if isinstance(ref, dict) else str(index),
                         "relation_valid": valid, "metadata": None, "external_ids": dois,
                         "identity_note": "ambiguous_multiple_dois" if len(dois) > 1 else "unresolved"})
        return rows, None, "OC_INDEX_ONLY_UNPAGINATED" if rows else "SUCCESS_EMPTY_INDEX_RESULT"
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise fail("MALFORMED_RESPONSE", str(exc), provider) from exc
