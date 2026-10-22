from __future__ import annotations

import csv
import json
import re
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..constants import CSV_FIELDS
from ..state import utc_now, write_json_atomic
from .contracts import IdentityMatch, MetadataResolution, PaperCandidate, PaperRecord
from .normalization import identity_fingerprint, normalize_doi, normalize_person, normalize_title
from .store import DiscoveryStore


REGISTRY_VERSION = "1.0.0"


@dataclass(frozen=True)
class RegistrationResult:
    status: str
    paper_id: str | None
    identity_match: IdentityMatch
    metadata_resolution: MetadataResolution | None


def _source_key(provider: str, provider_record_id: str) -> str:
    return f"{provider}:{provider_record_id}"


def biomedical_identifiers(source_ids):
    """Exact, namespaced aliases only. Never treat a bare number as a global ID."""
    result = set()
    for name, value in source_ids.items():
        name = name.casefold()
        value = str(value).strip().rstrip("/").rsplit("/", 1)[-1]
        if name in {"pmid", "pubmed"} and value.isdigit():
            result.add("pmid:" + value)
        if name in {"pmcid", "pmc", "pubmedcentral"} and re.fullmatch(r"PMC\d+", value, re.I):
            result.add("pmcid:" + value.upper())
    return result


def _blank_registry() -> dict[str, Any]:
    return {
        "registry_version": REGISTRY_VERSION,
        "next_sequence": 1,
        "records": {},
        "provider_index": {},
        "doi_index": {},
        "fingerprint_index": {},
        "title_index": {},
    }


