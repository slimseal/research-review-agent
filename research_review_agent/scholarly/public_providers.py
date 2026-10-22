"""Low-configuration metadata adapters; no full-text download or scientific inference."""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from ..state import utc_now
from .contracts import ProviderFailure
from .providers import FetchedPage, _decode_payload, _safe_headers
from .request_budget import redact_url
from .transport import HttpTransport, ProviderRequestError


def malformed(provider, message):
    raise ProviderRequestError(ProviderFailure("MALFORMED_RESPONSE", provider, message, utc_now(), False, 1))


def records_from_payload(provider, payload):
    if provider in {"eric", "arxiv", "openaire"}:
        from .open_providers import open_records
        return open_records(provider, payload)
    if provider == "europepmc":
        records = (payload.get("resultList") or {}).get("result")
        cursor = payload.get("nextCursorMark")
    elif provider == "semantic_scholar":
        records = payload.get("data")
        cursor = payload.get("next")
    elif provider == "pubmed":
        # Replay from the preserved upstream XML, not a cached parser projection.
        xml = payload.get("pubmed_xml")
        if not isinstance(xml, str):
            malformed(provider, "PubMed replay requires its original metadata XML envelope.")
        records = pubmed_records(xml) if xml else []
        cursor = payload.get("next_cursor")
    else:
        raise ValueError("UNSUPPORTED_PROVIDER")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        malformed(provider, "Missing or malformed record list; not a successful empty result.")
    return records, str(cursor) if cursor is not None and records else None


def page(provider, response, payload, params, url, *, envelope=False):
    records, cursor = records_from_payload(provider, payload)
    return FetchedPage(provider, json.dumps(payload, ensure_ascii=False).encode() if envelope else response.body,
                       payload, records, redact_url(url), params, response.status,
                       _safe_headers(response.headers), utc_now(), cursor)


class EuropePMCAdapter:
    name = "europepmc"
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, transport=None):
        self.transport = transport or HttpTransport()

    def fetch_search_page(self, request, cursor):
        if request.filters or request.sort:
            raise ValueError("EUROPEPMC_USE_REVIEWED_QUERY_SYNTAX: filters/sort belong in the exact query")
        params = {"query": request.exact_query, "format": "json", "resultType": "core",
                  "pageSize": str(request.per_page), "cursorMark": cursor or "*"}
        url = self.base_url + "?" + urlencode(params)
        response = self.transport.get(provider=self.name, url=url, headers={"Accept": "application/json"})
        payload = _decode_payload(self.name, response)
        return page(self.name, response, payload, params, url)


class SemanticScholarAdapter:
    name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, transport=None, api_key=None):
        self.transport = transport or HttpTransport()
        self.api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") if api_key is None else api_key

    def fetch_search_page(self, request, cursor):
        allowed = {"year", "fieldsOfStudy", "publicationTypes", "publicationDateOrYear"}
        if set(request.filters) - allowed or request.sort:
            raise ValueError("UNSUPPORTED_SEMANTIC_SCHOLAR_FILTER_OR_SORT")
        offset = 0 if cursor in (None, "*") else int(cursor)
        if offset < 0 or offset + request.per_page > 1000:
            raise ProviderRequestError(ProviderFailure("PROVIDER_RESULT_WINDOW", self.name,
                "Relevance search is bounded to the first 1000 results; no automatic bulk-search substitution.", utc_now(), False, 0))
        params = {"query": request.exact_query, "offset": str(offset), "limit": str(request.per_page),
                  "fields": "paperId,externalIds,title,authors,year,venue,abstract,url,publicationTypes", **request.filters}
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        url = self.base_url + "?" + urlencode(params)
        response = self.transport.get(provider=self.name, url=url, headers=headers)
        return page(self.name, response, _decode_payload(self.name, response), params, url)


