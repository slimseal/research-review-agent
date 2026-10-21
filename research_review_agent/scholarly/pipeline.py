from __future__ import annotations

import csv
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

from ..constants import CSV_FIELDS
from ..state import load_state, persist_state, utc_now
from ..validation import validate_protocol
from .contracts import ProviderFailure, ProviderResponse, SearchRequest, SearchRun
from .normalization import normalize_doi, normalize_provider_records
from .providers import CrossrefAdapter, FetchedPage, OpenAlexAdapter
from .registry import PaperRegistry
from .store import DiscoveryStore, RawResponseIntegrityError
from .transport import ProviderRequestError


class WorkflowAuthorizationError(RuntimeError):
    pass


class ScholarlyDiscoveryPipeline:
    """Coordinates provider, normalization, registry, provenance and workflow events."""

    def __init__(
        self,
        project_root: Path,
        *,
        adapters: dict[str, Any] | None = None,
        enforce_workflow: bool = True,
    ) -> None:
        self.project_root = project_root.resolve()
        self.store = DiscoveryStore(self.project_root)
        self.registry = PaperRegistry(self.project_root, self.store)
        self.adapters = adapters or {
            "openalex": OpenAlexAdapter(),
            "crossref": CrossrefAdapter(),
        }
        self.enforce_workflow = enforce_workflow

    def run_search(self, request: SearchRequest, *, resume_run_id: str | None = None) -> SearchRun:
        if self.enforce_workflow:
            self._assert_search_allowed(request)
        if request.provider not in self.adapters:
            raise ValueError(f"UNSUPPORTED_PROVIDER: {request.provider}")
        if not request.exact_query.strip():
            raise ValueError("EMPTY_SEARCH_QUERY")
        if request.per_page < 1 or request.per_page > (100 if request.provider == "openalex" else 1000):
            raise ValueError("INVALID_PER_PAGE")
        if request.max_pages < 1:
            raise ValueError("INVALID_MAX_PAGES")

        if resume_run_id:
            run = self.store.load_run(resume_run_id)
            self._assert_resume_matches(run, request)
            if run.retrieval_status in {"complete", "complete_empty", "complete_with_limit", "replayed"}:
                return run
            if run.errors:
                run.error_history.extend(run.errors)
                run.warnings.extend(
                    f"RESUMED_AFTER_ERROR:{value.get('code', 'UNKNOWN')}" for value in run.errors
                )
                run.errors = []
                run.coverage_limitations = [
                    value for value in run.coverage_limitations if not value.endswith("retrieval may be incomplete.")
                ]
            run.retrieval_status = "running"
            run.completed_at = None
            cursor = run.pagination_cursor
        else:
            run = SearchRun(
                search_run_id=f"SR-{uuid.uuid4().hex[:16].upper()}",
                project_id=request.project_id,
                protocol_version=request.protocol_version,
                search_strategy_version=request.search_strategy_version,
                provider=request.provider,
                exact_query=request.exact_query,
                filters=dict(request.filters),
                execution_timestamp=utc_now(),
                retrieval_status="running",
                pagination_cursor=request.cursor or "*",
            )
            cursor = request.cursor or "*"
        self.store.save_run(run)
        adapter = self.adapters[request.provider]

        for _ in range(request.max_pages):
            page_number = run.pages_completed + 1
            try:
                page = adapter.fetch_search_page(request, cursor)
                self._process_page(run, page, page_number)
            except ProviderRequestError as exc:
                self._record_failure(run, exc.failure)
                return self._finalize(run)
            except (RawResponseIntegrityError, json.JSONDecodeError, OSError, ValueError) as exc:
                failure = ProviderFailure(
                    code=self._internal_failure_code(exc),
                    provider=request.provider,
                    message=str(exc),
                    occurred_at=utc_now(),
                    retryable=False,
                    attempt=1,
                )
                self._record_failure(run, failure)
                return self._finalize(run)

            previous_cursor = cursor
            cursor = page.next_cursor
            run.pagination_cursor = cursor
            self.store.save_run(run)
            if not page.records or cursor is None:
                break
            if request.provider == "crossref" and len(page.records) < request.per_page:
                run.pagination_cursor = None
                break
            if cursor == previous_cursor:
                failure = ProviderFailure(
                    code="PAGINATION_CURSOR_STALLED",
                    provider=request.provider,
                    message="Provider returned the same pagination cursor; retrieval stopped to avoid duplication.",
                    occurred_at=utc_now(),
                    retryable=False,
                    attempt=1,
                )
                self._record_failure(run, failure)
                return self._finalize(run)
        else:
            if run.pagination_cursor:
                run.coverage_limitations.append("MAX_PAGES_REACHED: additional provider results may remain.")

        if run.errors:
            run.retrieval_status = "partial" if run.retrieved_count else "failed"
        elif run.retrieved_count == 0:
            run.retrieval_status = "complete_empty"
            run.warnings.append("EMPTY_SUCCESS: provider returned a successful response with zero records.")
        elif run.pagination_cursor and "MAX_PAGES_REACHED: additional provider results may remain." in run.coverage_limitations:
            run.retrieval_status = "complete_with_limit"
        else:
            run.retrieval_status = "complete"
            run.pagination_cursor = None
        return self._finalize(run)

    def resolve_crossref_doi(self, request: SearchRequest, doi: str) -> SearchRun:
        if request.provider != "crossref":
            raise ValueError("DOI_RESOLUTION_REQUIRES_CROSSREF")
        normalized = normalize_doi(doi)
        if not normalized:
            raise ValueError(f"INVALID_DOI: {doi}")
        if self.enforce_workflow:
            self._assert_search_allowed(request, allowed_active_phases={3, 5})
        run = SearchRun(
            search_run_id=f"SR-{uuid.uuid4().hex[:16].upper()}",
            project_id=request.project_id,
            protocol_version=request.protocol_version,
            search_strategy_version=request.search_strategy_version,
            provider="crossref",
            exact_query=f"doi:{normalized}",
            filters={},
            execution_timestamp=utc_now(),
            retrieval_status="running",
            pagination_cursor=None,
        )
        self.store.save_run(run)
        try:
            page = self.adapters["crossref"].fetch_doi(normalized)
            self._process_page(run, page, 1)
            run.retrieval_status = "complete" if run.retrieved_count else "complete_empty"
            run.pagination_cursor = None
        except ProviderRequestError as exc:
            self._record_failure(run, exc.failure)
        except (RawResponseIntegrityError, OSError, ValueError) as exc:
            self._record_failure(
                run,
                ProviderFailure(
                    code=self._internal_failure_code(exc),
                    provider="crossref",
                    message=str(exc),
                    occurred_at=utc_now(),
                    retryable=False,
                    attempt=1,
                ),
            )
        return self._finalize(run)

    def replay(self, original_run_id: str) -> SearchRun:
        original = self.store.load_run(original_run_id)
        if self.enforce_workflow:
            request = SearchRequest(
                project_id=original.project_id,
                protocol_version=original.protocol_version,
                search_strategy_version=original.search_strategy_version,
                provider=original.provider,
                exact_query=original.exact_query,
                filters=original.filters,
            )
            self._assert_search_allowed(request, allowed_active_phases={3, 5})
        responses = self.store.provider_responses(original_run_id)
        if not responses:
            raise ValueError(f"NO_REPLAYABLE_RESPONSES: {original_run_id}")
        run = SearchRun(
            search_run_id=f"SR-{uuid.uuid4().hex[:16].upper()}",
            project_id=original.project_id,
            protocol_version=original.protocol_version,
            search_strategy_version=original.search_strategy_version,
            provider=original.provider,
            exact_query=original.exact_query,
            filters=original.filters,
            execution_timestamp=utc_now(),
            retrieval_status="running",
            coverage_limitations=["OFFLINE_REPLAY: no live provider request was made."],
            replay_of=original_run_id,
        )
        self.store.save_run(run)
        for response in responses:
            try:
                body = self.store.verify_raw_response(response["raw_response_path"], response["raw_response_sha256"])
                payload = json.loads(body.decode("utf-8"))
                records, next_cursor = self._records_from_payload(original.provider, payload)
                page = FetchedPage(
                    provider=original.provider,
                    body=body,
                    payload=payload,
                    records=records,
                    request_url_redacted="offline-replay",
                    request_parameters={"replay_of": original_run_id},
                    http_status=200,
                    response_headers={},
                    retrieved_at=utc_now(),
                    next_cursor=next_cursor,
                )
                self._process_page(
                    run,
                    page,
                    run.pages_completed + 1,
                    existing_raw=(response["raw_response_path"], response["raw_response_sha256"]),
                )
            except (RawResponseIntegrityError, UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError) as exc:
                self._record_failure(
                    run,
                    ProviderFailure(
                        code=self._internal_failure_code(exc),
                        provider=original.provider,
                        message=str(exc),
                        occurred_at=utc_now(),
                        retryable=False,
                        attempt=1,
                    ),
                )
                return self._finalize(run)
        run.retrieval_status = "replayed"
        run.pagination_cursor = original.pagination_cursor
        return self._finalize(run)

    def _process_page(
        self,
        run: SearchRun,
        page: FetchedPage,
        page_number: int,
        *,
        existing_raw: tuple[str, str] | None = None,
    ) -> None:
        if existing_raw:
            raw_path, checksum = existing_raw
        else:
            raw_path, checksum = self.store.write_raw_response(page.provider, run.search_run_id, page_number, page.body)
        run.raw_response_path.append(raw_path)
        run.raw_response_sha256.append(checksum)
        run.retrieved_count += len(page.records)
        provider_response = ProviderResponse(
            search_run_id=run.search_run_id,
            provider=page.provider,
            page_number=page_number,
            request_url_redacted=page.request_url_redacted,
            request_parameters=page.request_parameters,
            http_status=page.http_status,
            response_headers=page.response_headers,
            retrieved_at=page.retrieved_at,
            raw_response_path=raw_path,
            raw_response_sha256=checksum,
            record_count=len(page.records),
            next_cursor=page.next_cursor,
        )
        self.store.append_provider_response(provider_response)
        normalized = normalize_provider_records(
            page.provider,
            page.records,
            search_run_id=run.search_run_id,
            retrieved_at=page.retrieved_at,
            raw_response_path=raw_path,
        )
        run.parsed_count += len(normalized.candidates)
        run.rejected_count += normalized.rejected_count
        run.warnings.extend(value for value in normalized.warnings if value not in run.warnings)
        for candidate in normalized.candidates:
            if candidate.provider_record_id not in run.provider_record_ids:
                run.provider_record_ids.append(candidate.provider_record_id)
            registration = self.registry.register(candidate)
            if registration.status == "created":
                run.unique_canonical_count += 1
            elif registration.status == "duplicate":
                run.duplicate_count += 1
            elif registration.status == "ambiguous":
                run.ambiguous_identity_count += 1
            self._upsert_discovery_candidate(candidate, registration.paper_id, registration.status)
        run.pages_completed += 1
        run.pagination_cursor = page.next_cursor
        self.store.save_run(run)

    def _record_failure(self, run: SearchRun, failure: ProviderFailure) -> None:
        run.errors.append(failure.to_dict())
        run.coverage_limitations.append(f"{failure.code}: retrieval may be incomplete.")
        run.retrieval_status = "partial" if run.retrieved_count else "failed"
        self.store.save_run(run)

    def _finalize(self, run: SearchRun) -> SearchRun:
        run.completed_at = utc_now()
        self.store.save_run(run)
        self._upsert_search_log(run)
        state_path = self.project_root / ".review/state.json"
        if state_path.exists():
            state = load_state(self.project_root)
            persist_state(
                self.project_root,
                state,
                "scholarly_search_finished",
                {
                    "search_run_id": run.search_run_id,
                    "provider": run.provider,
                    "retrieval_status": run.retrieval_status,
                    "retrieved_count": run.retrieved_count,
                    "pagination_cursor_present": bool(run.pagination_cursor),
                    "error_codes": [value.get("code", "UNKNOWN") for value in run.errors],
                    "coverage_limitations": run.coverage_limitations,
                },
            )
        return run

    def _assert_search_allowed(self, request: SearchRequest, allowed_active_phases: set[int] | None = None) -> None:
        issues = validate_protocol(self.project_root, require_approved=True, require_substantive=True)
        if issues:
            raise WorkflowAuthorizationError(
                "PROTOCOL_APPROVAL_REQUIRED: " + "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
            )
        protocol = json.loads((self.project_root / "00_protocol/PROTOCOL.json").read_text(encoding="utf-8"))
        if protocol.get("project_id") != request.project_id:
            raise WorkflowAuthorizationError("PROJECT_ID_MISMATCH")
        if protocol.get("protocol_version") != request.protocol_version:
            raise WorkflowAuthorizationError("PROTOCOL_VERSION_MISMATCH")
        state = load_state(self.project_root)
        if state["phases"]["2"]["status"] != "completed":
            raise WorkflowAuthorizationError("PHASE_2_REQUIRED: search strings must be completed before official discovery.")
        allowed = allowed_active_phases or {3}
        if not any(state["phases"][str(phase)]["status"] == "in_progress" for phase in allowed):
            phase_list = ", ".join(str(value) for value in sorted(allowed))
            raise WorkflowAuthorizationError(f"ACTIVE_PHASE_REQUIRED: one of phases {phase_list} must be in_progress.")

    @staticmethod
    def _assert_resume_matches(run: SearchRun, request: SearchRequest) -> None:
        expected = (
            run.project_id,
            run.protocol_version,
            run.search_strategy_version,
            run.provider,
            run.exact_query,
            run.filters,
        )
        actual = (
            request.project_id,
            request.protocol_version,
            request.search_strategy_version,
            request.provider,
            request.exact_query,
            request.filters,
        )
        if expected != actual:
            raise ValueError("RESUME_REQUEST_MISMATCH")

    @staticmethod
    def _records_from_payload(provider: str, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        if provider == "openalex":
            records = payload.get("results")
            meta = payload.get("meta")
            if not isinstance(records, list) or not isinstance(meta, dict):
                raise ValueError("MALFORMED_RESPONSE: OpenAlex replay payload")
            return [value for value in records if isinstance(value, dict)], meta.get("next_cursor")
        if provider == "crossref":
            message = payload.get("message")
            if not isinstance(message, dict):
                raise ValueError("MALFORMED_RESPONSE: Crossref replay payload")
            if isinstance(message.get("items"), list):
                return [value for value in message["items"] if isinstance(value, dict)], message.get("next-cursor")
            return [message], None
        raise ValueError(f"UNSUPPORTED_PROVIDER: {provider}")

    @staticmethod
    def _internal_failure_code(exc: Exception) -> str:
        message = str(exc)
        if "CHECKSUM" in message or "COLLISION" in message:
            return "RAW_RESPONSE_INTEGRITY_FAILURE"
        if isinstance(exc, json.JSONDecodeError):
            return "MALFORMED_RESPONSE"
        if isinstance(exc, OSError):
            return "LOCAL_IO_FAILURE"
        return "NORMALIZATION_OR_REGISTRY_FAILURE"

    def _upsert_search_log(self, run: SearchRun) -> None:
        error_codes = [str(value.get("code", "UNKNOWN")) for value in run.errors]
        row = {
            "search_id": run.search_run_id,
            "database": run.provider,
            "query": run.exact_query,
            "filters": json.dumps(run.filters, ensure_ascii=False, sort_keys=True),
            "searched_at": run.execution_timestamp,
            "result_count": str(run.retrieved_count),
            "status": run.retrieval_status,
            "failure_reason": ";".join(error_codes),
            "example_data": "false",
        }
        self._upsert_csv(self.project_root / "01_search/SEARCH_LOG.csv", CSV_FIELDS["search_log"], "search_id", row)

    def _upsert_discovery_candidate(self, candidate: Any, paper_id: str | None, identity_status: str) -> None:
        extension = {
            "search_run_id": candidate.search_run_id,
            "provider": candidate.provider,
            "provider_record_id": candidate.provider_record_id,
            "raw_response_path": candidate.raw_response_path,
            "raw_record_index": candidate.raw_record_index,
            "retrieved_at": candidate.retrieved_at,
            "source_ids": candidate.source_ids,
            "identity_status": identity_status,
            "version_type": candidate.version_type,
            "abstract_available": candidate.abstract is not None,
            "screening_status": "not_screened",
        }
        row = {
            "paper_id": paper_id or "",
            "title": candidate.title,
            "authors": "; ".join(candidate.authors),
            "year": str(candidate.publication_year or ""),
            "journal": candidate.source_title or "",
            "doi": candidate.doi or "",
            "paper_type": candidate.work_type or "",
            "theme": "",
            "why_relevant": "",
            "discovery_source": candidate.provider,
            "source_identifier": candidate.provider_record_id,
            "abstract_basis": "provider_abstract_available" if candidate.abstract is not None else "metadata_only_missing_abstract",
            "example_data": "false",
            "extension_json": json.dumps(extension, ensure_ascii=False, sort_keys=True),
        }
        key = "source_identifier"
        self._upsert_csv(self.project_root / "02_discovery/DISCOVERY_MASTER.csv", CSV_FIELDS["discovery"], key, row)

    @staticmethod
    def _upsert_csv(path: Path, fields: list[str], key: str, value: dict[str, str]) -> None:
        rows: list[dict[str, str]] = []
        found = False
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    same_key = row.get(key) == value.get(key)
                    if key == "source_identifier" and same_key:
                        same_key = row.get("discovery_source") == value.get("discovery_source")
                    if same_key:
                        rows.append(value)
                        found = True
                    else:
                        rows.append(row)
        if not found:
            rows.append(value)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for row in rows:
                    writer.writerow({field: row.get(field, "") for field in fields})
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
