from __future__ import annotations

from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from .contracts import DocumentError
from .transport import SecureTransport, clean_url


class FullTextProvider(Protocol):
    name: str
    def discover(self, landing_url: str) -> dict: ...


class _PDFLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "meta" and (attr.get("name") or "").lower() == "citation_pdf_url" and attr.get("content"):
            self.links.append(attr["content"])
        if tag == "a" and attr.get("href") and (urlsplit(attr["href"]).path.lower().endswith(".pdf") or attr.get("type") == "application/pdf"):
            self.links.append(attr["href"])


class PublisherPageProvider:
    name = "publisher_page"

    def __init__(self, transport=None):
        self.transport = transport or SecureTransport(max_bytes=2 * 1024 * 1024)

    def discover(self, landing_url: str) -> dict:
        response = self.transport.get(landing_url)
        if response["mime_type"] == "application/pdf":
            links = [response["final_url"]]
        elif response["mime_type"] in {"text/html", "application/xhtml+xml"}:
            parser = _PDFLinks()
            parser.feed(response["data"].decode("utf-8", errors="replace"))
            links = list(dict.fromkeys(urljoin(response["final_url"], link) for link in parser.links))
        else:
            raise DocumentError("METADATA_ONLY", "Source is not a supported HTML publisher page or PDF.")
        candidates = []
        for link in links[:50]:
            try:
                candidates.append({"candidate_url": clean_url(link), "kind": "pdf_link", "access_decision": "unassessed"})
            except DocumentError:
                continue
        return {"response": response, "candidates": candidates, "status": "pdf_links_found" if candidates else "landing_page_no_pdf"}
