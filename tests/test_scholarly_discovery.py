from __future__ import annotations

import hashlib
import io
import json
import socket
import tempfile
import unittest
import urllib.error
from pathlib import Path

from research_review_agent.project import approve_protocol, initialize_project
from research_review_agent.scholarly.contracts import PaperCandidate, ProviderFailure, SearchRequest
from research_review_agent.scholarly.normalization import normalize_doi, normalize_openalex_records
from research_review_agent.scholarly.pipeline import ScholarlyDiscoveryPipeline, WorkflowAuthorizationError
from research_review_agent.scholarly.providers import CrossrefAdapter, FetchedPage, OpenAlexAdapter
from research_review_agent.scholarly.registry import PaperRegistry
from research_review_agent.scholarly.store import DiscoveryStore, RawResponseIntegrityError
from research_review_agent.scholarly.transport import HttpResponse, HttpTransport, ProviderRequestError
from research_review_agent.state import utc_now
from research_review_agent.validation import validate_discovery_provenance, validate_phase
from research_review_agent.workflow import transition_phase


FIXTURES = Path(__file__).parent / "fixtures"


class FixtureTransport:
    def __init__(self, bodies: list[bytes]) -> None:
        self.bodies = list(bodies)
        self.requests: list[tuple[str, dict[str, str]]] = []

    def get(self, *, provider: str, url: str, headers: dict[str, str]) -> HttpResponse:
        self.requests.append((url, headers))
        if not self.bodies:
            raise AssertionError("Fixture transport exhausted")
        return HttpResponse(200, {"content-type": "application/json"}, self.bodies.pop(0), url)


class SequenceAdapter:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.cursors: list[str | None] = []

    def fetch_search_page(self, request: SearchRequest, cursor: str | None) -> FetchedPage:
        self.cursors.append(cursor)
        if not self.outcomes:
            raise AssertionError("Adapter outcomes exhausted")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]


def fixture_bytes(provider: str, name: str) -> bytes:
    return (FIXTURES / provider / name).read_bytes()


def fetched_page(provider: str, name: str, page_number: int = 1) -> FetchedPage:
    body = fixture_bytes(provider, name)
    payload = json.loads(body)
    if provider == "openalex":
        records = payload["results"]
        next_cursor = payload["meta"].get("next_cursor")
    else:
        message = payload["message"]
        records = message.get("items", [message])
        next_cursor = message.get("next-cursor")
    return FetchedPage(
        provider=provider,
        body=body,
        payload=payload,
        records=records,
        request_url_redacted=f"https://fixture.invalid/{provider}/{page_number}",
        request_parameters={"fixture": name},
        http_status=200,
        response_headers={"content-type": "application/json"},
        retrieved_at="2099-01-01T00:00:00+00:00",
        next_cursor=next_cursor,
    )


def candidate(
    *,
    provider: str,
    provider_id: str,
    title: str,
    authors: list[str],
    year: int | None,
    doi: str | None,
    version: str = "unknown",
    run_id: str = "SR-FIXTURE",
) -> PaperCandidate:
    return PaperCandidate(
        provider=provider,
        provider_record_id=provider_id,
        search_run_id=run_id,
        retrieved_at="2099-01-01T00:00:00+00:00",
        raw_response_path="02_discovery/raw/fixture.json",
        raw_record_index=0,
        title=title,
        authors=authors,
        publication_year=year,
        source_title="Fictional Venue",
        doi=doi,
        landing_page_url=None,
        work_type="article",
        version_type=version,
        abstract=None,
    )


class ScholarlyDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def ready_project(self) -> Path:
        project = Path(self.temp.name) / "review"
        initialize_project(
            project,
            "How do fictional test records exercise metadata infrastructure?",
            "software-validation",
            self.repo / "examples/configs/education.json",
        )
        approve_protocol(project, "fixture-reviewer")
        (project / "01_search/SEARCH_CONCEPTS.md").write_text("# Fixture concepts\n\nSynthetic test concepts only.\n", encoding="utf-8")
        transition_phase(project, 1, "in_progress")
        transition_phase(project, 1, "completed")
        (project / "01_search/SEARCH_STRINGS.md").write_text("# Fixture search\n\n`fictional metadata`\n", encoding="utf-8")
        transition_phase(project, 2, "in_progress")
        transition_phase(project, 2, "completed")
        transition_phase(project, 3, "in_progress")
        return project

    def request(self, project: Path, provider: str = "openalex", max_pages: int = 1) -> SearchRequest:
        protocol = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
        return SearchRequest(
            project_id=protocol["project_id"],
            protocol_version=protocol["protocol_version"],
            search_strategy_version="fixture-v1",
            provider=provider,
            exact_query="fictional metadata",
            per_page=2,
            max_pages=max_pages,
        )

    def test_openalex_provider_parses_search_pagination_and_redacts_key(self) -> None:
        transport = FixtureTransport([fixture_bytes("openalex", "page1.json")])
        adapter = OpenAlexAdapter(transport=transport, api_key="secret-test-key")
        page = adapter.fetch_search_page(self.request_stub("openalex"), "*")
        self.assertEqual(len(page.records), 2)
        self.assertEqual(page.next_cursor, "CURSOR_PAGE_2")
        self.assertNotIn("secret-test-key", page.request_url_redacted)
        self.assertEqual(transport.requests[0][1]["Authorization"], "Bearer secret-test-key")

    def test_crossref_provider_search_and_doi_resolution(self) -> None:
        transport = FixtureTransport([fixture_bytes("crossref", "search.json"), fixture_bytes("crossref", "doi.json")])
        adapter = CrossrefAdapter(transport=transport, mailto="test@example.invalid")
        search_page = adapter.fetch_search_page(self.request_stub("crossref"), "*")
        doi_page = adapter.fetch_doi("10.5555/fictional.alpha")
        self.assertEqual(len(search_page.records), 2)
        self.assertEqual(len(doi_page.records), 1)
        self.assertNotIn("test@example.invalid", search_page.request_url_redacted)
        self.assertIn("mailto=test%40example.invalid", transport.requests[0][0])

    def test_doi_normalization(self) -> None:
        values = [
            "https://doi.org/10.5555/FICTIONAL.ALPHA",
            "doi:10.5555/fictional.alpha",
            " 10.5555/fictional.alpha. ",
        ]
        self.assertEqual({normalize_doi(value) for value in values}, {"10.5555/fictional.alpha"})
        self.assertIsNone(normalize_doi("not-a-doi"))

    def test_openalex_normalization_handles_unicode_missing_doi_and_abstract(self) -> None:
        payload = json.loads(fixture_bytes("openalex", "page1.json"))
        result = normalize_openalex_records(
            payload["results"],
            search_run_id="SR-FIXTURE",
            retrieved_at=utc_now(),
            raw_response_path="fixture.json",
        )
        self.assertEqual(result.candidates[0].authors, ["Ána García"])
        self.assertEqual(result.candidates[1].title, "虚构考古材料记录")
        self.assertIsNone(result.candidates[1].doi)
        self.assertIsNone(result.candidates[1].abstract)
        self.assertTrue(any(value.startswith("MISSING_DOI") for value in result.warnings))

    def test_pipeline_paginates_preserves_raw_and_assigns_ids(self) -> None:
        project = self.ready_project()
        adapter = SequenceAdapter([fetched_page("openalex", "page1.json", 1), fetched_page("openalex", "page2.json", 2)])
        pipeline = ScholarlyDiscoveryPipeline(project, adapters={"openalex": adapter})
        run = pipeline.run_search(self.request(project, max_pages=2))
        self.assertEqual(run.retrieval_status, "complete")
        self.assertEqual(run.retrieved_count, 3)
        self.assertEqual(run.unique_canonical_count, 3)
        self.assertEqual(adapter.cursors, ["*", "CURSOR_PAGE_2"])
        for path, checksum in zip(run.raw_response_path, run.raw_response_sha256):
            self.assertEqual(hashlib.sha256((project / path).read_bytes()).hexdigest(), checksum)
        registry = json.loads((project / "03_library/PAPER_IDENTITIES.json").read_text(encoding="utf-8"))
        self.assertEqual(len(registry["records"]), 3)

    def test_repeated_search_keeps_stable_ids_and_counts_duplicates(self) -> None:
        project = self.ready_project()
        first = ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])})
        run1 = first.run_search(self.request(project))
        ids1 = set(json.loads((project / "03_library/PAPER_IDENTITIES.json").read_text(encoding="utf-8"))["records"])
        second = ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])})
        run2 = second.run_search(self.request(project))
        ids2 = set(json.loads((project / "03_library/PAPER_IDENTITIES.json").read_text(encoding="utf-8"))["records"])
        self.assertEqual(ids1, ids2)
        self.assertEqual(run1.unique_canonical_count, 2)
        self.assertEqual(run2.duplicate_count, 2)

    def test_cross_provider_doi_deduplication_and_conflict_recording(self) -> None:
        project = self.ready_project()
        ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])}).run_search(self.request(project))
        conflict_page = fetched_page("crossref", "conflict.json")
        pipeline = ScholarlyDiscoveryPipeline(project, adapters={"crossref": SequenceAdapter([conflict_page])})
        run = pipeline.run_search(self.request(project, provider="crossref"))
        self.assertEqual(run.duplicate_count, 1)
        registry = json.loads((project / "03_library/PAPER_IDENTITIES.json").read_text(encoding="utf-8"))
        alpha = next(value for value in registry["records"].values() if value["doi"] == "10.5555/fictional.alpha")
        self.assertEqual(alpha["verification_status"], "conflict")
        self.assertTrue(alpha["conflict_notes"])

    def test_ambiguous_title_is_not_merged(self) -> None:
        root = Path(self.temp.name) / "registry"
        store = DiscoveryStore(root)
        registry = PaperRegistry(root, store)
        first = registry.register(candidate(provider="openalex", provider_id="W1", title="Same fictional title", authors=["A One"], year=2020, doi=None))
        second = registry.register(candidate(provider="crossref", provider_id="X2", title="Same fictional title", authors=[], year=None, doi=None, run_id="SR-2"))
        self.assertIsNotNone(first.paper_id)
        self.assertEqual(second.status, "ambiguous")
        self.assertIsNone(second.paper_id)
        self.assertEqual(len(registry.data["records"]), 1)

    def test_preprint_and_published_different_dois_remain_separate_and_related(self) -> None:
        root = Path(self.temp.name) / "versions"
        registry = PaperRegistry(root)
        preprint = registry.register(candidate(provider="openalex", provider_id="W1", title="Versioned fictional record", authors=["A One"], year=2020, doi="10.5555/preprint", version="preprint"))
        published = registry.register(candidate(provider="crossref", provider_id="10.5555/published", title="Versioned fictional record", authors=["A One"], year=2020, doi="10.5555/published", version="published_version", run_id="SR-2"))
        self.assertNotEqual(preprint.paper_id, published.paper_id)
        self.assertIn(published.paper_id, registry.data["records"][preprint.paper_id]["related_versions"])

    def test_partial_failure_preserves_cursor_and_resume_is_idempotent(self) -> None:
        project = self.ready_project()
        failure = ProviderRequestError(ProviderFailure("NETWORK_UNAVAILABLE", "openalex", "fixture outage", utc_now(), True, 3))
        adapter = SequenceAdapter([fetched_page("openalex", "page1.json"), failure, fetched_page("openalex", "page2.json")])
        pipeline = ScholarlyDiscoveryPipeline(project, adapters={"openalex": adapter})
        request = self.request(project, max_pages=2)
        interrupted = pipeline.run_search(request)
        self.assertEqual(interrupted.retrieval_status, "partial")
        self.assertEqual(interrupted.pagination_cursor, "CURSOR_PAGE_2")
        resumed = pipeline.run_search(request, resume_run_id=interrupted.search_run_id)
        self.assertEqual(resumed.retrieval_status, "complete")
        self.assertEqual(resumed.retrieved_count, 3)
        self.assertEqual(len(set(resumed.provider_record_ids)), 3)

    def test_empty_success_is_not_reported_as_failure(self) -> None:
        project = self.ready_project()
        pipeline = ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "empty.json")])})
        run = pipeline.run_search(self.request(project))
        self.assertEqual(run.retrieval_status, "complete_empty")
        self.assertEqual(run.retrieved_count, 0)
        self.assertFalse(run.errors)

    def test_raw_checksum_mismatch_blocks_replay(self) -> None:
        project = self.ready_project()
        pipeline = ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])})
        run = pipeline.run_search(self.request(project))
        (project / run.raw_response_path[0]).write_text("tampered", encoding="utf-8")
        replay = pipeline.replay(run.search_run_id)
        self.assertEqual(replay.retrieval_status, "failed")
        self.assertEqual(replay.errors[0]["code"], "RAW_RESPONSE_INTEGRITY_FAILURE")

    def test_offline_replay_uses_raw_response_without_network(self) -> None:
        project = self.ready_project()
        pipeline = ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])})
        original = pipeline.run_search(self.request(project))
        replayed = pipeline.replay(original.search_run_id)
        self.assertEqual(replayed.retrieval_status, "replayed")
        self.assertEqual(replayed.replay_of, original.search_run_id)
        self.assertEqual(replayed.duplicate_count, 2)

    def test_unapproved_protocol_blocks_official_search_before_adapter_call(self) -> None:
        project = Path(self.temp.name) / "draft"
        initialize_project(project, "Draft-only fictional question?", "test", self.repo / "examples/configs/education.json")
        protocol = json.loads((project / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
        request = SearchRequest(protocol["project_id"], protocol["protocol_version"], "v1", "openalex", "fixture")
        adapter = SequenceAdapter([fetched_page("openalex", "page1.json")])
        with self.assertRaisesRegex(WorkflowAuthorizationError, "PROTOCOL_APPROVAL_REQUIRED"):
            ScholarlyDiscoveryPipeline(project, adapters={"openalex": adapter}).run_search(request)
        self.assertEqual(adapter.cursors, [])

    def test_openalex_cursor_without_key_fails_explicitly(self) -> None:
        adapter = OpenAlexAdapter(transport=FixtureTransport([]), api_key="")
        with self.assertRaisesRegex(ProviderRequestError, "REQUIRES_API_KEY"):
            adapter.fetch_search_page(self.request_stub("openalex"), "SECOND_CURSOR")

    def test_malformed_provider_envelope_fails_explicitly(self) -> None:
        adapter = OpenAlexAdapter(transport=FixtureTransport([b"[]"]), api_key="fixture-key")
        with self.assertRaises(ProviderRequestError) as caught:
            adapter.fetch_search_page(self.request_stub("openalex"), "*")
        self.assertEqual(caught.exception.failure.code, "MALFORMED_RESPONSE")

    def test_transport_timeout_has_stable_code(self) -> None:
        def opener(request: object, timeout: float) -> object:
            raise socket.timeout("fixture timeout")
        transport = HttpTransport(max_attempts=2, sleep=lambda _: None, opener=opener)
        with self.assertRaises(ProviderRequestError) as caught:
            transport.get(provider="fixture", url="https://fixture.invalid", headers={})
        self.assertEqual(caught.exception.failure.code, "TIMEOUT")
        self.assertEqual(caught.exception.failure.attempt, 2)

    def test_http_transport_retries_429_and_5xx(self) -> None:
        outcomes: list[object] = [
            urllib.error.HTTPError("https://fixture.invalid", 429, "rate", {"Retry-After": "0"}, io.BytesIO(b'{"error":"rate"}')),
            urllib.error.HTTPError("https://fixture.invalid", 503, "down", {}, io.BytesIO(b'{"message":"down"}')),
            FakeUrlResponse(b'{"ok":true}'),
        ]

        def opener(request: object, timeout: float) -> object:
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        transport = HttpTransport(max_attempts=3, sleep=lambda _: None, opener=opener)
        response = transport.get(provider="fixture", url="https://fixture.invalid", headers={})
        self.assertEqual(response.status, 200)
        self.assertEqual(len(outcomes), 0)

    def test_http_transport_distinguishes_auth_and_quota(self) -> None:
        for status, body, code in [
            (401, b'{"message":"bad key"}', "AUTHENTICATION_FAILED"),
            (429, b'{"error":"not_enough_credits"}', "QUOTA_EXHAUSTED"),
            (429, b'{"error":"Rate limit exceeded","message":"Insufficient budget; daily budget is used up ($0 remaining)."}', "QUOTA_EXHAUSTED"),
        ]:
            def opener(request: object, timeout: float, status: int = status, body: bytes = body) -> object:
                raise urllib.error.HTTPError("https://fixture.invalid", status, "error", {}, io.BytesIO(body))
            transport = HttpTransport(max_attempts=1, sleep=lambda _: None, opener=opener)
            with self.assertRaises(ProviderRequestError) as caught:
                transport.get(provider="fixture", url="https://fixture.invalid", headers={})
            self.assertEqual(caught.exception.failure.code, code)

    def test_search_run_records_required_provenance_and_state_event(self) -> None:
        project = self.ready_project()
        run = ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])}).run_search(self.request(project))
        persisted = json.loads((project / f"02_discovery/search_runs/{run.search_run_id}.json").read_text(encoding="utf-8"))
        required = {
            "search_run_id", "project_id", "protocol_version", "search_strategy_version", "provider",
            "exact_query", "filters", "execution_timestamp", "retrieval_status", "raw_response_path",
            "raw_response_sha256", "provider_record_ids", "retrieved_count", "pagination_cursor",
            "warnings", "errors", "coverage_limitations",
        }
        self.assertTrue(required.issubset(persisted))
        events = (project / ".review/events.jsonl").read_text(encoding="utf-8")
        self.assertIn("scholarly_search_finished", events)

    def test_discovery_validator_accepts_intact_run_and_phase3_artifacts(self) -> None:
        project = self.ready_project()
        ScholarlyDiscoveryPipeline(project, adapters={"openalex": SequenceAdapter([fetched_page("openalex", "page1.json")])}).run_search(self.request(project))
        self.assertEqual(validate_discovery_provenance(project, require_runs=True), [])
        self.assertEqual(validate_phase(project, 3), [])

    @staticmethod
    def request_stub(provider: str) -> SearchRequest:
        return SearchRequest("P", "1.0", "S1", provider, "fictional metadata", per_page=2, max_pages=1)


class FakeUrlResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.status = 200
        self.headers: dict[str, str] = {}
        self.url = "https://fixture.invalid"

    def __enter__(self) -> "FakeUrlResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


if __name__ == "__main__":
    unittest.main()
