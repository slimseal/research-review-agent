from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from ..state import load_state, utc_now
from ..validation import validate_protocol
from ..workflow import evaluate_gates, gates_pass
from .contracts import AcquisitionAttempt, DocumentError, DocumentVersion, ParsedDocument, SourceAnchor, VERSION_KINDS, validate_contract
from .parser import checksum, parser_version, run_parser
from .providers import PublisherPageProvider
from .store import DocumentStore, atomic_blob, digest, safe_path
from .transport import MAX_BYTES, SecureTransport, clean_url


def identifier(prefix):
    return prefix + uuid.uuid4().hex[:20].upper()


def authorization_checked(value: dict, *, remote: bool) -> dict:
    if not isinstance(value, dict) or any(not isinstance(value.get(key, ""), str) for key in ("access_basis", "asserted_by", "reason", "license_status", "redistribution_permission")):
        raise DocumentError("INVALID_AUTHORIZATION", "Authorization must be a JSON object with string-valued rights fields.")
    allowed = {"publisher_open_access", "researcher_asserted_authorized"} if remote else {"researcher_asserted_authorized"}
    if value.get("access_basis") not in allowed or not value.get("asserted_by", "").strip() or not value.get("reason", "").strip():
        raise DocumentError("ACCESS_NOT_AUTHORIZED", "Supply a named researcher assertion, access_basis and reason; a public link alone is not authorization.")
    result = {k: value.get(k) for k in ("access_basis", "asserted_by", "reason")}
    result.update(asserted_at=utc_now(), independent_legal_verification=False)
    status = value.get("license_status", "unknown")
    if status not in {"unknown", "open_license_asserted", "restricted"}:
        raise DocumentError("INVALID_LICENSE_STATUS", "Use unknown, open_license_asserted or restricted.")
    if any(value.get(key) is not None and not isinstance(value[key], str) for key in ("license_url", "rights_url")):
        raise DocumentError("INVALID_AUTHORIZATION", "Rights and license URLs must be strings or null.")
    license_url = clean_url(value["license_url"]) if value.get("license_url") else None
    rights_url = clean_url(value["rights_url"]) if value.get("rights_url") else None
    if value["access_basis"] == "publisher_open_access" and not rights_url:
        raise DocumentError("RIGHTS_PROVENANCE_REQUIRED", "Publisher OA assertion requires its supporting policy or article URL.")
    permission = value.get("redistribution_permission", "unknown")
    if permission not in {"unknown", "not_permitted", "permitted_with_conditions"}:
        raise DocumentError("INVALID_REDISTRIBUTION_STATUS", "Use unknown, not_permitted or permitted_with_conditions.")
    if permission == "permitted_with_conditions" and (status != "open_license_asserted" or not license_url):
        raise DocumentError("REDISTRIBUTION_BASIS_REQUIRED", "Redistribution needs explicit license evidence, not public availability.")
    result.update(license_status=status, license_url=license_url, rights_url=rights_url, redistribution_permission=permission)
    return result


