"""Synthetic contract tests. These fixtures are not papers or live API evidence."""
import io
import json
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from research_review_agent.scholarly.contracts import SearchRequest, PaperCandidate
from research_review_agent.scholarly.normalization import normalize_provider_records
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline
from research_review_agent.scholarly.providers import make_adapters
from research_review_agent.scholarly.public_providers import records_from_payload, pubmed_records
from research_review_agent.scholarly.registry import PaperRegistry
from research_review_agent.scholarly.request_budget import RecordedTransport
from research_review_agent.scholarly.source_plan import coverage_report, source_plan
from research_review_agent.scholarly.transport import ProviderRequestError

ERIC = {"response": {"numFound": 2, "start": 0, "docs": [{"id": "EJ-FICTIONAL", "title": "Fictional education result",
    "publicationdateyear": 2099, "author": ["Tester, A"], "description": "Fictional abstract.",
    "publicationtype": ["Reports - Research"], "peerreviewed": "F"}]}}
OPENAIRE = {"header": {"numFound": 2, "page": 1, "pageSize": 1}, "results": [{"id": "fictional::1",
    "mainTitle": "Fictional software", "type": "software", "publicationDate": "2099-01-01",
    "authors": [{"fullName": "A Tester"}], "descriptions": ["Fictional description"],
    "pids": [{"scheme": "pmc", "value": "PMC123"}], "instances": [{"type": "Software", "refereed": "UNKNOWN"}]}]}
ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:o="http://a9.com/-/spec/opensearch/1.1/" xmlns:a="http://arxiv.org/schemas/atom">
<o:totalResults>2</o:totalResults><o:startIndex>0</o:startIndex><entry>
<id>http://arxiv.org/abs/9999.00001v2</id><title>Fictional preprint</title><published>2099-01-01</published>
<author><name>A Tester</name></author><summary>Fictional null result</summary>
<a:doi>10.5555/fictional-published</a:doi><a:journal_ref>Fictional Journal</a:journal_ref></entry></feed>'''


class Response(io.BytesIO):
    status, headers = 200, {}


class OpenDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.requests, self.delays = [], []

    def tearDown(self):
        self.temp.cleanup()

    def transport(self, bodies, name="http", budget=1):
        queue = list(bodies)
        def opener(request, **kwargs):
            self.requests.append(request)
            value = queue.pop(0)
            if isinstance(value, Exception):
                raise value
            return Response(value if isinstance(value, bytes) else json.dumps(value).encode())
        return RecordedTransport(self.root / name, max_requests=budget, opener=opener, sleep=self.delays.append)

    def request(self, provider):
        return SearchRequest("FICTIONAL", "none", "test-v1", provider, 'title:"fictional"', per_page=1)

    def test_native_queries_pagination_and_no_implicit_followup(self):
        for provider, body, querykey, pagekey, following in [
            ("eric", ERIC, "search", "start", "1"), ("openaire", OPENAIRE, "search", "page", "2"),
            ("arxiv", ATOM, "search_query", "start", "1")]:
            with self.subTest(provider=provider):
                transport = self.transport([body], provider)
                page = make_adapters(transport)[provider].fetch_search_page(self.request(provider), "*")
                params = parse_qs(urlsplit(self.requests[-1].full_url).query)
                self.assertEqual(params[querykey], ['title:"fictional"'])
                self.assertIn(pagekey, params)
                self.assertEqual(page.next_cursor, following)
                self.assertEqual(transport.used, 1)
        self.assertIn(3.05, self.delays)
        self.assertIn("/graph/v3/research-products", make_adapters()["openaire"].base_url)

    def test_raw_replay_and_normalization(self):
        for provider, body in [("eric", ERIC), ("openaire", OPENAIRE), ("arxiv", ATOM)]:
            root = self.root / provider
            transport = self.transport([body], provider + "/http")
            pipe = ScholarlyDiscoveryPipeline(root, adapters=make_adapters(transport), enforce_workflow=False)
            run = pipe.run_search(self.request(provider))
            self.assertEqual(run.retrieved_count, 1)
            self.assertEqual(run.http_attempts, 1)
            replay = pipe.replay(run.search_run_id)
            self.assertEqual(replay.retrieved_count, 1)
            self.assertEqual(len(pipe.registry.data["records"]), 1)
            record = next(iter(pipe.registry.data["records"].values()))
            origin = record["provenance"][0]
            self.assertTrue(origin["abstract_available"])
            if provider == "arxiv":
                self.assertEqual(record["version_type"], "preprint")
                self.assertIsNone(record["doi"])
                self.assertEqual(origin["relations"]["published_doi"], "10.5555/fictional-published")
                self.assertEqual(origin["relations"]["arxiv_version"], "v2")
            if provider == "openaire":
                self.assertEqual(record["work_type"], "software")
                self.assertEqual(origin["source_ids"]["pmcid"], "PMC123")

    def test_bad_envelopes_are_not_successful_empty_queries(self):
        for provider, bad in [("eric", {}), ("openaire", {"header": {}, "results": []}),
            ("arxiv", {"arxiv_atom": "<html/>"}), ("arxiv", {"arxiv_atom": '<!DOCTYPE feed><feed/>'})]:
            with self.assertRaises(ProviderRequestError):
                records_from_payload(provider, bad)

    def test_record_limit_fail_closed(self):
        body = {"response": {"numFound": 2, "start": 0, "docs": ERIC["response"]["docs"] * 2}}
        transport = self.transport([body])
        with self.assertRaises(ProviderRequestError):
            make_adapters(transport)["eric"].fetch_search_page(self.request("eric"), "*")
        self.assertEqual(transport.used, 1)

    def test_unsupported_filters_stop_before_network(self):
        transport = self.transport([])
        for provider in ("eric", "arxiv", "openaire"):
            with self.assertRaises(ValueError):
                make_adapters(transport)[provider].fetch_search_page(replace(self.request(provider), filters={"invented": "x"}), "*")
        self.assertEqual(transport.used, 0)

    def candidate(self, provider="pubmed", identifier="123", **kwargs):
        base = PaperCandidate(provider, identifier, "SYNTHETIC", "2099-01-01", "fictional.json", 0,
            "Fictional title", ["A Tester"], 2099, None, None, None, "article", "unknown", "Fictional abstract",
            source_ids={"pmid": "123"})
        return replace(base, **kwargs)

    def test_cross_provider_pmid_without_doi_or_same_title(self):
        registry = PaperRegistry(self.root)
        one = registry.register(self.candidate())
        two = registry.register(self.candidate("semantic_scholar", "s2", title="Variant title", source_ids={"PubMed": "123"}))
        self.assertEqual(one.paper_id, two.paper_id)
        self.assertEqual(two.identity_match.method, "exact_biomedical_identifier")
        self.assertEqual(len(registry.data["records"][one.paper_id]["provenance"]), 2)
        restored = PaperRegistry(self.root)
        three = restored.register(self.candidate("europepmc", "MED:123", title="Third title"))
        self.assertEqual(one.paper_id, three.paper_id)

    def test_pmcid_match_and_doi_conflict_are_distinct(self):
        registry = PaperRegistry(self.root)
        one = registry.register(self.candidate(source_ids={"pmcid": "PMC456"}, doi="10.5555/one"))
        match = registry.register(self.candidate("openaire", "oa1", source_ids={"pmc": "PMC456"}))
        self.assertEqual(one.paper_id, match.paper_id)
        bad = registry.register(self.candidate("openaire", "oa2", source_ids={"pmcid": "PMC456"}, doi="10.5555/two"))
        self.assertEqual(bad.status, "ambiguous")
        self.assertIsNone(bad.paper_id)

    def test_preprints_and_versions_are_not_title_merged_into_journal(self):
        registry = PaperRegistry(self.root)
        journal = registry.register(self.candidate(source_ids={}, doi="10.5555/published"))
        preprint = registry.register(self.candidate("arxiv", "9999.00001v1", source_ids={}, version_type="preprint"))
        revised = registry.register(self.candidate("arxiv", "9999.00001v2", source_ids={}, version_type="preprint", title="Revised fictional title"))
        self.assertNotEqual(journal.paper_id, preprint.paper_id)
        self.assertNotEqual(preprint.paper_id, revised.paper_id)

    def test_429_headers_preserved_without_retry_or_secrets(self):
        err = urllib.error.HTTPError("https://fixture.invalid", 429, "Limited", {
            "Retry-After": "120", "x-ratelimit-remaining": "0", "x-ratelimit-token": "private-secret"}, io.BytesIO(b'{}'))
        transport = self.transport([err])
        with self.assertRaises(ProviderRequestError) as raised:
            transport.get(provider="semantic_scholar", url="https://fixture.invalid", headers={})
        self.assertEqual(raised.exception.failure.details["response_headers"]["retry-after"], "120")
        self.assertEqual(transport.used, 1)
        self.assertNotIn("private-secret", transport.path.read_text())

    def test_long_retry_after_pauses_instead_of_retrying_early(self):
        def opener(*args, **kwargs):
            raise urllib.error.HTTPError("https://fixture.invalid", 429, "Limited", {"Retry-After": "120"}, io.BytesIO(b'{}'))
        transport = RecordedTransport(self.root / "http", max_requests=2, max_attempts=2,
                                      opener=opener, sleep=self.delays.append)
        with self.assertRaises(ProviderRequestError):
            transport.get(provider="semantic_scholar", url="https://fixture.invalid", headers={})
        self.assertEqual(transport.used, 1)
        self.assertNotIn(60, self.delays)

    def test_replay_does_not_double_count_live_searches(self):
        t = self.transport([ERIC], "http")
        pipe = ScholarlyDiscoveryPipeline(self.root, adapters=make_adapters(t), enforce_workflow=False)
        run = pipe.run_search(self.request("eric"))
        replay = pipe.replay(run.search_run_id)
        report = coverage_report(self.root)
        self.assertEqual(report["raw_result_count"], 1)
        self.assertEqual(report["http_requests_accounted"], 1)
        self.assertEqual(report["latest_normalization_totals"]["duplicate_count"], 1)
        self.assertIn(replay.search_run_id, report["offline_replay_runs_excluded_from_search_counts"])

    def test_coverage_overlap_missingness_and_skips(self):
        registry = PaperRegistry(self.root)
        registry.register(self.candidate())
        registry.register(self.candidate("europepmc", "MED:123"))
        runs = self.root / "02_discovery/search_runs"
        runs.mkdir(parents=True, exist_ok=True)
        for p in ("pubmed", "europepmc"):
            (runs / (p + ".json")).write_text(json.dumps({"provider": p, "retrieved_count": 1, "retrieval_status": "complete", "http_attempts": 1}))
        report = coverage_report(self.root, {"sources": [{"provider": "core"}]})
        self.assertEqual(report["canonical_paper_count"], 1)
        self.assertEqual(report["pairwise_overlaps"][0]["count"], 1)
        self.assertEqual(report["providers"]["pubmed"]["provider_only_candidate_count"], 0)
        self.assertEqual(report["relevance"], "not_evaluated")
        self.assertIsNone(report["unexecuted_sources"][0]["result_count"])

    def test_recommendations_respect_scope_and_explicit_exclusions(self):
        names = lambda p: [s["provider"] for s in p["sources"]]
        self.assertIn("eric", names(source_plan("School education outcomes")))
        self.assertIn("arxiv", names(source_plan("Machine learning for physics")))
        self.assertEqual(names(source_plan("School", include=["crossref"])), ["crossref"])
        self.assertNotIn("openaire", names(source_plan("School", exclude=["openaire"])))

    def test_pubmed_reference_identifiers_never_replace_article_identity(self):
        xml = '''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
        <ArticleTitle>Fictional primary paper</ArticleTitle></Article></MedlineCitation><PubmedData>
        <ArticleIdList><ArticleId IdType="doi">10.5555/primary</ArticleId><ArticleId IdType="pmc">PMC123</ArticleId></ArticleIdList>
        <ReferenceList><Reference><ArticleIdList><ArticleId IdType="doi">10.5555/cited</ArticleId>
        <ArticleId IdType="pmc">PMC999</ArticleId></ArticleIdList></Reference></ReferenceList>
        </PubmedData></PubmedArticle></PubmedArticleSet>'''
        row = pubmed_records(xml)[0]
        self.assertEqual(row["doi"], "10.5555/primary")
        self.assertEqual(row["pmcid"], "PMC123")

    def test_aggregated_multiple_identifiers_cannot_merge_via_shared_pmcid(self):
        registry = PaperRegistry(self.root)
        registry.register(self.candidate(source_ids={"pmcid": "PMC123"}, doi="10.5555/one"))
        row = {**OPENAIRE["results"][0], "pids": [{"scheme": "doi", "value": "10.5555/one"},
            {"scheme": "doi", "value": "10.5555/two"}, {"scheme": "pmc", "value": "PMC123"}]}
        candidate = normalize_provider_records("openaire", [row], search_run_id="SYNTHETIC",
            retrieved_at="2099", raw_response_path="fictional.json").candidates[0]
        result = registry.register(candidate)
        self.assertEqual(result.status, "ambiguous")
        self.assertIsNone(result.paper_id)
        self.assertEqual(len(registry.data["records"]), 1)


if __name__ == "__main__":
    unittest.main()
