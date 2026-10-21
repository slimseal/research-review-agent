from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..state import canonical_json, utc_now, write_json_atomic
from .contracts import DocumentError
from .parser import checksum


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or root.resolve() not in path.parents:
        raise DocumentError("UNSAFE_PATH", "Managed paths must remain inside the document workspace.")
    return path


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def atomic_blob(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if checksum(path) != hashlib.sha256(data).hexdigest():
            raise DocumentError("CONTENT_COLLISION", "Refusing to replace a different existing document/artifact.")
        return
    fd, temporary = tempfile.mkstemp(prefix=".document-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize_lab(root: Path, catalog: list[dict]) -> dict:
    # Lab cannot be inside or itself be an official project.
    for parent in (root, *root.parents):
        if (parent / "00_protocol/PROTOCOL.json").exists() or (parent / ".review/state.json").exists():
            raise DocumentError("LAB_ISOLATION_REQUIRED", "Choose a separate directory outside every official project.")
    if root.exists() and any(root.iterdir()):
        raise DocumentError("LAB_NOT_EMPTY", "Initialize only an empty new isolated directory.")
    identities = {}
    for row in catalog:
        paper_id = row.get("paper_id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", paper_id) or paper_id in identities:
            raise DocumentError("INVALID_PAPER_ID", "Lab catalog needs unique safe paper IDs.")
        if not all(row.get(key) for key in ("title", "authors", "year", "identity_source")):
            raise DocumentError("INCOMPLETE_IDENTITY", "Lab identities need title, authors, year and identity_source; DOI is optional.")
        identities[paper_id] = row
    value = {"contract_version": "1.0.0", "mode": "isolated_document_tooling", "created_at": utc_now(), "papers": identities, "warning": "Not an official review; no protocol approval, screening or phase progression."}
    write_json_atomic(root / "DOCUMENT_LAB.json", value)
    return value


class DocumentStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.base = safe_path(self.root, "03_library/documents")
        self.path = self.base / "manifest.json"

    @contextmanager
    def lock(self):
        self.base.mkdir(parents=True, exist_ok=True)
        path = self.base / "writer.lock"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise DocumentError("DOCUMENT_STORE_LOCKED", "Another writer or interrupted lock exists. Confirm no writer is running before removing this exact writer.lock and using documents-recover.") from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            if (self.base / "transactions").exists() and any((self.base / "transactions").iterdir()):
                raise DocumentError("DOCUMENT_RECOVERY_REQUIRED", "Manifest missing with transactions present; run documents-recover.")
            return {"contract_version": "1.0.0", "seq": 0, "documents": {}, "attempts": {}, "candidates": {}, "anchors": {}, "parser_logs": []}
        try:
            envelope = json.loads(self.path.read_text())
            if digest(envelope["data"]) != envelope["sha256"]:
                raise ValueError()
            data = envelope["data"]
            if list((self.base / "transactions").glob(f"{data['seq']+1:08d}-*.json")):
                raise ValueError()
            return data
        except (ValueError, KeyError, TypeError):
            raise DocumentError("DOCUMENT_RECOVERY_REQUIRED", "Document manifest is corrupt or behind the journal; run documents-recover.") from None

    def commit(self, data: dict, operation: str):
        data["seq"] += 1
        envelope = {"data": data, "sha256": digest(data), "operation": operation, "timestamp": utc_now()}
        path = safe_path(self.root, f"03_library/documents/transactions/{data['seq']:08d}-{envelope['sha256']}.json")
        atomic_blob(path, (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode())
        write_json_atomic(self.path, envelope)

    def recover(self) -> dict:
        with self.lock():
            snapshots = []
            for path in sorted((self.base / "transactions").glob("*.json")):
                try:
                    entry = json.loads(path.read_text())
                    if digest(entry["data"]) == entry["sha256"]:
                        snapshots.append(entry)
                except (ValueError, KeyError):
                    continue
            if not snapshots:
                raise DocumentError("NO_DOCUMENT_RECOVERY", "No valid document transaction snapshot found.")
            latest = max(snapshots, key=lambda e: e["data"]["seq"])
            write_json_atomic(self.path, latest)
            data = latest["data"]
            for attempt in data["attempts"].values():
                if attempt["result_status"] == "started":
                    attempt.update(result_status="interrupted", failure_code="INTERRUPTED_OPERATION", message="Operation did not commit a completed result; retry explicitly.")
            for log in data["parser_logs"]:
                if log["status"] == "started":
                    log.update(status="interrupted", error={"code": "INTERRUPTED_OPERATION", "message": "Parsing did not finalize; rerun explicitly."})
            self.commit(data, "document_recovery")
            return {"status": "recovered", "seq": data["seq"], "documents": len(data["documents"]), "phase_changes": False}

    def paper_ids(self) -> set[str]:
        lab = self.root / "DOCUMENT_LAB.json"
        if lab.exists():
            return set(json.loads(lab.read_text())["papers"])
        path = self.root / "03_library/PAPER_REGISTRY.csv"
        if not path.exists():
            return set()
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return {r["paper_id"] for r in csv.DictReader(handle) if r.get("paper_id")}
