"""Isolated synthetic transport tests; never a real connection or scientific approval."""
import io
import json
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from research_review_agent.scholarly.access import access_configuration, failure_status, probe_provider
from research_review_agent.scholarly.contracts import ProviderFailure, SearchRequest
from research_review_agent.scholarly.normalization import normalize_provider_records
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline
from research_review_agent.scholarly.providers import make_adapters
from research_review_agent.scholarly.public_providers import pubmed_records
from research_review_agent.scholarly.request_budget import RecordedTransport
from research_review_agent.scholarly.source_plan import source_plan, coverage_report
from research_review_agent.scholarly.transport import ProviderRequestError
from research_review_agent.screening.pipeline import ScreeningPipeline


XML = '''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123456</PMID><Article>
<ArticleTitle>Fictional shared study</ArticleTitle><Journal><Title>Fictional Journal</Title>
<JournalIssue><PubDate><Year>2099</Year></PubDate></JournalIssue></Journal>
<AuthorList><Author><ForeName>A</ForeName><LastName>Tester</LastName></Author></AuthorList>
<Abstract><AbstractText Label="RESULTS">Fictional null result.</AbstractText></Abstract>
<PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.5555/fictional</ArticleId>
</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>'''
EUROPE = {"hitCount": 1, "resultList": {"result": [{"id": "123456", "source": "MED", "pmid": "123456",
    "title": "Fictional shared study", "doi": "10.5555/fictional", "pubYear": "2099",
    "authorList": {"author": [{"fullName": "A Tester"}]}, "abstractText": "Fictional null result."}]}}
