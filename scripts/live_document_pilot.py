#!/usr/bin/env python3
"""Explicit, isolated two-document infrastructure pilot. No scientific interpretation."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_review_agent.documents.pipeline import DocumentPipeline
from research_review_agent.documents.store import atomic_blob, initialize_lab
from research_review_agent.documents.transport import SecureTransport
from research_review_agent.state import utc_now, write_json_atomic

SOURCES = ["https://joss.theoj.org/papers/10.21105/joss.01686", "https://joss.theoj.org/papers/10.21105/joss.03021"]


class CitationMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("name", "").startswith("citation_"):
            self.meta.setdefault(values["name"], []).append(values.get("content"))


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--output", required=True, type=Path)
    options = args.parse_args()
    output = options.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Pilot requires a new empty directory; do not overwrite existing trials.")
    transport = SecureTransport()
    metadata, source_responses = [], []
    for index, url in enumerate(SOURCES, 1):
        response = transport.get(url)
        parser = CitationMetadata()
        parser.feed(response["data"].decode())
        fields = parser.meta
        doi = fields["citation_doi"][0]
        if not url.endswith(doi):
            raise ValueError("Publisher DOI metadata does not match the requested article.")
        metadata.append({"paper_id": f"PILOT{index:03d}", "title": fields["citation_title"][0], "authors": fields["citation_author"], "year": int(fields["citation_publication_date"][0][:4]), "doi": doi, "identity_source": url, "metadata_sha256": response["sha256"], "example_data": False, "purpose": "document infrastructure test, not a research review"})
        source_responses.append(response)
    initialize_lab(output, metadata)
    policy = transport.get("https://joss.theoj.org/about")
    atomic_blob(output / "identity_sources" / "publisher_rights.html", policy["data"])
    pipeline = DocumentPipeline(output)
    manifest = {"pilot_type": "real_document_infrastructure_only", "executed_at": utc_now(), "official_project": False, "phase_changes": False, "scientific_evidence_rows": 0, "sources": []}
    for paper, response in zip(metadata, source_responses):
        atomic_blob(output / "identity_sources" / f"{paper['paper_id']}.html", response["data"])
        discovery = pipeline.discover(paper["paper_id"], paper["identity_source"])
        record = {"identity": paper, "discovery": discovery}
        manifest["sources"].append(record)
        write_json_atomic(output / "PILOT_MANIFEST.json", manifest)
        if not discovery.get("candidates"):
            continue
        auth = {"access_basis": "publisher_open_access", "asserted_by": "Codex pilot operator under user-authorized Round 2D", "reason": "Article landing page and publisher policy explicitly identify CC BY 4.0. This is a recorded source-based assertion, not legal advice or independent legal verification.", "rights_url": paper["identity_source"], "license_status": "open_license_asserted", "license_url": "https://creativecommons.org/licenses/by/4.0/", "redistribution_permission": "permitted_with_conditions"}
        result = pipeline.acquire(paper_id=paper["paper_id"], candidate_id=discovery["candidates"][0]["candidate_id"], authorization=auth, version_kind="version_of_record")
        record["acquisition"] = result
        write_json_atomic(output / "PILOT_MANIFEST.json", manifest)
        if "document" not in result:
            continue
        document = result["document"]
        parsed_result = pipeline.parse(document["document_id"])
        record["parsing"] = parsed_result
        if "parse" not in parsed_result:
            continue
        parsed = json.loads((output / parsed_result["parse"]["path"]).read_text())
        record["identity_check"] = {"publisher_metadata_doi_matches_requested": True, "doi_present_on_pdf_page_1": paper["doi"] in parsed["pages"][0]["text"], "title_check": "requires_visual_confirmation"}
        record["anchors"] = []
        # Actual nonempty extracted text only; no inferred page/quote or scientific claims.
        for page in parsed["pages"][:3]:
            quote = next((line.strip() for line in page["text"].splitlines() if len(line.strip()) >= 12), "")
            if not quote:
                continue
            anchor = pipeline.anchor(document["document_id"], quote, pdf_page=page["pdf_page"])
            resolved = pipeline.lookup(anchor["anchor_id"])
            record["anchors"].append({"anchor_id": anchor["anchor_id"], "pdf_page": anchor["pdf_page"], "quote_fingerprint": anchor["quote_fingerprint"], "effective_status": resolved["effective_status"], "visual_check": "pending"})
        write_json_atomic(output / "PILOT_MANIFEST.json", manifest)
    manifest["validation"] = pipeline.validate()
    write_json_atomic(output / "PILOT_MANIFEST.json", manifest)
    print(json.dumps({"output": str(output), "records": [{"paper_id": r["identity"]["paper_id"], "acquisition": r.get("acquisition", {}).get("status"), "parsing": r.get("parsing", {}).get("status"), "anchors": r.get("anchors", [])} for r in manifest["sources"]], "validation": manifest["validation"]}, indent=2))
    return 0 if len(manifest["sources"]) == 2 and all(r.get("parsing", {}).get("status") == "parsed" for r in manifest["sources"]) and manifest["validation"]["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