def xml_text(element):
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def pubmed_records(xml):
    # ElementTree does not fetch external DTDs. Disallow internal entity declarations.
    if "<!ENTITY" in xml.upper():
        malformed("pubmed", "XML entity declarations are not accepted.")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        malformed("pubmed", "PubMed metadata XML cannot be parsed.")
    if root.tag != "PubmedArticleSet" or root.find(".//ERROR") is not None:
        malformed("pubmed", "PubMed returned an unexpected XML document.")
    records = []
    for item in root:
        citation = item.find("MedlineCitation") if item.tag == "PubmedArticle" else item.find("BookDocument")
        if citation is None:
            continue
        article = citation.find("Article") if item.tag == "PubmedArticle" else citation
        if article is None:
            continue
        # References may have ArticleIdList too. Only the article's own identity
        # container is authoritative; descendant-wide matching corrupts DOI/PMCID.
        id_path = "PubmedData/ArticleIdList/ArticleId" if item.tag == "PubmedArticle" else "BookDocument/ArticleIdList/ArticleId"
        identifiers = {node.get("IdType"): xml_text(node) for node in item.findall(id_path)}
        pmid = xml_text(citation.find("PMID"))
        title = xml_text(article.find("ArticleTitle"))
        authors = []
        for author in article.findall("AuthorList/Author"):
            name = xml_text(author.find("CollectiveName")) or " ".join(filter(None, [
                xml_text(author.find("ForeName")) or xml_text(author.find("Initials")), xml_text(author.find("LastName"))]))
            if name:
                authors.append(name)
        # Adjacent <Year>2026</Year><Month>Oct</Month> has no inter-tag whitespace.
        # Read the explicit year, not concatenated parent text ("2026Oct").
        date_node = article.find("Journal/JournalIssue/PubDate")
        if date_node is None:
            date_node = article.find("PubDate")
        date = (xml_text(date_node.find("Year")) or xml_text(date_node.find("MedlineDate"))) if date_node is not None else ""
        year = re.search(r"\b(1[6-9]\d{2}|20\d{2})\b", date)
        abstract = []
        for node in article.findall("Abstract/AbstractText"):
            abstract.append((node.get("Label", "") + ": " if node.get("Label") else "") + xml_text(node))
        records.append({"id": pmid, "title": title, "authors": authors,
                        "year": int(year.group()) if year else None,
                        "journal": xml_text(article.find("Journal/Title")) or xml_text(article.find("Book/BookTitle")),
                        "doi": identifiers.get("doi"), "pmcid": identifiers.get("pmc"),
                        "abstract": "\n".join(abstract) or None,
                        "publication_types": [xml_text(n) for n in article.findall("PublicationTypeList/PublicationType")]})
    return records


class PubMedAdapter:
    name = "pubmed"
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    def __init__(self, transport=None, api_key=None):
        self.transport = transport or HttpTransport()
        self.api_key = os.environ.get("NCBI_API_KEY") if api_key is None else api_key

    def fetch_search_page(self, request, cursor):
        if request.filters or request.sort:
            raise ValueError("PUBMED_USE_REVIEWED_QUERY_SYNTAX: no implicit filter translation")
        offset = 0 if cursor in (None, "*") else int(cursor)
        if offset < 0 or offset + request.per_page > 9999:
            raise ValueError("PUBMED_RESULT_WINDOW: split the reviewed query before exceeding 9999 IDs")
        params = {"db": "pubmed", "term": request.exact_query, "retmode": "json",
                  "retstart": str(offset), "retmax": str(request.per_page), "sort": "relevance",
                  "tool": "ResearchReviewAgent"}
        def get(endpoint, values):
            actual = {**values, **({"api_key": self.api_key} if self.api_key else {})}
            return self.transport.get(provider=self.name, url=self.base_url + endpoint + "?" + urlencode(actual),
                                      headers={"Accept": "application/json, application/xml"})
        search_response = get("esearch.fcgi", params)
        payload = _decode_payload(self.name, search_response)
        search = payload.get("esearchresult", {})
        ids = search.get("idlist")
        if not isinstance(ids, list) or not all(isinstance(i, str) and i.isdigit() for i in ids) or "ERROR" in payload or search.get("errorlist"):
            malformed(self.name, "PubMed ID search failed or returned invalid query/identifiers.")
        count = int(search["count"])
        xml = ""
        records = []
        fetch_params = None
        if ids:
            fetch_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": "ResearchReviewAgent"}
            fetched = get("efetch.fcgi", fetch_params)
            xml = fetched.body.decode("utf-8")
            records = pubmed_records(xml)
            if {r["id"] for r in records} != set(ids):
                malformed(self.name, "PubMed fetched IDs differ from the searched IDs; do not report a complete page.")
        next_cursor = str(offset + len(ids)) if ids and offset + len(ids) < count else None
        envelope = {"pubmed_search": payload, "pubmed_xml": xml, "records": records, "next_cursor": next_cursor}
        return page(self.name, search_response, envelope,
                    {"esearch": params, "efetch": fetch_params, "raw_format": "search_json_and_original_xml_envelope"},
                    self.base_url + "esearch.fcgi?" + urlencode(params), envelope=True)
