from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..state import canonical_json, write_json_atomic
from .contracts import ProviderResponse, SearchRun


class RawResponseIntegrityError(RuntimeError):
    pass


class DiscoveryStore:
    """Project-local immutable raw store plus replaceable derived indexes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.discovery_dir = self.root / "02_discovery"
        self.library_dir = self.root / "03_library"
        self.runs_dir = self.discovery_dir / "search_runs"

    def ensure(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        (self.discovery_dir / "raw/openalex").mkdir(parents=True, exist_ok=True)
        (self.discovery_dir / "raw/crossref").mkdir(parents=True, exist_ok=True)
        self.library_dir.mkdir(parents=True, exist_ok=True)

    def run_path(self, search_run_id: str) -> Path:
        return self.runs_dir / f"{search_run_id}.json"

    def save_run(self, run: SearchRun) -> None:
        self.ensure()
        write_json_atomic(self.run_path(run.search_run_id), run.to_dict())
        self._upsert_jsonl(self.discovery_dir / "SEARCH_RUNS.jsonl", "search_run_id", run.to_dict())

    def load_run(self, search_run_id: str) -> SearchRun:
        value = json.loads(self.run_path(search_run_id).read_text(encoding="utf-8"))
        return SearchRun(**value)

    def write_raw_response(self, provider: str, search_run_id: str, page_number: int, body: bytes) -> tuple[str, str]:
        self.ensure()
        directory = self.discovery_dir / "raw" / provider / search_run_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"page-{page_number:06d}.json"
        checksum = hashlib.sha256(body).hexdigest()
        if path.exists():
            existing_checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            if existing_checksum != checksum:
                raise RawResponseIntegrityError(f"RAW_RESPONSE_COLLISION: {path}")
            return self.relative(path), checksum
        with path.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        return self.relative(path), checksum

    def verify_raw_response(self, relative_path: str, expected_sha256: str) -> bytes:
        path = self.resolve_relative(relative_path)
        body = path.read_bytes()
        actual = hashlib.sha256(body).hexdigest()
        if actual != expected_sha256:
            raise RawResponseIntegrityError(
                f"RAW_RESPONSE_CHECKSUM_MISMATCH: {relative_path}; expected={expected_sha256}; actual={actual}"
            )
        return body

    def append_provider_response(self, response: ProviderResponse) -> None:
        self._append_jsonl(self.discovery_dir / "PROVIDER_RESPONSES.jsonl", response.to_dict())

    def append_identity_match(self, value: dict[str, Any]) -> None:
        self._append_jsonl(self.discovery_dir / "IDENTITY_MATCHES.jsonl", value)

    def append_metadata_resolution(self, value: dict[str, Any]) -> None:
        self._append_jsonl(self.discovery_dir / "METADATA_RESOLUTIONS.jsonl", value)

    def provider_responses(self, search_run_id: str) -> list[dict[str, Any]]:
        path = self.discovery_dir / "PROVIDER_RESPONSES.jsonl"
        if not path.exists():
            return []
        responses = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                value = json.loads(line)
                if value.get("search_run_id") == search_run_id:
                    responses.append(value)
        return sorted(responses, key=lambda item: int(item["page_number"]))

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def resolve_relative(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"UNSAFE_PROJECT_PATH: {relative_path}")
        return candidate

    @staticmethod
    def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _upsert_jsonl(path: Path, key: str, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        found = False
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get(key) == value.get(key):
                        rows.append(value)
                        found = True
                    else:
                        rows.append(row)
        if not found:
            rows.append(value)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(canonical_json(row) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
