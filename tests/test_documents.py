from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from research_review_agent.documents.contracts import DocumentError
from research_review_agent.documents.parser import run_parser
from research_review_agent.documents.pipeline import DocumentPipeline, authorization_checked
from research_review_agent.documents.providers import PublisherPageProvider
from research_review_agent.documents.store import DocumentStore, initialize_lab, safe_path
from research_review_agent.documents.transport import SecureTransport, clean_url, public_addresses
from research_review_agent.project import approve_protocol, initialize_project
from research_review_agent.state import load_state, persist_state
from research_review_agent.workflow import evaluate_gates
from research_review_agent.validation import validate_phase
from tests.pdf_fixtures import pdf_bytes
from tests.helpers import fictional_registry_row, write_rows

AUTH = {"access_basis": "researcher_asserted_authorized", "asserted_by": "Synthetic fixture operator", "reason": "Generated synthetic software-validation fixture; not scientific evidence."}
CATALOG = [{"paper_id": "FICT001", "title": "Synthetic document identity", "authors": ["Fixture generator"], "year": 2099, "identity_source": "explicitly fictional software fixture", "example_data": True}]
HAS_PARSER = bool(importlib.util.find_spec("pypdf"))


class TransportTests(unittest.TestCase):
    def response(self, status=200, body=b"%PDF-1.4\nfixture", headers=None):
        response = MagicMock()
        response.status = status
        fields = {"Content-Type": "application/pdf", "Content-Length": str(len(body)), **(headers or {})}
        response.getheader.side_effect = lambda key, default=None: fields.get(key, default)
        response.read.side_effect = [body, b""]
        return response

    def fetch(self, response):
        with patch("research_review_agent.documents.transport.public_addresses", return_value=["8.8.8.8"]), patch("research_review_agent.documents.transport.PinnedHTTPS") as connection:
            connection.return_value.getresponse.return_value = response
            return SecureTransport().get("https://example.org/paper.pdf", pdf=True)

    def test_403_404_429_and_5xx_have_distinct_codes(self):
        for status, code in [(403, "ACCESS_FORBIDDEN"), (404, "FULLTEXT_NOT_FOUND"), (429, "HTTP_RATE_LIMITED"), (503, "HTTP_SERVER_ERROR")]:
            with self.subTest(status=status), self.assertRaisesRegex(DocumentError, code):
                self.fetch(self.response(status=status))

    def test_network_interruption(self):
        response = self.response()
        response.read.side_effect = ConnectionResetError()
        with self.assertRaisesRegex(DocumentError, "NETWORK_INTERRUPTED"):
            self.fetch(response)

    def test_timeout(self):
        response = self.response()
        response.read.side_effect = TimeoutError()
        with self.assertRaisesRegex(DocumentError, "TIMEOUT"):
            self.fetch(response)

    def test_malformed_pdf_and_html_response(self):
        for body, headers, code in [(b"html", {}, "INVALID_PDF_SIGNATURE"), (b"%PDF-1.4", {"Content-Type": "text/html"}, "NOT_PDF_CONTENT_TYPE")]:
            with self.subTest(code=code), self.assertRaisesRegex(DocumentError, code):
                self.fetch(self.response(body=body, headers=headers))

    def test_size_limits_for_declared_and_streaming_body(self):
        with self.assertRaisesRegex(DocumentError, "FILE_TOO_LARGE"):
            self.fetch(self.response(headers={"Content-Length": str(100 * 1024**2)}))
        with patch("research_review_agent.documents.transport.public_addresses", return_value=["8.8.8.8"]), patch("research_review_agent.documents.transport.PinnedHTTPS") as connection:
            connection.return_value.getresponse.return_value = self.response(body=b"%PDF-too-long", headers={"Content-Length": None})
            with self.assertRaisesRegex(DocumentError, "FILE_TOO_LARGE"):
                SecureTransport(max_bytes=8).get("https://example.org/a", pdf=True)

    def test_short_body_is_not_success(self):
        with self.assertRaisesRegex(DocumentError, "DOWNLOAD_INTERRUPTED"):
            self.fetch(self.response(headers={"Content-Length": "1000"}))

    def test_unsafe_url_credentials_and_traversal(self):
        for url in ["file:///etc/passwd", "http://example.org/p.pdf", "https://user:password@example.org/a", "https://example.org:8443/a", "https://example.org/%2e%2e/a", "https://example.org/a?api_key=secret"]:
            with self.subTest(url=url), self.assertRaises(DocumentError):
                clean_url(url)

    def test_private_and_mixed_dns_addresses_blocked(self):
        for addresses in [["127.0.0.1"], ["::1"], ["169.254.169.254"], ["224.0.0.1"], ["8.8.8.8", "10.0.0.1"]]:
            with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", (a, 443)) for a in addresses]), self.assertRaisesRegex(DocumentError, "UNSAFE_DESTINATION"):
                public_addresses("example.org")

    def test_unsafe_redirect_checked_before_second_connection(self):
        response = self.response(status=302, headers={"Location": "https://127.0.0.1/private"})
        with patch("research_review_agent.documents.transport.public_addresses", side_effect=[["8.8.8.8"], DocumentError("UNSAFE_DESTINATION", "blocked")]), patch("research_review_agent.documents.transport.PinnedHTTPS") as connection:
            connection.return_value.getresponse.return_value = response
            with self.assertRaisesRegex(DocumentError, "UNSAFE_DESTINATION"):
                SecureTransport().get("https://example.org/a")
            self.assertEqual(connection.call_count, 1)

    def test_pinned_tls_uses_validated_ip_and_hostname(self):
        from research_review_agent.documents.transport import PinnedHTTPS
        with patch("socket.create_connection") as connect, patch("ssl.create_default_context") as context:
            connection = PinnedHTTPS("example.org", "8.8.8.8", 3)
            connection.connect()
            connect.assert_called_once_with(("8.8.8.8", 443), 3)
            context.return_value.wrap_socket.assert_called_once_with(connect.return_value, server_hostname="example.org")

    def test_publisher_links_are_candidates_not_authorization(self):
        transport = MagicMock()
        transport.get.return_value = {"data": b'<meta name="citation_pdf_url" content="/paper.pdf"><a href="/landing">Landing</a>', "mime_type": "text/html", "final_url": "https://example.org/article"}
        result = PublisherPageProvider(transport).discover("https://example.org/article")
        self.assertEqual(result["candidates"], [{"candidate_url": "https://example.org/paper.pdf", "kind": "pdf_link", "access_decision": "unassessed"}])
        transport.get.return_value["data"] = b"<html>Metadata only, no PDF</html>"
        self.assertEqual(PublisherPageProvider(transport).discover("https://example.org/article")["status"], "landing_page_no_pdf")


