"""ERIC, arXiv Atom and current OpenAIRE JSON Graph v3 metadata search.

Native queries are passed unchanged. No full text, identity lookups or fallback APIs.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from .providers import _decode_payload
from .public_providers import malformed, page, xml_text
from .transport import HttpTransport

OPEN_PROVIDERS = {"eric", "arxiv", "openaire"}
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
SEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"


def arxiv_records(xml):
    if "<!ENTITY" in xml.upper() or "<!DOCTYPE" in xml.upper():
        malformed("arxiv", "XML declarations are not accepted.")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        malformed("arxiv", "Invalid Atom response.")
    if root.tag != ATOM + "feed":
        malformed("arxiv", "Expected an Atom feed, not an HTML error page.")
    records = []
    for entry in root.findall(ATOM + "entry"):
        url = xml_text(entry.find(ATOM + "id"))
        if "/api/errors" in url or xml_text(entry.find(ATOM + "title")) == "Error":
            malformed("arxiv", "Provider returned an Atom error entry.")
        identifier = url.split("/abs/", 1)[-1] if "/abs/" in url else ""
        records.append({"id": identifier, "url": url, "title": xml_text(entry.find(ATOM + "title")),
            "authors": [xml_text(a.find(ATOM + "name")) for a in entry.findall(ATOM + "author")],
            "published": xml_text(entry.find(ATOM + "published")),
            "updated": xml_text(entry.find(ATOM + "updated")),
            "abstract": xml_text(entry.find(ATOM + "summary")),
            "doi": xml_text(entry.find(ARXIV + "doi")),
            "journal_ref": xml_text(entry.find(ARXIV + "journal_ref")),
            "categories": [c.get("term") for c in entry.findall(ATOM + "category")],
            "version": (re.search(r"v(\d+)$", identifier).group(0) if re.search(r"v(\d+)$", identifier) else None)})
    try:
        total = int(xml_text(root.find(SEARCH + "totalResults")))
        start = int(xml_text(root.find(SEARCH + "startIndex")))
    except ValueError:
        malformed("arxiv", "Missing paging counts.")
    return records, str(start + len(records)) if records and start + len(records) < total else None


def open_records(provider, payload):
    if provider == "arxiv":
        if not isinstance(payload.get("arxiv_atom"), str):
            malformed(provider, "Replay requires the original Atom envelope.")
        return arxiv_records(payload["arxiv_atom"])
    if provider == "eric":
        container = payload.get("response") or {}
        rows = container.get("docs")
        start, total = container.get("start"), container.get("numFound")
        if not isinstance(start, int) or not isinstance(total, int):
            malformed(provider, "Missing ERIC paging counts.")
        following = start + len(rows) if isinstance(rows, list) else start
        cursor = str(following) if following < total else None
    elif provider == "openaire":
        container = payload.get("header") or {}
        rows = payload.get("results")
        start, size, total = container.get("page"), container.get("pageSize"), container.get("numFound")
        if not all(isinstance(v, int) for v in (start, size, total)) or start < 1 or size < 1:
            malformed(provider, "Missing Graph v3 page/header counts.")
        cursor = str(start + 1) if start * size < total else None
    else:
        raise ValueError("UNSUPPORTED_PROVIDER")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        malformed(provider, "Missing or malformed records; not a successful empty search.")
    return rows, cursor if rows else None


def bounded_page(provider, response, payload, params, url, limit, *, envelope=False):
    result = page(provider, response, payload, params, url, envelope=envelope)
    if len(result.records) > limit:
        malformed(provider, "Provider exceeded the requested page size; raw HTTP retained, no unapproved ingestion.")
    return result


class ERICAdapter:
    name = "eric"
    base_url = "https://api.ies.ed.gov/eric/"

    def __init__(self, transport=None):
        self.transport = transport or HttpTransport(max_attempts=1)

    def fetch_search_page(self, request, cursor):
        if request.filters or request.sort:
            raise ValueError("ERIC_USE_NATIVE_QUERY: fielded Boolean filters belong in exact_query")
        start = 0 if cursor in (None, "*") else int(cursor)
        if start < 0:
            raise ValueError("INVALID_ERIC_OFFSET")
        params = {"search": request.exact_query, "format": "json", "rows": str(request.per_page), "start": str(start)}
        url = self.base_url + "?" + urlencode(params)
        response = self.transport.get(provider=self.name, url=url, headers={"Accept": "application/json"})
        return bounded_page(self.name, response, _decode_payload(self.name, response), params, url, request.per_page)


class ArxivAdapter:
    name = "arxiv"
    base_url = "https://export.arxiv.org/api/query"

    def __init__(self, transport=None):
        self.transport = transport or HttpTransport(max_attempts=1)

    def fetch_search_page(self, request, cursor):
        if request.filters:
            raise ValueError("ARXIV_USE_NATIVE_QUERY: ti/abs/cat/au and Boolean syntax")
        start = 0 if cursor in (None, "*") else int(cursor)
        sort = (request.sort or "relevance descending").split()
        if start < 0 or start + request.per_page > 30000 or len(sort) != 2 or sort[0] not in {
                "relevance", "lastUpdatedDate", "submittedDate"} or sort[1] not in {"ascending", "descending"}:
            raise ValueError("INVALID_ARXIV_WINDOW_OR_SORT")
        params = {"search_query": request.exact_query, "start": str(start), "max_results": str(request.per_page),
                  "sortBy": sort[0], "sortOrder": sort[1]}
        url = self.base_url + "?" + urlencode(params)
        response = self.transport.get(provider=self.name, url=url,
            headers={"Accept": "application/atom+xml", "User-Agent": "ResearchReviewAgent/1.1 (metadata integration)"})
        payload = {"arxiv_atom": response.body.decode("utf-8"), "raw_format": "original_atom_envelope"}
        return bounded_page(self.name, response, payload, params, url, request.per_page, envelope=True)


class OpenAIREAdapter:
    name = "openaire"
    base_url = "https://api.openaire.eu/graph/v3/research-products"
    # A deliberately bounded subset of the documented v3 filter vocabulary.
    filters = {"type", "instanceType", "fromPublicationYear", "toPublicationYear", "publicationYear",
               "fromPublicationDate", "toPublicationDate", "mainTitle", "description", "pid", "authorFullName",
               "subjects", "language", "isPeerReviewed", "accessRightLabel"}

    def __init__(self, transport=None):
        self.transport = transport or HttpTransport(max_attempts=1)

    def fetch_search_page(self, request, cursor):
        number = 1 if cursor in (None, "*") else int(cursor)
        if set(request.filters) - self.filters or number < 1 or number * request.per_page > 10000:
            raise ValueError("UNSUPPORTED_OPENAIRE_FILTER_OR_OFFSET_WINDOW")
        sort = request.sort or "relevance DESC"
        if not re.fullmatch(r"(relevance|publicationDate|dateOfCollection|influence|popularity|citationCount|impulse) (ASC|DESC)", sort):
            raise ValueError("INVALID_OPENAIRE_SORT")
        params = {"search": request.exact_query, "page": str(number), "pageSize": str(request.per_page),
                  "sortBy": sort, **{k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in request.filters.items()}}
        url = self.base_url + "?" + urlencode(params)
        response = self.transport.get(provider=self.name, url=url, headers={"Accept": "application/json"})
        return bounded_page(self.name, response, _decode_payload(self.name, response), params, url, request.per_page)