class PaperRegistry:
    def __init__(self, project_root: Path, store: DiscoveryStore | None = None) -> None:
        self.project_root = project_root.resolve()
        self.store = store or DiscoveryStore(self.project_root)
        self.path = self.project_root / "03_library/PAPER_IDENTITIES.json"
        self.data = self._load()
        # Rebuild in memory from authoritative provenance; legacy registries remain readable.
        self.biomedical_index = {}
        for pid, record in self.data["records"].items():
            for origin in record.get("provenance", []):
                self._index_biomedical(pid, origin.get("source_ids", {}))

    def _index_biomedical(self, paper_id, source_ids):
        for identifier in biomedical_identifiers(source_ids):
            self.biomedical_index.setdefault(identifier, set()).add(paper_id)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return _blank_registry()
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("registry_version") != REGISTRY_VERSION:
            raise ValueError(f"UNSUPPORTED_PAPER_REGISTRY_VERSION: {value.get('registry_version')}")
        return value

    def save(self) -> None:
        write_json_atomic(self.path, self.data)
        self._write_registry_csv()
        self._write_bibliography()

    def register(self, candidate: PaperCandidate) -> RegistrationResult:
        now = utc_now()
        source_key = _source_key(candidate.provider, candidate.provider_record_id)
        fingerprint = identity_fingerprint(candidate)
        normalized_title = normalize_title(candidate.title)
        doi = normalize_doi(candidate.doi)
        records: dict[str, dict[str, Any]] = self.data["records"]
        competing: list[str] = []
        separate_version = False
        method: str | None = None
        matched_id = self.data["provider_index"].get(source_key)
        if matched_id:
            method = "provider_identifier"
        elif doi and doi in self.data["doi_index"]:
            matched_id = self.data["doi_index"][doi]
            method = "verified_doi"
        elif fingerprint:
            fingerprint_matches = list(dict.fromkeys(self.data["fingerprint_index"].get(fingerprint, [])))
            if len(fingerprint_matches) == 1:
                possible = records[fingerprint_matches[0]]
                existing_doi = normalize_doi(possible.get("doi"))
                if doi and existing_doi and doi != existing_doi:
                    if candidate.version_type != "unknown" or possible.get("version_type") != "unknown":
                        separate_version = True
                    else:
                        competing = fingerprint_matches
                else:
                    matched_id = fingerprint_matches[0]
                    method = "title_first_author_year"
            elif len(fingerprint_matches) > 1:
                competing = fingerprint_matches
        elif normalized_title:
            competing = list(dict.fromkeys(self.data["title_index"].get(normalized_title, [])))

        if matched_id and method == "title_first_author_year" and (
                candidate.version_type == "preprint" or records[matched_id].get("version_type") == "preprint"):
            # A deposited version is not interchangeable with a journal manifestation or another version.
            matched_id, separate_version = None, True

        identifier_matches = set().union(*(self.biomedical_index.get(key, set())
            for key in biomedical_identifiers(candidate.source_ids)))
        if identifier_matches:
            if len(identifier_matches) != 1 or (matched_id and matched_id not in identifier_matches):
                competing = sorted(identifier_matches | ({matched_id} if matched_id else set()))
                matched_id = None
            else:
                possible_id = next(iter(identifier_matches))
                existing_doi = normalize_doi(records[possible_id].get("doi"))
                if doi and existing_doi and doi != existing_doi:
                    competing, matched_id = [possible_id], None
                elif candidate.version_type == "preprint" and records[possible_id].get("version_type") != "preprint":
                    competing, matched_id = [possible_id], None
                else:
                    matched_id, method, competing = possible_id, "exact_biomedical_identifier", []

        aggregate_ambiguity = candidate.relations.get("identity_ambiguity")
        if aggregate_ambiguity and matched_id:
            competing = sorted(set(competing + [matched_id]))
            matched_id = None
        if aggregate_ambiguity or (competing and not matched_id):
            identity = IdentityMatch(
                candidate_provider=candidate.provider,
                candidate_provider_record_id=candidate.provider_record_id,
                search_run_id=candidate.search_run_id,
                matched_paper_id=None,
                method="ambiguous_metadata",
                status="review_required",
                confidence="uncertain",
                candidate_fingerprint=fingerprint,
                competing_paper_ids=competing,
                notes=[str(aggregate_ambiguity or "Candidate was not merged because more than one identity interpretation remains possible.")],
                decided_at=now,
            )
            self.store.append_identity_match(identity.to_dict())
            return RegistrationResult("ambiguous", None, identity, None)

        resolution: MetadataResolution | None = None
        if matched_id:
            resolution = self._merge_record(matched_id, candidate)
            status = "duplicate"
            confidence = "high" if method in {"provider_identifier", "verified_doi", "exact_biomedical_identifier"} else "moderate"
        else:
            matched_id = self._create_record(candidate)
            status = "created"
            method = "new_version_identity" if separate_version else "new_identity"
            confidence = "high" if doi or fingerprint else "low"

        identity = IdentityMatch(
            candidate_provider=candidate.provider,
            candidate_provider_record_id=candidate.provider_record_id,
            search_run_id=candidate.search_run_id,
            matched_paper_id=matched_id,
            method=method or "new_identity",
            status=status,
            confidence=confidence,
            candidate_fingerprint=fingerprint,
            competing_paper_ids=[],
            notes=[],
            decided_at=now,
        )
        self.store.append_identity_match(identity.to_dict())
        if resolution:
            self.store.append_metadata_resolution(resolution.to_dict())
        self.save()
        return RegistrationResult(status, matched_id, identity, resolution)

    def _new_paper_id(self) -> str:
        value = int(self.data["next_sequence"])
        # Legacy/manual rows are not automatically migrated, but their IDs are reserved.
        path = self.project_root / "03_library/PAPER_REGISTRY.csv"
        reserved = set(self.data["records"])
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reserved.update(row.get("paper_id", "") for row in csv.DictReader(handle))
        while f"P{value:07d}" in reserved:
            value += 1
        self.data["next_sequence"] = value + 1
        return f"P{value:07d}"

    def _create_record(self, candidate: PaperCandidate) -> str:
        paper_id = self._new_paper_id()
        provenance = self._provenance(candidate)
        record = PaperRecord(
            paper_id=paper_id,
            title=candidate.title,
            authors=list(candidate.authors),
            publication_year=candidate.publication_year,
            source_title=candidate.source_title,
            doi=normalize_doi(candidate.doi),
            landing_page_url=candidate.landing_page_url,
            work_type=candidate.work_type,
            version_type=candidate.version_type,
            provider_ids={candidate.provider: [candidate.provider_record_id]},
            search_run_ids=[candidate.search_run_id],
            provenance=[provenance],
            first_registered_at=candidate.retrieved_at,
            last_seen_at=candidate.retrieved_at,
        )
        self.data["records"][paper_id] = record.to_dict()
        self._index_record(paper_id, candidate)
        self._link_possible_versions(paper_id, candidate)
        return paper_id

    def _index_record(self, paper_id: str, candidate: PaperCandidate) -> None:
        self._index_biomedical(paper_id, candidate.source_ids)
        self.data["provider_index"][_source_key(candidate.provider, candidate.provider_record_id)] = paper_id
        doi = normalize_doi(candidate.doi)
        if doi:
            self.data["doi_index"][doi] = paper_id
        fingerprint = identity_fingerprint(candidate)
        if fingerprint:
            values = self.data["fingerprint_index"].setdefault(fingerprint, [])
            if paper_id not in values:
                values.append(paper_id)
        title = normalize_title(candidate.title)
        if title:
            values = self.data["title_index"].setdefault(title, [])
            if paper_id not in values:
                values.append(paper_id)

    def _link_possible_versions(self, paper_id: str, candidate: PaperCandidate) -> None:
        title_key = normalize_title(candidate.title)
        related = [value for value in self.data["title_index"].get(title_key, []) if value != paper_id]
        current = self.data["records"][paper_id]
        for related_id in related:
            other = self.data["records"][related_id]
            if current.get("doi") and normalize_doi(current.get("doi")) == normalize_doi(other.get("doi")):
                continue
            if candidate.version_type == "unknown" and other.get("version_type") == "unknown":
                continue
            if related_id not in current["related_versions"]:
                current["related_versions"].append(related_id)
            if paper_id not in other["related_versions"]:
                other["related_versions"].append(paper_id)

    def _merge_record(self, paper_id: str, candidate: PaperCandidate) -> MetadataResolution:
        record = self.data["records"][paper_id]
        field_map = {
            "title": candidate.title,
            "authors": list(candidate.authors),
            "publication_year": candidate.publication_year,
            "source_title": candidate.source_title,
            "doi": normalize_doi(candidate.doi),
            "landing_page_url": candidate.landing_page_url,
            "work_type": candidate.work_type,
            "version_type": candidate.version_type,
        }
        decisions: dict[str, dict[str, Any]] = {}
        conflicts: list[str] = []
        for field_name, candidate_value in field_map.items():
            existing_value = record.get(field_name)
            if existing_value in (None, "", [], "unknown") and candidate_value not in (None, "", [], "unknown"):
                record[field_name] = candidate_value
                decision = "filled_from_candidate"
            elif candidate_value in (None, "", [], "unknown"):
                decision = "kept_existing_candidate_missing"
            elif self._equivalent(field_name, existing_value, candidate_value):
                decision = "confirmed"
            else:
                decision = "conflict_kept_existing"
                conflicts.append(field_name)
                note = f"{field_name} differs between canonical record and {candidate.provider}:{candidate.provider_record_id}."
                if note not in record["conflict_notes"]:
                    record["conflict_notes"].append(note)
            decisions[field_name] = {
                "existing": existing_value,
                "candidate": candidate_value,
                "decision": decision,
            }
        provider_ids = record["provider_ids"].setdefault(candidate.provider, [])
        if candidate.provider_record_id not in provider_ids:
            provider_ids.append(candidate.provider_record_id)
        if candidate.search_run_id not in record["search_run_ids"]:
            record["search_run_ids"].append(candidate.search_run_id)
        provenance = self._provenance(candidate)
        provenance_key = (provenance["provider"], provenance["provider_record_id"], provenance["search_run_id"])
        existing_keys = {
            (item["provider"], item["provider_record_id"], item["search_run_id"])
            for item in record["provenance"]
        }
        if provenance_key not in existing_keys:
            record["provenance"].append(provenance)
        record["last_seen_at"] = candidate.retrieved_at
        provider_count = len([name for name, identifiers in record["provider_ids"].items() if identifiers])
        record["verification_status"] = "conflict" if record["conflict_notes"] else ("verified_cross_provider" if provider_count > 1 else "single_provider")
        self._index_record(paper_id, candidate)
        return MetadataResolution(
            resolution_id=f"MR-{uuid.uuid4().hex[:12].upper()}",
            paper_id=paper_id,
            candidate_provider=candidate.provider,
            candidate_provider_record_id=candidate.provider_record_id,
            field_decisions=decisions,
            conflict_fields=conflicts,
            verification_status=record["verification_status"],
            resolved_at=utc_now(),
        )

    @staticmethod
    def _equivalent(field_name: str, existing: Any, candidate: Any) -> bool:
        if field_name in {"title", "source_title"}:
            return normalize_title(str(existing)) == normalize_title(str(candidate))
        if field_name == "authors":
            return [normalize_person(str(item)) for item in existing] == [normalize_person(str(item)) for item in candidate]
        if field_name == "doi":
            return normalize_doi(str(existing)) == normalize_doi(str(candidate))
        return existing == candidate

    @staticmethod
    def _provenance(candidate: PaperCandidate) -> dict[str, Any]:
        return {
            "provider": candidate.provider,
            "provider_record_id": candidate.provider_record_id,
            "raw_response_path": candidate.raw_response_path,
            "raw_record_index": candidate.raw_record_index,
            "search_run_id": candidate.search_run_id,
            "retrieved_at": candidate.retrieved_at,
            "source_ids": dict(candidate.source_ids),
            "relations": dict(candidate.relations),
            "work_type": candidate.work_type,
            "version_type": candidate.version_type,
            "abstract_available": bool(candidate.abstract),
        }

    def _write_registry_csv(self) -> None:
        path = self.project_root / "03_library/PAPER_REGISTRY.csv"
        fields = list(CSV_FIELDS["paper_registry"])
        preserved: dict[str, dict[str, str]] = {}
        previous: dict[str, dict[str, str]] = {}
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fields += [field for field in (reader.fieldnames or []) if field not in fields]
                for row in reader:
                    previous[row.get("paper_id", "")] = row
                    if row.get("paper_id") and row["paper_id"] not in self.data["records"]:
                        preserved[row["paper_id"]] = row
        generated: list[dict[str, str]] = []
        for paper_id in sorted(self.data["records"]):
            record = self.data["records"][paper_id]
            old = previous.get(paper_id, {})
            extension = json.loads(old.get("extension_json") or "{}")
            extension.update({
                "metadata_verification_status": record["verification_status"],
                "conflict_notes": record["conflict_notes"],
                "provider_ids": record["provider_ids"],
                "search_run_ids": record["search_run_ids"],
                "provenance": record["provenance"],
                "version_type": record["version_type"],
                "related_versions": record["related_versions"],
                "citation_provenance": record.get("citation_provenance", []),
            })
            extension.setdefault("full_text_status", "not_acquired_round2c")
            generated.append({
                **old,
                "paper_id": paper_id,
                "title": record["title"],
                "authors": "; ".join(record["authors"]),
                "year": str(record["publication_year"] or ""),
                "journal": record["source_title"] or "",
                "doi": record["doi"] or "",
                "url": record["landing_page_url"] or (f"https://doi.org/{record['doi']}" if record["doi"] else ""),
                "pdf_path": old.get("pdf_path", ""),
                "paper_type": record["work_type"] or "",
                "retrieval_source": "metadata_only:" + ",".join(sorted(record["provider_ids"])),
                "retrieval_date": (record["last_seen_at"] or "")[:10],
                "fulltext_available": old.get("fulltext_available", "false"),
                "license": old.get("license", ""),
                "sha256": old.get("sha256", ""),
                "example_data": old.get("example_data", "false"),
                "extension_json": json.dumps(extension, ensure_ascii=False, sort_keys=True),
            })
        rows = list(preserved.values()) + generated
        self._write_csv_atomic(path, fields, rows)

    def _write_bibliography(self) -> None:
        path = self.project_root / "03_library/references.bib"
        begin = "% BEGIN RRA MANAGED BIBLIOGRAPHY"
        end = "% END RRA MANAGED BIBLIOGRAPHY"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if begin in existing and end in existing:
            prefix = existing.split(begin, 1)[0].rstrip()
            suffix = existing.split(end, 1)[1].lstrip()
        else:
            prefix = existing.rstrip()
            suffix = ""
        entries = [self._bib_entry(self.data["records"][paper_id]) for paper_id in sorted(self.data["records"])]
        managed = begin + "\n\n" + "\n\n".join(entries) + "\n\n" + end
        content = "\n\n".join(part for part in (prefix, managed, suffix) if part).rstrip() + "\n"
        self._write_text_atomic(path, content)

    @staticmethod
    def _bib_escape(value: str) -> str:
        return value.replace("\\", "\\textbackslash{} ").replace("&", "\\&").replace("{", "\\{").replace("}", "\\}")

    def _bib_entry(self, record: dict[str, Any]) -> str:
        entry_type = "article" if record.get("source_title") else "misc"
        fields = [
            ("title", self._bib_escape(record["title"])),
            ("author", " and ".join(self._bib_escape(name) for name in record["authors"])),
            ("year", str(record["publication_year"] or "")),
            ("journal", self._bib_escape(record.get("source_title") or "")),
            ("doi", record.get("doi") or ""),
            ("url", record.get("landing_page_url") or ""),
        ]
        rendered = [f"  {key} = {{{value}}}" for key, value in fields if value]
        return f"@{entry_type}{{{record['paper_id']},\n" + ",\n".join(rendered) + "\n}"

    @staticmethod
    def _write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
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

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