@unittest.skipUnless(HAS_PARSER, "PDF integration requires the declared [pdf] extra")
class PDFIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "lab"
        initialize_lab(self.root, CATALOG)
        self.pipeline = DocumentPipeline(self.root)
        self.source = self.base / "authorized.pdf"
        self.source.write_bytes(pdf_bytes())

    def acquire(self, **kwargs):
        return self.pipeline.acquire(paper_id="FICT001", local=self.source, authorization=AUTH, **kwargs)

    def parsed(self):
        document = self.acquire()["document"]
        result = self.pipeline.parse(document["document_id"])
        self.assertEqual(result["status"], "parsed", result)
        parsed = json.loads((self.root / result["parse"]["path"]).read_text())
        return document, parsed

    def test_born_digital_integrity_text_and_original_preserved(self):
        original = self.source.read_bytes()
        document, parsed = self.parsed()
        self.assertEqual(parsed["page_count"], 1)
        self.assertIn("SYNTHETIC SOFTWARE TEST ONLY", parsed["pages"][0]["text"])
        self.assertEqual(document["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(document["acquisition_method"], "authorized_local_import")
        self.assertTrue(self.pipeline.validate()["valid"])

    def test_corrupt_pdf_is_failure_not_document(self):
        self.source.write_bytes(b"%PDF-1.4\ntruncated")
        result = self.acquire()
        self.assertEqual(result["error"]["code"], "PDF_CORRUPT")
        self.assertEqual(self.pipeline.store.load()["documents"], {})
        self.assertFalse(list((self.pipeline.store.base / "staging").glob("*.pdf")))

    def test_encrypted_pdf_no_decryption_attempt(self):
        self.source.write_bytes(pdf_bytes(encrypted=True))
        self.assertEqual(self.acquire()["error"]["code"], "PDF_ENCRYPTED")

    def test_image_only_requires_ocr_or_manual_no_substitute(self):
        self.source.write_bytes(pdf_bytes(scanned=True))
        doc = self.acquire()["document"]
        result = self.pipeline.parse(doc["document_id"])
        self.assertEqual(result["status"], "ocr_or_manual_required")
        parsed = json.loads((self.root / result["parse"]["path"]).read_text())
        self.assertEqual(parsed["pages"][0]["text"], "")

    def test_multicolumn_warning_actual_pdf(self):
        self.source.write_bytes(pdf_bytes(columns=True))
        _, parsed = self.parsed()
        self.assertIn("POSSIBLE_MULTI_COLUMN_OR_POSITIONED_TEXT", parsed["pages"][0]["warnings"])
        self.assertEqual(parsed["reading_order_confidence"], "unverified")

    def test_printed_page_different_from_pdf_index_not_inferred(self):
        self.source.write_bytes(pdf_bytes(printed_label=True))
        _, parsed = self.parsed()
        page = parsed["pages"][0]
        self.assertEqual(page["pdf_page"], 1)
        self.assertEqual(page["pdf_page_label"], "41")
        self.assertIsNone(page["printed_page"])

    def test_identical_import_idempotent_different_versions_preserved(self):
        first = self.acquire(version_kind="preprint")["document"]
        duplicate = self.acquire(version_kind="preprint")
        self.assertEqual(duplicate["status"], "duplicate_content")
        self.assertEqual(duplicate["document"]["document_id"], first["document_id"])
        self.source.write_bytes(pdf_bytes(text="SYNTHETIC SECOND VERSION"))
        second = self.acquire(version_kind="version_of_record")["document"]
        self.assertNotEqual(second["document_id"], first["document_id"])
        self.assertEqual(second["paper_id"], first["paper_id"])
        self.assertIn(first["document_id"], second["related_document_ids"])

    def test_anchor_round_trip_readonly_and_human_confirmation(self):
        document, _ = self.parsed()
        anchor = self.pipeline.anchor(document["document_id"], "SYNTHETIC SOFTWARE TEST ONLY", pdf_page=1)
        before = self.pipeline.store.path.read_bytes()
        result = self.pipeline.lookup(anchor["anchor_id"])
        self.assertEqual(result["effective_status"], "machine_located")
        self.assertEqual(result["resolved_pdf_page"], 1)
        self.assertEqual(result["resolved_text"], "SYNTHETIC SOFTWARE TEST ONLY")
        self.assertTrue(Path(result["resolved_pdf"]).exists())
        self.assertEqual(self.pipeline.store.path.read_bytes(), before)
        confirmed = self.pipeline.confirm(anchor["anchor_id"], "Synthetic test human", "Synthetic confirmation, not a real human inspection", printed_page="41")
        self.assertEqual(confirmed["verification_status"], "human_confirmed")

    def test_invalid_unresolved_and_ambiguous_anchors(self):
        self.source.write_bytes(pdf_bytes(text="REPEATED REPEATED"))
        document, _ = self.parsed()
        with self.assertRaisesRegex(DocumentError, "INVALID_PDF_PAGE"):
            self.pipeline.anchor(document["document_id"], "REPEATED", pdf_page=2)
        with self.assertRaisesRegex(DocumentError, "INVALID_SPAN"):
            self.pipeline.anchor(document["document_id"], "REPEATED", pdf_page=1, start=1, end=3)
        self.assertEqual(self.pipeline.anchor(document["document_id"], "NOT IN FILE")["verification_status"], "unresolved")
        self.assertEqual(self.pipeline.anchor(document["document_id"], "REPEATED")["verification_status"], "ambiguous")
        anchor = self.pipeline.anchor(document["document_id"], "REPEATED", pdf_page=1, start=0, end=8)
        self.assertEqual(anchor["verification_status"], "machine_located")

    def test_document_checksum_change_invalidates_anchor(self):
        document, _ = self.parsed()
        anchor = self.pipeline.anchor(document["document_id"], "SYNTHETIC SOFTWARE TEST ONLY")
        (self.root / document["local_path"]).write_bytes(pdf_bytes(text="REPLACED CONTENT"))
        self.assertEqual(self.pipeline.lookup(anchor["anchor_id"])["effective_status"], "stale")
        self.assertEqual(self.pipeline.parse(document["document_id"])["error"]["code"], "DOCUMENT_CHECKSUM_MISMATCH")
        self.assertFalse(self.pipeline.validate()["valid"])

    def test_parser_version_change_and_artifact_change_invalidate(self):
        document, _ = self.parsed()
        anchor = self.pipeline.anchor(document["document_id"], "SYNTHETIC SOFTWARE TEST ONLY")
        with patch("research_review_agent.documents.pipeline.parser_version", return_value="future-parser"):
            self.assertEqual(self.pipeline.lookup(anchor["anchor_id"])["effective_status"], "stale")
        (self.root / anchor["parse_path"]).write_text("{}")
        self.assertEqual(self.pipeline.lookup(anchor["anchor_id"])["effective_status"], "stale")

    def test_unknown_license_not_redistributable(self):
        document = self.acquire()["document"]
        self.assertEqual(document["license_status"], "unknown")
        self.assertEqual(document["redistribution_permission"], "unknown")
        with self.assertRaisesRegex(DocumentError, "REDISTRIBUTION_BASIS_REQUIRED"):
            authorization_checked({**AUTH, "redistribution_permission": "permitted_with_conditions"}, remote=False)

    def test_missing_id_and_explicit_unresolved_identity(self):
        result = self.pipeline.acquire(paper_id="ABSENT", local=self.source, authorization=AUTH)
        self.assertEqual(result["error"]["code"], "MISSING_PAPER_ID")
        result = self.pipeline.acquire(local=self.source, authorization=AUTH, unresolved=True)
        self.assertIsNone(result["document"]["paper_id"])
        self.assertEqual(result["document"]["identity_status"], "unresolved")

    def test_unauthorized_download_blocked_before_network(self):
        self.pipeline.transport = MagicMock()
        result = self.pipeline.acquire(paper_id="FICT001", candidate_id="anything", authorization={})
        self.assertEqual(result["error"]["code"], "ACCESS_NOT_AUTHORIZED")
        self.pipeline.transport.get.assert_not_called()

    def test_mocked_discovery_and_remote_acquisition_real_pdf_parser(self):
        body = self.source.read_bytes()
        html = b'<meta name="citation_pdf_url" content="https://example.org/paper.pdf">'
        self.pipeline.transport = MagicMock()
        self.pipeline.transport.get.return_value = {"data": html, "mime_type": "text/html", "final_url": "https://example.org/article", "redirects": [], "http_status": 200, "sha256": hashlib.sha256(html).hexdigest()}
        candidate = self.pipeline.discover("FICT001", "https://example.org/article")["candidates"][0]
        self.pipeline.transport.get.return_value = {"data": body, "mime_type": "application/pdf", "final_url": "https://example.org/paper.pdf", "redirects": [], "http_status": 200}
        result = self.pipeline.acquire(paper_id="FICT001", candidate_id=candidate["candidate_id"], authorization=AUTH)
        self.assertEqual(result["status"], "acquired")
        self.assertEqual(result["document"]["source_url"], "https://example.org/paper.pdf")
        attempt = self.pipeline.store.load()["attempts"][result["attempt_id"]]
        self.assertEqual(attempt["http_status"], 200)
        self.assertEqual(attempt["downloaded_bytes"], len(body))

    def test_parser_failure_logged_without_claiming_success(self):
        document = self.acquire()["document"]
        with patch("research_review_agent.documents.pipeline.run_parser", side_effect=DocumentError("PARSER_FAILED", "synthetic failure")):
            result = self.pipeline.parse(document["document_id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.pipeline.store.load()["documents"][document["document_id"]]["parsing_status"], "failed")

    def test_recovery_and_parse_replay(self):
        document, _ = self.parsed()
        result = self.pipeline.parse(document["document_id"])
        self.assertEqual(result["status"], "replayed")
        self.pipeline.store.path.write_text("corrupt manifest")
        self.assertEqual(self.pipeline.store.recover()["status"], "recovered")
        self.assertTrue(self.pipeline.validate()["valid"])
        self.assertEqual(self.acquire()["status"], "duplicate_content")

    def test_legacy_paper_identity_is_readonly_and_doi_optional(self):
        root = self.base / "official"
        initialize_project(root, "Synthetic question", "test")
        write_rows(root / "03_library/PAPER_REGISTRY.csv", "paper_registry", [fictional_registry_row()], legacy=True)
        pipeline = DocumentPipeline(root)
        before = (root / "03_library/PAPER_REGISTRY.csv").read_bytes()
        self.assertEqual(pipeline.store.paper_ids(), {"FICT001"})
        # Mock gate only here to test legacy storage compatibility, not gate behavior.
        with patch.object(pipeline, "guard"):
            result = pipeline.acquire(paper_id="FICT001", local=self.source, authorization=AUTH)
        self.assertEqual(result["status"], "imported_manually")
        self.assertEqual((root / "03_library/PAPER_REGISTRY.csv").read_bytes(), before)

    def test_parser_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pdf_worker", 45)), self.assertRaisesRegex(DocumentError, "PARSER_TIMEOUT"):
            run_parser(self.source, extract=True)


class WorkflowAndPortabilityTests(unittest.TestCase):
    def test_machine_readable_contract_types_and_status_validation(self):
        from research_review_agent.documents.contracts import AcquisitionAttempt, document_schema, validate_contract
        attempt = AcquisitionAttempt("TEST", None, "synthetic", None, "2099-01-01").to_dict()
        validate_contract("AcquisitionAttempt", attempt)
        attempt["downloaded_bytes"] = "not a number"
        with self.assertRaisesRegex(DocumentError, "INVALID_DOCUMENT_CONTRACT"):
            validate_contract("AcquisitionAttempt", attempt)
        self.assertEqual(len(document_schema()["$defs"]), 4)

    def test_unapproved_protocol_blocks_official_document_operation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "review"
            initialize_project(root, "Synthetic workflow protection question", "test")
            before = load_state(root)
            pipeline = DocumentPipeline(root)
            with self.assertRaisesRegex(DocumentError, "PROTOCOL_NOT_APPROVED"):
                pipeline.acquire(paper_id="missing", local=Path("absent.pdf"), authorization=AUTH)
            self.assertEqual(load_state(root), before)
            self.assertEqual(before["phases"]["4"]["status"], "pending")
            with self.assertRaisesRegex(DocumentError, "LAB_ISOLATION_REQUIRED"):
                initialize_lab(root / "lab", CATALOG)

    def test_phase4_and_gate1_enforced_even_with_approved_protocol(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "review"
            initialize_project(root, "Synthetic gate question", "test", Path(__file__).resolve().parents[1] / "examples/configs/education.json")
            approve_protocol(root, "synthetic-test-reviewer")
            pipeline = DocumentPipeline(root)
            state = load_state(root)
            for phase in (1, 2, 3):
                state["phases"][str(phase)]["status"] = "completed"
            persist_state(root, state, "synthetic_test_only")
            gates = evaluate_gates(root, 5)
            self.assertEqual(gates["protocol-approved"]["status"], "pass")
            self.assertIn("[4]", gates["phase-prerequisites"]["message"])
            self.assertEqual(evaluate_gates(root, 7)["gate-1-screening-before-reading"]["status"], "fail")
            for phase in (5, 7):
                with self.subTest(phase=phase), self.assertRaisesRegex(DocumentError, "WORKFLOW_GATE_BLOCKED"):
                    pipeline.guard(phase)
            self.assertEqual(load_state(root)["phases"]["4"]["status"], "pending")

    def test_metadata_or_acquisition_alone_does_not_complete_phase5(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "review"
            initialize_project(root, "Synthetic phase5 check", "test")
            write_rows(root / "03_library/PAPER_REGISTRY.csv", "paper_registry", [fictional_registry_row()])
            (root / "03_library/references.bib").write_text("% synthetic fixture")
            codes = {i.code for i in validate_phase(root, 5, allow_example_data=True)}
            self.assertIn("acquisition_review_required", codes)

    def test_unsafe_managed_path(self):
        with self.assertRaisesRegex(DocumentError, "UNSAFE_PATH"):
            safe_path(Path("/tmp/lab"), "../../escape.pdf")

    def test_missing_parser_actionable_error(self):
        from importlib.metadata import PackageNotFoundError
        from research_review_agent.documents.parser import parser_version
        with patch("importlib.metadata.version", side_effect=PackageNotFoundError()), self.assertRaisesRegex(DocumentError, "PARSER_UNAVAILABLE"):
            parser_version()

    def test_recover_started_operation_marks_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            initialize_lab(root, CATALOG)
            store = DocumentStore(root)
            with store.lock():
                data = store.load()
                data["attempts"]["interrupted"] = {"result_status": "started"}
                store.commit(data, "synthetic_interruption")
            store.recover()
            self.assertEqual(store.load()["attempts"]["interrupted"]["result_status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