SEMANTIC = {"total": 1, "data": [{"paperId": "FICTIONAL-S2", "title": "Fictional shared study", "year": 2099,
    "authors": [{"name": "A Tester"}], "externalIds": {"DOI": "10.5555/fictional", "PubMed": "123456"},
    "abstract": "Fictional null result."}]}


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, body):
        super().__init__(body if isinstance(body, bytes) else json.dumps(body).encode())


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def transport(self, bodies, budget=4, attempts=1, name="http"):
        self.calls = []
        queue = list(bodies)
        def opener(request, **kwargs):
            self.calls.append(request)
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return Response(item)
        return RecordedTransport(self.root / name, max_requests=budget, max_attempts=attempts,
                                 opener=opener, sleep=lambda _: None)

    def request(self, provider):
        return SearchRequest("FICTIONAL", "fixture", "fixture", provider, "fictional", per_page=1)

    def test_configuration_never_claims_verified_or_exposes_keys(self):
        with patch.dict("os.environ", {"OPENALEX_API_KEY": "test-private-secret"}):
            value = access_configuration()
        self.assertNotIn("test-private-secret", json.dumps(value))
        self.assertEqual(value["openalex"]["status"], "not_verified")
        self.assertEqual(value["scopus"]["status"], "not_implemented")
        self.assertEqual(value["psycinfo"]["access_requirement"], "requires_institutional_access")

    def test_all_required_failure_states(self):
        for code, status, configured in [("REQUIRES_API_KEY", "key_missing", False),
            ("AUTHENTICATION_FAILED", "key_invalid", True), ("AUTHENTICATION_FAILED", "key_missing", False),
            ("ACCESS_FORBIDDEN", "insufficient_entitlement", True), ("QUOTA_EXHAUSTED", "quota_exhausted", True),
            ("HTTP_RATE_LIMITED", "rate_limited", False), ("TIMEOUT", "temporarily_unavailable", False)]:
            self.assertEqual(failure_status(ProviderFailure(code, "fixture", "fixture", "now", False, 1),
                                           key_configured=configured), status)

    def test_quota_missing_does_not_probe_or_block_anonymous_search(self):
        transport = self.transport([{"results": [], "meta": {}}], budget=1)
        missing = probe_provider("openalex", transport, operation="quota", anonymous=True)
        self.assertEqual(missing["status"], "key_missing")
        self.assertEqual(transport.used, 0)
        ok = probe_provider("openalex", transport, anonymous=True)
        self.assertEqual(ok["status"], "available")
        self.assertTrue(ok["verified"])

    def test_quota_401_does_not_change_search_access(self):
        failure = urllib.error.HTTPError("https://fixture.invalid", 401, "Denied", {}, io.BytesIO(b'{}'))
        transport = self.transport([failure, {"results": [], "meta": {}}], budget=2)
        with patch.dict("os.environ", {"OPENALEX_API_KEY": "fixture-key"}):
            result = probe_provider("openalex", transport, operation="quota")
        self.assertEqual(result["status"], "key_invalid")
        self.assertEqual(probe_provider("openalex", transport, anonymous=True)["status"], "available")

    def test_budget_counts_retry_and_reopen(self):
        failure = urllib.error.HTTPError("https://fixture.invalid", 429, "Limited", {}, io.BytesIO(b'{}'))
        transport = self.transport([failure, {}], budget=2, attempts=2)
        transport.get(provider="fixture", url="https://fixture.invalid", headers={})
        self.assertEqual(transport.used, 2)
        again = RecordedTransport(self.root / "http", max_requests=2, max_attempts=2, sleep=lambda _: None)
        with self.assertRaises(ProviderRequestError) as ctx:
            again.get(provider="fixture", url="https://fixture.invalid", headers={})
        self.assertEqual(ctx.exception.failure.code, "REQUEST_BUDGET_EXHAUSTED")
        self.assertEqual(len(self.calls), 2)

    def test_budget_conflict(self):
        self.transport([], budget=1)
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            RecordedTransport(self.root / "http", max_requests=2)

    def test_received_raw_tamper_detected(self):
        transport = self.transport([{}], budget=1)
        transport.get(provider="fixture", url="https://fixture.invalid", headers={})
        self.assertEqual(transport.validate(), [])
        (self.root / "http/response-000001.bin").write_bytes(b"tampered")
        self.assertIn("HTTP_RAW_CHECKSUM_MISMATCH", transport.validate())

    def test_plan_accepts_only_recent_search_observations(self):
        from research_review_agent.state import utc_now
        observation = {"provider": "crossref", "status": "available", "verified": True,
                       "checked_at": utc_now(), "operation": "search"}
        result = source_plan("fixture", include=["crossref"], access_report=observation)
        self.assertEqual(result["sources"][0]["category"], "Recommended and available")
        for modified in ({**observation, "operation": "quota"}, {**observation, "checked_at": "2000-01-01T00:00:00+00:00"}):
            result = source_plan("fixture", include=["crossref"], access_report=modified)
            self.assertEqual(result["sources"][0]["category"], "Not implemented or not verified")

    def test_timeout_never_blind_retries(self):
        transport = self.transport([TimeoutError()], budget=2, attempts=2)
        with self.assertRaises(ProviderRequestError):
            transport.get(provider="fixture", url="https://fixture.invalid", headers={})
        self.assertEqual(transport.used, 1)
        with self.assertRaisesRegex(ValueError, "SEND_UNCERTAIN"):
            RecordedTransport(self.root / "http", max_requests=2, max_attempts=2)

    def test_interrupted_receipt_and_lock_are_not_ignored(self):
        transport = self.transport([KeyboardInterrupt()], budget=2)
        with self.assertRaises(KeyboardInterrupt):
            transport.get(provider="fixture", url="https://fixture.invalid", headers={})
        with self.assertRaisesRegex(ValueError, "SEND_UNCERTAIN"):
            RecordedTransport(self.root / "http", max_requests=2)
        (self.root / "http/active.lock").touch()
        with self.assertRaisesRegex(ValueError, "OPERATION_CONFLICT"):
            transport.get(provider="fixture", url="https://fixture.invalid", headers={})

    def test_redirect_is_not_followed(self):
        from research_review_agent.scholarly.request_budget import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.invalid"))
        failure = urllib.error.HTTPError("https://fixture.invalid", 302, "Redirect", {}, io.BytesIO(b''))
        transport = self.transport([failure], budget=1)
        with self.assertRaises(ProviderRequestError):
            transport.get(provider="fixture", url="https://fixture.invalid", headers={})
        self.assertEqual(len(self.calls), 1)

    def test_secrets_not_written_and_echo_rejected(self):
        transport = self.transport([{}], budget=1)
        transport.get(provider="fixture", url="https://fixture.invalid?api_key=secret123&email=private@example.invalid", headers={"x-api-key": "secret456"})
        saved = (self.root / "http/budget.json").read_text()
        self.assertNotIn("secret123", saved)
        self.assertNotIn("private@example.invalid", saved)
        transport = self.transport([{"message": "secret123"}], budget=1, name="echo")
        with self.assertRaisesRegex(ProviderRequestError, "SENSITIVE_RESPONSE_REJECTED"):
            transport.get(provider="fixture", url="https://fixture.invalid?api_key=secret123", headers={})
        self.assertFalse(list((self.root / "echo").glob("*.bin")))

    def test_new_providers_dedup_replay_and_abstract_provenance(self):
        transport = self.transport([EUROPE, SEMANTIC,
            {"esearchresult": {"count": "1", "idlist": ["123456"]}}, XML.encode()], budget=4)
        pipeline = ScholarlyDiscoveryPipeline(self.root / "fixture", adapters=make_adapters(transport, anonymous=True), enforce_workflow=False)
        runs = [pipeline.run_search(self.request(p)) for p in ("europepmc", "semantic_scholar", "pubmed")]
        self.assertEqual([r.retrieval_status for r in runs], ["complete"] * 3)
        self.assertEqual(len(pipeline.registry.data["records"]), 1)
        self.assertEqual(sum(r.duplicate_count for r in runs), 2)
        report = coverage_report(self.root / "fixture")
        self.assertIsNone(report["providers"]["pubmed"]["runs"][0]["http_attempts"])
        replay = pipeline.replay(runs[-1].search_run_id)
        self.assertEqual(replay.retrieval_status, "replayed")
        self.assertEqual(transport.used, 4)
        # Read-only substrate check, not a Phase 6 approval or screening execution.
        reader = object.__new__(ScreeningPipeline)
        reader.root, reader.registry = self.root / "fixture", pipeline.registry
        pid = next(iter(pipeline.registry.data["records"]))
        abstract = reader.abstract(pid)
        self.assertIn("Fictional null result", abstract["text"])
        self.assertTrue(abstract["raw_sha256"])

    def test_pubmed_subrequest_budget_failure_not_empty_success(self):
        transport = self.transport([{"esearchresult": {"count": "1", "idlist": ["123456"]}}], budget=1)
        pipeline = ScholarlyDiscoveryPipeline(self.root / "fixture", adapters=make_adapters(transport, anonymous=True), enforce_workflow=False)
        run = pipeline.run_search(self.request("pubmed"))
        self.assertEqual(run.retrieval_status, "failed")
        self.assertEqual(run.errors[0]["code"], "REQUEST_BUDGET_EXHAUSTED")
        self.assertEqual(transport.used, 1)

    def test_missing_or_malformed_responses_not_empty(self):
        for provider in ("pubmed", "europepmc", "semantic_scholar"):
            transport = self.transport([{}], budget=1, name=provider)
            with self.assertRaises(ProviderRequestError):
                make_adapters(transport, anonymous=True)[provider].fetch_search_page(self.request(provider), "*")

    def test_missing_metadata_never_invented(self):
        result = normalize_provider_records("semantic_scholar", [{"paperId": "F", "title": "Fictional"}],
                    search_run_id="F", retrieved_at="now", raw_response_path="fixture")
        self.assertIsNone(result.candidates[0].doi)
        self.assertIsNone(result.candidates[0].abstract)
        self.assertIsNone(result.candidates[0].publication_year)

    def test_pubmed_identity_mismatch_rejected(self):
        transport = self.transport([{"esearchresult": {"count": "1", "idlist": ["999"]}}, XML.encode()], budget=2)
        with self.assertRaises(ProviderRequestError):
            make_adapters(transport, anonymous=True)["pubmed"].fetch_search_page(self.request("pubmed"), "*")

    def test_xml_entities_rejected(self):
        with self.assertRaises(ProviderRequestError):
            pubmed_records('<!ENTITY bad "private"><PubmedArticleSet/>')

    def test_pubmed_adjacent_date_tags_and_original_xml_replay(self):
        from research_review_agent.scholarly.public_providers import records_from_payload
        xml = XML.replace("<Year>2099</Year>", "<Year>2099</Year><Month>Oct</Month><Day>22</Day>")
        self.assertEqual(pubmed_records(xml)[0]["year"], 2099)
        records, _ = records_from_payload("pubmed", {"pubmed_xml": xml, "records": [{"year": None}]})
        self.assertEqual(records[0]["year"], 2099)

    def test_pagination_and_unknown_filters(self):
        europe = {**EUROPE, "nextCursorMark": "NEXT"}
        transport = self.transport([europe], budget=1)
        page = make_adapters(transport, anonymous=True)["europepmc"].fetch_search_page(self.request("europepmc"), "*")
        self.assertEqual(page.next_cursor, "NEXT")
        adapter = make_adapters(transport, anonymous=True)["semantic_scholar"]
        with self.assertRaises(ProviderRequestError):
            adapter.fetch_search_page(replace(self.request("semantic_scholar"), per_page=25), "999")
        with self.assertRaises(ValueError):
            adapter.fetch_search_page(replace(self.request("semantic_scholar"), filters={"fake": "yes"}), "*")
        self.assertEqual(transport.used, 1)

    def test_source_plans_across_domains_and_user_overrides(self):
        health = source_plan("Adolescent health", "public health")
        self.assertIn("pubmed", [s["provider"] for s in health["sources"]])
        for domain in ("archaeology", "education"):
            plan = source_plan("What evidence addresses this question?", domain)
            self.assertNotIn("pubmed", [s["provider"] for s in plan["sources"]])
            self.assertTrue(all(not s["selected"] for s in plan["sources"]))
        plan = source_plan("Health", include=["pubmed"], exclude=["openalex"])
        self.assertEqual([s["provider"] for s in plan["sources"]], ["pubmed"])
        with self.assertRaises(ValueError):
            source_plan("q", include=["pubmed"], exclude=["pubmed"])

    def test_coverage_unexecuted_is_not_zero_and_counts_not_sufficiency(self):
        report = coverage_report(self.root, source_plan("Fictional", include=["pubmed"]))
        self.assertIsNone(report["unexecuted_sources"][0]["result_count"])
        self.assertEqual(report["coverage_judgment"], "pending_human_review")


if __name__ == "__main__":
    unittest.main()