class DocumentPipeline:
    def __init__(self, root: Path, transport=None):
        self.root = root.resolve()
        self.store = DocumentStore(self.root)
        self.transport = transport or SecureTransport()

    def guard(self, phase: int):
        if (self.root / "READING_LAB.json").exists():
            from ..reading.pipeline import lab_context
            lab_context(self.root)
            if phase != 7:
                raise DocumentError("READING_LAB_IS_READ_ONLY_SOURCE", "Import authorized documents upstream and create an isolated reading copy.")
            return
        if (self.root / "SCREENING_LAB.json").exists():
            from ..screening.pipeline import ScreeningPipeline
            screening = ScreeningPipeline(self.root)
            screening.context()  # reject nested official reviews
            if phase != 5:
                raise DocumentError("SCREENING_LAB_NOT_SCIENTIFIC_READING", "Use screening-context for targeted eligibility pages only.")
            return
        lab = self.root / "DOCUMENT_LAB.json"
        if lab.exists():
            for parent in (self.root, *self.root.parents):
                if (parent / "00_protocol/PROTOCOL.json").exists() or (parent / ".review/state.json").exists():
                    raise DocumentError("LAB_ISOLATION_REQUIRED", "Lab mode is forbidden inside an official project.")
            if json.loads(lab.read_text()).get("mode") != "isolated_document_tooling":
                raise DocumentError("INVALID_LAB", "Invalid isolated document lab marker.")
            return
        if validate_protocol(self.root, require_approved=True, require_substantive=True):
            raise DocumentError("PROTOCOL_NOT_APPROVED", "A substantively populated human-approved Protocol is required.")
        if not gates_pass(evaluate_gates(self.root, phase)):
            raise DocumentError("WORKFLOW_GATE_BLOCKED", f"Phase {phase} prerequisites/gates are incomplete. Phase 4 and Gate 1 cannot be bypassed.")
        if load_state(self.root)["phases"][str(phase)]["status"] != "in_progress":
            raise DocumentError("PHASE_NOT_ACTIVE", f"Start Phase {phase} through the existing controller first.")

    def check_identity(self, paper_id, unresolved=False):
        if paper_id is None and unresolved:
            return
        if paper_id not in self.store.paper_ids():
            raise DocumentError("MISSING_PAPER_ID", "Use an existing registered paper ID, or explicitly assert unresolved identity with no paper ID.")

    def discover(self, paper_id: str, url: str) -> dict:
        self.guard(5)
        self.check_identity(paper_id)
        with self.store.lock():
            data = self.store.load()
            attempt = AcquisitionAttempt(identifier("AT-"), paper_id, "publisher_page", None, utc_now()).to_dict()
            data["attempts"][attempt["attempt_id"]] = attempt
            self.store.commit(data, "discovery_started")
            try:
                attempt["candidate_url"] = clean_url(url)
                result = PublisherPageProvider(self.transport).discover(url)
                response = result["response"]
                relative = f"03_library/documents/source_responses/{response['sha256']}.bin"
                atomic_blob(safe_path(self.root, relative), response["data"])
                candidates = []
                for candidate in result["candidates"]:
                    candidate.update(contract_version="1.0.0", paper_id=paper_id, provider="publisher_page", source_url=clean_url(url), source_response_path=relative, source_response_sha256=response["sha256"], retrieved_at=utc_now())
                    candidate["candidate_id"] = "FC-" + digest(candidate)[:20].upper()
                    data["candidates"][candidate["candidate_id"]] = candidate
                    candidates.append(candidate)
                attempt.update(result_status=result["status"], http_status=response["http_status"], final_url=response["final_url"], redirects=response["redirects"], checksum=response["sha256"], downloaded_bytes=len(response["data"]))
                self.store.commit(data, "discovery_finished")
                return {"status": result["status"], "candidates": candidates, "attempt_id": attempt["attempt_id"]}
            except (DocumentError, OSError) as error:
                return self._fail(data, attempt, error)

    def _fail(self, data, attempt, error):
        if not isinstance(error, DocumentError):
            error = DocumentError("LOCAL_IO_FAILURE", "Local I/O failed. Check disk space and permissions; no success should be inferred.")
        attempt.update(result_status="failed", failure_code=error.code, message=error.message)
        if error.http_status is not None:
            attempt["http_status"] = error.http_status
        if error.code == "ACCESS_NOT_AUTHORIZED":
            attempt["access_decision"] = "blocked"
        self.store.commit(data, "operation_failed")
        return {"status": "failed", "attempt_id": attempt["attempt_id"], "error": error.to_dict()}

    def acquire(self, *, paper_id: str | None = None, local: Path | None = None, candidate_id: str | None = None,
                authorization: dict, version_kind="unknown", unresolved=False) -> dict:
        self.guard(5)
        with self.store.lock():
            data = self.store.load()
            attempt = AcquisitionAttempt(identifier("AT-"), paper_id, "local_import" if local else "publisher_page", None, utc_now()).to_dict()
            data["attempts"][attempt["attempt_id"]] = attempt
            self.store.commit(data, "acquisition_started")
            try:
                self.check_identity(paper_id, unresolved)
                if version_kind not in VERSION_KINDS:
                    raise DocumentError("INVALID_VERSION_KIND", "Unknown version kind; do not conflate preprint and published versions.")
                if bool(local) == bool(candidate_id):
                    raise DocumentError("INVALID_ACQUISITION", "Specify exactly one local file or discovered candidate ID.")
                rights = authorization_checked(authorization, remote=local is None)
                attempt.update(authorization=rights, access_decision="researcher_assertion_recorded_not_independently_verified")
                parser_version()  # fail before remote download if integrity parser is unavailable
                if local:
                    if not local.is_file():
                        raise DocumentError("LOCAL_FILE_MISSING", "Authorized local PDF does not exist.")
                    if local.stat().st_size > MAX_BYTES:
                        raise DocumentError("FILE_TOO_LARGE", "Local PDF exceeds 25 MiB limit.")
                    with local.open("rb") as handle:
                        body = handle.read(MAX_BYTES + 1)
                    attempt["local_source_name"] = local.name
                else:
                    candidate = data["candidates"].get(candidate_id)
                    if not candidate or candidate["paper_id"] != paper_id:
                        raise DocumentError("INVALID_CANDIDATE", "Select a saved PDF candidate for this registered paper.")
                    source = safe_path(self.root, candidate["source_response_path"])
                    if checksum(source) != candidate["source_response_sha256"]:
                        raise DocumentError("PROVENANCE_CHECKSUM_MISMATCH", "Saved discovery response has changed.")
                    attempt["candidate_url"] = clean_url(candidate["candidate_url"])
                    response = self.transport.get(candidate["candidate_url"], pdf=True)
                    body = response["data"]
                    attempt.update(http_status=response["http_status"], final_url=response["final_url"], redirects=response["redirects"])
                if len(body) > MAX_BYTES:
                    raise DocumentError("FILE_TOO_LARGE", "PDF exceeds 25 MiB limit.")
                sha = hashlib.sha256(body).hexdigest()
                attempt.update(downloaded_bytes=len(body), checksum=sha)
                # A staging blob is not an acquired document. It is removed on every handled outcome.
                staging = safe_path(self.root, f"03_library/documents/staging/{attempt['attempt_id']}.pdf")
                atomic_blob(staging, body)
                try:
                    inspected = run_parser(staging, extract=False)
                    relative = f"03_library/documents/files/{sha}.pdf"
                    atomic_blob(safe_path(self.root, relative), body)
                finally:
                    staging.unlink(missing_ok=True)
                existing = next((d for d in data["documents"].values() if (d["paper_id"], d["sha256"], d["version_kind"]) == (paper_id, sha, version_kind)), None)
                if existing:
                    document = existing
                    document["attempt_ids"].append(attempt["attempt_id"])
                    status = "duplicate_content"
                else:
                    document = DocumentVersion(
                        document_id=identifier("DV-"), paper_id=paper_id, document_type="supplementary" if version_kind == "supplementary" else "article_or_source",
                        version_kind=version_kind, source_url=attempt["candidate_url"], acquisition_method="authorized_local_import" if local else "authorized_remote_download",
                        provider=attempt["provider"], acquired_at=utc_now(), access_basis=rights["access_basis"], license_status=rights["license_status"], license_url=rights["license_url"],
                        redistribution_permission=rights["redistribution_permission"], local_path=relative, sha256=sha, file_size=len(body), mime_type="application/pdf", pdf_page_count=inspected["page_count"],
                        identity_status="unresolved" if paper_id is None else "registered_paper", attempt_ids=[attempt["attempt_id"]],
                        related_document_ids=[d["document_id"] for d in data["documents"].values() if paper_id is not None and d["paper_id"] == paper_id],
                    ).to_dict()
                    data["documents"][document["document_id"]] = document
                    status = "imported_manually" if local else "acquired"
                attempt.update(result_status=status, document_id=document["document_id"])
                self.store.commit(data, "acquisition_finished")
                return {"status": status, "document": document, "attempt_id": attempt["attempt_id"]}
            except (DocumentError, OSError) as error:
                return self._fail(data, attempt, error)

    def _document_file(self, data, document_id):
        document = data["documents"].get(document_id)
        if not document:
            raise DocumentError("UNKNOWN_DOCUMENT", "Document ID is not registered.")
        path = safe_path(self.root, document["local_path"])
        if not path.is_file() or checksum(path) != document["sha256"]:
            raise DocumentError("DOCUMENT_CHECKSUM_MISMATCH", "Document bytes changed or are missing; do not replace an old version. Import the new version separately.")
        return document, path

    def parse(self, document_id: str) -> dict:
        self.guard(7)
        self.guard_included_document(document_id)
        with self.store.lock():
            data = self.store.load()
            log = {"operation_id": identifier("PR-"), "document_id": document_id, "timestamp": utc_now(), "status": "started"}
            data["parser_logs"].append(log)
            self.store.commit(data, "parsing_started")
            try:
                document, path = self._document_file(data, document_id)
                version = parser_version()
                previous = next((r for r in document["parse_refs"] if r["parser_version"] == version and r["status"] == "parsed"), None)
                if previous:
                    self._read_parse(document, previous)
                    result = {"status": "replayed", "parse": previous}
                else:
                    extracted = run_parser(path, extract=True)
                    if checksum(path) != document["sha256"]:
                        raise DocumentError("DOCUMENT_CHECKSUM_MISMATCH", "PDF changed during parsing.")
                    parsed = ParsedDocument(document_id=document_id, document_sha256=document["sha256"], parser_name="pypdf", parser_version=version, parsed_at=utc_now(), **extracted).to_dict()
                    payload = (json.dumps(parsed, ensure_ascii=False, indent=2) + "\n").encode()
                    sha = hashlib.sha256(payload).hexdigest()
                    relative = f"03_library/documents/parsed/{document_id}/{sha}.json"
                    atomic_blob(safe_path(self.root, relative), payload)
                    reference = {"path": relative, "sha256": sha, "parser_version": version, "status": parsed["status"]}
                    document["parse_refs"].append(reference)
                    document.update(parsing_status=parsed["status"], parser_version=version)
                    result = {"status": parsed["status"], "parse": reference}
                log.update(status=result["status"], parser_version=version)
                self.store.commit(data, "parsing_finished")
                # Parsing changes availability telemetry, not screening judgments.
                # The pre-parse Gate 1 check already verified the old projections.
                if not any((self.root / name).exists() for name in ("DOCUMENT_LAB.json", "READING_LAB.json")):
                    from ..screening.pipeline import ScreeningPipeline
                    ScreeningPipeline(self.root).export_acquisition()
                return result
            except (DocumentError, OSError) as exc:
                error = exc if isinstance(exc, DocumentError) else DocumentError("LOCAL_IO_FAILURE", "Could not read or store parser artifacts.")
                log.update(status="failed", error=error.to_dict())
                if document_id in data["documents"]:
                    data["documents"][document_id]["parsing_status"] = "failed"
                self.store.commit(data, "parsing_failed")
                return {"status": "failed", "error": error.to_dict()}

    def _read_parse(self, document, ref):
        path = safe_path(self.root, ref["path"])
        if not path.exists() or checksum(path) != ref["sha256"]:
            raise DocumentError("PARSE_CHECKSUM_MISMATCH", "Parsed artifact is missing or changed; anchors need reverification.")
        parsed = json.loads(path.read_text())
        validate_contract("ParsedDocument", parsed)
        if parsed["document_sha256"] != document["sha256"] or parsed["document_id"] != document["document_id"] or parsed["parser_version"] != ref["parser_version"]:
            raise DocumentError("PARSE_BINDING_MISMATCH", "Parser artifact no longer matches this document version.")
        return parsed

    def anchor(self, document_id: str, quote: str, *, pdf_page=None, start=None, end=None) -> dict:
        self.guard(7)
        self.guard_included_document(document_id)
        if not quote.strip() or len(quote) > 4000:
            raise DocumentError("INVALID_ANCHOR_TEXT", "Provide 1–4000 characters of actual source text.")
        with self.store.lock():
            data = self.store.load()
            document, _ = self._document_file(data, document_id)
            if not document["parse_refs"]:
                raise DocumentError("DOCUMENT_NOT_PARSED", "Parse the document before anchoring text.")
            ref = document["parse_refs"][-1]
            if ref["parser_version"] != parser_version():
                raise DocumentError("PARSER_VERSION_CHANGED", "Reparse with the current parser before making anchors.")
            parsed = self._read_parse(document, ref)
            if pdf_page is not None and (not isinstance(pdf_page, int) or not 1 <= pdf_page <= parsed["page_count"]):
                raise DocumentError("INVALID_PDF_PAGE", "PDF page is 1-based and must exist.")
            if (start is None) != (end is None) or (start is not None and pdf_page is None):
                raise DocumentError("INVALID_SPAN", "Explicit offsets require both start/end and a PDF page.")
            matches = []
            for page in parsed["pages"]:
                if pdf_page is not None and page["pdf_page"] != pdf_page:
                    continue
                text = page["text"]
                if start is not None:
                    if not 0 <= start < end <= len(text) or text[start:end] != quote:
                        raise DocumentError("INVALID_SPAN", "The supplied span does not match exact parsed source text.")
                    matches.append({"pdf_page": pdf_page, "start": start, "end": end})
                else:
                    offset = 0
                    while (position := text.find(quote, offset)) >= 0:
                        matches.append({"pdf_page": page["pdf_page"], "start": position, "end": position + len(quote)})
                        offset = position + 1
            status = "machine_located" if len(matches) == 1 else ("ambiguous" if matches else "unresolved")
            match = matches[0] if len(matches) == 1 else None
            anchor = SourceAnchor(identifier("SA-"), document["paper_id"], document_id, document["sha256"], ref["parser_version"], ref["path"], ref["sha256"], "page_text_span" if match else "unresolved_text", match["pdf_page"] if match else None, hashlib.sha256(quote.encode()).hexdigest(), status, text_span={"start": match["start"], "end": match["end"]} if match else None, matches=matches).to_dict()
            data["anchors"][anchor["anchor_id"]] = anchor
            self.store.commit(data, "anchor_registered")
            return anchor

    def guard_included_document(self, document_id):
        if (self.root / "READING_LAB.json").exists():
            from ..reading.pipeline import lab_context
            corpus = lab_context(self.root)["corpus"]
            if document_id not in {v["document_id"] for v in corpus.values()}:
                raise DocumentError("DOCUMENT_NOT_IN_READING_PILOT", "Select an explicit pilot document.")
            return
        if (self.root / "DOCUMENT_LAB.json").exists():
            return
        from ..screening.pipeline import ScreeningPipeline
        screening = ScreeningPipeline(self.root)
        eligible = screening.gate()["eligible_paper_ids"]
        doc, _ = self._document_file(self.store.load(), document_id)
        decision = screening.latest(doc["paper_id"])
        if doc["paper_id"] not in eligible or not decision or decision["document_id"] != document_id:
            raise DocumentError("DOCUMENT_NOT_IN_APPROVED_READING_CORPUS", "Only the screened, human-approved document version may enter Phase 7.")

    def lookup(self, anchor_id: str) -> dict:
        # Deliberately read-only: reports effective stale state without rewriting history.
        data = self.store.load()
        anchor = data["anchors"].get(anchor_id)
        if not anchor:
            raise DocumentError("UNKNOWN_ANCHOR", "No registered anchor with this ID.")
        result = dict(anchor)
        try:
            validate_contract("SourceAnchor", anchor)
            document, path = self._document_file(data, anchor["document_id"])
            if document["sha256"] != anchor["document_sha256"] or parser_version() != anchor["parser_version"]:
                raise DocumentError("ANCHOR_STALE", "Document or parser version changed; create and verify a new anchor.")
            parsed = self._read_parse(document, {"path": anchor["parse_path"], "sha256": anchor["parse_sha256"], "parser_version": anchor["parser_version"]})
            if anchor["verification_status"] in {"machine_located", "human_confirmed"}:
                if not isinstance(anchor["pdf_page"], int) or not 1 <= anchor["pdf_page"] <= parsed["page_count"]:
                    raise DocumentError("ANCHOR_STALE", "Saved PDF page is outside the parsed document.")
                page = parsed["pages"][anchor["pdf_page"]-1]
                span = anchor["text_span"]
                quote = page["text"][span["start"]:span["end"]]
                if not 0 <= span["start"] < span["end"] <= len(page["text"]) or hashlib.sha256(quote.encode()).hexdigest() != anchor["quote_fingerprint"]:
                    raise DocumentError("ANCHOR_STALE", "Source text span no longer matches the stored fingerprint.")
                result.update(resolved_pdf=str(path), resolved_pdf_page=page["pdf_page"], resolved_text=quote)
            result["effective_status"] = anchor["verification_status"]
        except (DocumentError, OSError, ValueError, KeyError, IndexError, TypeError) as error:
            result.update(effective_status="stale", error=error.to_dict() if isinstance(error, DocumentError) else {"code": "ANCHOR_STALE", "message": "Document or parse locator cannot be resolved."})
        return result

    def confirm(self, anchor_id: str, by: str, note: str, printed_page=None) -> dict:
        self.guard(7)
        if (self.root / "READING_LAB.json").exists():
            raise DocumentError("PILOT_CANNOT_HUMAN_APPROVE", "Reading pilots retain machine-located anchors only.")
        if not by.strip() or not note.strip():
            raise DocumentError("HUMAN_CONFIRMATION_REQUIRED", "A named human and visual-location confirmation note are required.")
        with self.store.lock():
            resolved = self.lookup(anchor_id)
            if resolved["effective_status"] not in {"machine_located", "human_confirmed"}:
                raise DocumentError("ANCHOR_NOT_CONFIRMABLE", "Resolve ambiguous, missing or stale anchors first.")
            data = self.store.load()
            anchor = data["anchors"][anchor_id]
            anchor.update(verification_status="human_confirmed", printed_page=printed_page, confirmation={"by": by, "note": note, "at": utc_now(), "scope": "source location only; not scientific evidence"})
            self.store.commit(data, "human_anchor_confirmation")
            return anchor

    def validate(self) -> dict:
        data = self.store.load()
        errors = []
        for document in data["documents"].values():
            try:
                validate_contract("DocumentVersion", document)
                self.check_identity(document["paper_id"], document["identity_status"] == "unresolved")
                self._document_file(data, document["document_id"])
                for ref in document["parse_refs"]:
                    self._read_parse(document, ref)
            except (DocumentError, OSError) as error:
                errors.append({"document_id": document["document_id"], "error": str(error)})
        for anchor_id in data["anchors"]:
            try:
                validate_contract("SourceAnchor", data["anchors"][anchor_id])
            except DocumentError as error:
                errors.append({"anchor_id": anchor_id, "error": str(error)})
                continue
            lookup = self.lookup(anchor_id)
            if lookup["effective_status"] == "stale":
                errors.append({"anchor_id": anchor_id, "error": lookup["error"]})
        for attempt in data["attempts"].values():
            try:
                validate_contract("AcquisitionAttempt", attempt)
            except DocumentError as error:
                errors.append({"attempt_id": attempt.get("attempt_id"), "error": str(error)})
        return {"valid": not errors, "documents": len(data["documents"]), "anchors": len(data["anchors"]), "errors": errors, "phase_changes": False}
