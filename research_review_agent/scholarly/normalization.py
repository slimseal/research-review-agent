from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

from .contracts import PaperCandidate


DOI_PATTERN = re.compile(r"10\.\d{4,9}/\S+", flags=re.IGNORECASE)


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = unquote(str(value)).strip()
    cleaned = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" \t\r\n<>\"'")
    while cleaned and cleaned[-1] in ".,;:":
        cleaned = cleaned[:-1]
    match = DOI_PATTERN.fullmatch(cleaned)
    return cleaned.casefold() if match else None


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", html.unescape(str(value))).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def normalize_person(value: str | None) -> str:
    return normalize_title(value)


def identity_fingerprint(candidate: PaperCandidate) -> str | None:
    title = normalize_title(candidate.title)
    first_author = normalize_person(candidate.authors[0] if candidate.authors else None)
    if not title or not first_author or candidate.publication_year is None:
        return None
    return f"{title}|{first_author}|{candidate.publication_year}"


def _openalex_abstract(index: Any) -> str | None:
    if not isinstance(index, dict) or not index:
        return None
    positions: list[tuple[int, str]] = []
    for word, raw_positions in index.items():
        if not isinstance(word, str) or not isinstance(raw_positions, list):
            continue
        for position in raw_positions:
            if isinstance(position, int) and position >= 0:
                positions.append((position, word))
    if not positions:
        return None
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def _first_text(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _crossref_year(record: dict[str, Any]) -> int | None:
    for field_name in ("published-print", "published-online", "published", "issued", "created"):
        value = record.get(field_name)
        if not isinstance(value, dict):
            continue
        date_parts = value.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
            year = date_parts[0][0]
            if isinstance(year, int):
                return year
    return None


def _clean_abstract(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split()) or None


def _openalex_version(record: dict[str, Any]) -> str:
    primary = record.get("primary_location")
    if isinstance(primary, dict):
        version = primary.get("version")
        mapping = {
            "submittedVersion": "preprint",
            "acceptedVersion": "accepted_manuscript",
            "publishedVersion": "published_version",
        }
        if version in mapping:
            return mapping[version]
    if record.get("type") == "preprint":
        return "preprint"
    return "unknown"


def _crossref_version(record: dict[str, Any]) -> str:
    subtype = str(record.get("subtype") or "").casefold()
    work_type = str(record.get("type") or "").casefold()
    if "preprint" in subtype or work_type in {"posted-content", "preprint"}:
        return "preprint"
    if work_type in {"journal-article", "proceedings-article", "book-chapter", "book"}:
        return "published_version"
    return "unknown"


@dataclass
class NormalizationResult:
    candidates: list[PaperCandidate] = field(default_factory=list)
    rejected_count: int = 0
    warnings: list[str] = field(default_factory=list)


def normalize_openalex_records(
    records: list[dict[str, Any]],
    *,
    search_run_id: str,
    retrieved_at: str,
    raw_response_path: str,
) -> NormalizationResult:
    result = NormalizationResult()
    for index, record in enumerate(records):
        identifier = record.get("id")
        title = record.get("display_name") or record.get("title")
        if not isinstance(identifier, str) or not identifier.strip() or not isinstance(title, str) or not title.strip():
            result.rejected_count += 1
            result.warnings.append(f"MALFORMED_RECORD:openalex:{index}")
            continue
        authors: list[str] = []
        for authorship in record.get("authorships", []) if isinstance(record.get("authorships"), list) else []:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author")
            if isinstance(author, dict) and isinstance(author.get("display_name"), str):
                authors.append(author["display_name"].strip())
        primary = record.get("primary_location") if isinstance(record.get("primary_location"), dict) else {}
        source = primary.get("source") if isinstance(primary.get("source"), dict) else {}
        ids = record.get("ids") if isinstance(record.get("ids"), dict) else {}
        doi = normalize_doi(record.get("doi") or ids.get("doi"))
        source_ids = {"openalex": identifier}
        for key in ("pmid", "pmcid", "mag"):
            value = ids.get(key)
            if value is not None:
                source_ids[key] = str(value)
        year = record.get("publication_year")
        candidate = PaperCandidate(
            provider="openalex",
            provider_record_id=identifier,
            search_run_id=search_run_id,
            retrieved_at=retrieved_at,
            raw_response_path=raw_response_path,
            raw_record_index=index,
            title=title.strip(),
            authors=authors,
            publication_year=year if isinstance(year, int) else None,
            source_title=source.get("display_name") if isinstance(source.get("display_name"), str) else None,
            doi=doi,
            landing_page_url=primary.get("landing_page_url") if isinstance(primary.get("landing_page_url"), str) else None,
            work_type=str(record.get("type")) if record.get("type") is not None else None,
            version_type=_openalex_version(record),
            abstract=_openalex_abstract(record.get("abstract_inverted_index")),
            source_ids=source_ids,
        )
        if candidate.abstract is None:
            result.warnings.append(f"MISSING_ABSTRACT:openalex:{identifier}")
        if candidate.doi is None:
            result.warnings.append(f"MISSING_DOI:openalex:{identifier}")
        result.candidates.append(candidate)
    return result


def normalize_crossref_records(
    records: list[dict[str, Any]],
    *,
    search_run_id: str,
    retrieved_at: str,
    raw_response_path: str,
) -> NormalizationResult:
    result = NormalizationResult()
    for index, record in enumerate(records):
        doi = normalize_doi(record.get("DOI"))
        title = _first_text(record.get("title"))
        provider_id = doi or str(record.get("URL") or "").strip()
        if not provider_id or not title:
            result.rejected_count += 1
            result.warnings.append(f"MALFORMED_RECORD:crossref:{index}")
            continue
        authors: list[str] = []
        raw_authors = record.get("author") if isinstance(record.get("author"), list) else []
        for author in raw_authors:
            if not isinstance(author, dict):
                continue
            literal = author.get("name")
            if isinstance(literal, str) and literal.strip():
                authors.append(literal.strip())
                continue
            name = " ".join(
                item.strip()
                for item in (str(author.get("given") or ""), str(author.get("family") or ""))
                if item.strip()
            )
            if name:
                authors.append(name)
        relations: dict[str, list[str]] = {}
        raw_relation = record.get("relation")
        if isinstance(raw_relation, dict):
            for relation_type, values in raw_relation.items():
                if not isinstance(values, list):
                    continue
                identifiers = []
                for value in values:
                    if isinstance(value, dict) and value.get("id"):
                        identifiers.append(str(value["id"]))
                if identifiers:
                    relations[str(relation_type)] = identifiers
        candidate = PaperCandidate(
            provider="crossref",
            provider_record_id=provider_id,
            search_run_id=search_run_id,
            retrieved_at=retrieved_at,
            raw_response_path=raw_response_path,
            raw_record_index=index,
            title=title,
            authors=authors,
            publication_year=_crossref_year(record),
            source_title=_first_text(record.get("container-title")),
            doi=doi,
            landing_page_url=str(record.get("URL")) if record.get("URL") else None,
            work_type=str(record.get("type")) if record.get("type") is not None else None,
            version_type=_crossref_version(record),
            abstract=_clean_abstract(record.get("abstract")),
            source_ids={"crossref": provider_id},
            relations=relations,
        )
        if candidate.abstract is None:
            result.warnings.append(f"MISSING_ABSTRACT:crossref:{provider_id}")
        if candidate.doi is None:
            result.warnings.append(f"MISSING_DOI:crossref:{provider_id}")
        result.candidates.append(candidate)
    return result


def normalize_provider_records(
    provider: str,
    records: list[dict[str, Any]],
    *,
    search_run_id: str,
    retrieved_at: str,
    raw_response_path: str,
) -> NormalizationResult:
    if provider in {"eric", "arxiv", "openaire"}:
        return normalize_open_records(provider, records, search_run_id=search_run_id,
                                      retrieved_at=retrieved_at, raw_response_path=raw_response_path)
    if provider in {"pubmed", "europepmc", "semantic_scholar"}:
        return normalize_public_records(provider, records, search_run_id=search_run_id,
                                        retrieved_at=retrieved_at, raw_response_path=raw_response_path)
    if provider == "openalex":
        return normalize_openalex_records(
            records,
            search_run_id=search_run_id,
            retrieved_at=retrieved_at,
            raw_response_path=raw_response_path,
        )
    if provider == "crossref":
        return normalize_crossref_records(
            records,
            search_run_id=search_run_id,
            retrieved_at=retrieved_at,
            raw_response_path=raw_response_path,
        )
    raise ValueError(f"UNSUPPORTED_PROVIDER: {provider}")


def normalize_public_records(provider, records, *, search_run_id, retrieved_at, raw_response_path):
    result = NormalizationResult()
    for index, row in enumerate(records):
        title = _first_text(row.get("title"))
        if provider == "europepmc":
            identifier = f"{row.get('source')}:{row.get('id')}" if row.get("source") and row.get("id") else None
            author_rows = (row.get("authorList") or {}).get("author", [])
            authors = [r["fullName"] for r in author_rows if isinstance(r, dict) and r.get("fullName")]
            year = row.get("pubYear")
            journal = ((row.get("journalInfo") or {}).get("journal") or {}).get("title")
            doi = normalize_doi(row.get("doi"))
            abstract = _clean_abstract(row.get("abstractText"))
            ids = {k: str(row[k]) for k in ("pmid", "pmcid") if row.get(k)}
            if row.get("source") == "MED" and str(row.get("id", "")).isdigit():
                ids.setdefault("pmid", str(row["id"]))
            url = f"https://europepmc.org/article/{row['source']}/{row['id']}" if identifier else None
            types = (row.get("pubTypeList") or {}).get("pubType", [])
        elif provider == "semantic_scholar":
            identifier = row.get("paperId")
            authors = [r["name"] for r in row.get("authors", []) if isinstance(r, dict) and r.get("name")]
            year, journal = row.get("year"), row.get("venue")
            external = row.get("externalIds") or {}
            doi = normalize_doi(external.get("DOI"))
            abstract = _clean_abstract(row.get("abstract"))
            ids = {str(k): str(v) for k, v in external.items() if v is not None}
            url, types = row.get("url"), row.get("publicationTypes") or []
        else:
            identifier = row.get("id")
            authors, year, journal = row.get("authors", []), row.get("year"), row.get("journal")
            doi, abstract = normalize_doi(row.get("doi")), _clean_abstract(row.get("abstract"))
            ids = {"pmid": str(identifier)} if identifier else {}
            if row.get("pmcid"):
                ids["pmcid"] = row["pmcid"]
            url, types = f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/" if identifier else None, row.get("publication_types", [])
        if not identifier or not title:
            result.rejected_count += 1
            result.warnings.append(f"MALFORMED_RECORD:{provider}:{index}")
            continue
        ids[provider] = str(identifier)
        candidate = PaperCandidate(provider, str(identifier), search_run_id, retrieved_at, raw_response_path,
                                   index, title, authors, int(year) if str(year).isdigit() else None, journal or None,
                                   doi, url, "; ".join(types) or None, "unknown", abstract, source_ids=ids)
        result.candidates.append(candidate)
        if not abstract:
            result.warnings.append(f"MISSING_ABSTRACT:{provider}:{identifier}")
        if not doi:
            result.warnings.append(f"MISSING_DOI:{provider}:{identifier}")
    return result


def normalize_open_records(provider, records, *, search_run_id, retrieved_at, raw_response_path):
    result = NormalizationResult()
    for index, row in enumerate(records):
        identifier = str(row.get("id") or "")
        ids, relations = {provider: identifier}, {}
        doi, journal, version = None, None, "unknown"
        if provider == "eric":
            title = _first_text(row.get("title"))
            authors = row.get("author") or []
            if isinstance(authors, str):
                authors = [authors]
            year = row.get("publicationdateyear")
            journal = _first_text(row.get("source"))
            abstract = _clean_abstract(_first_text(row.get("description")))
            urls = row.get("url") or []
            urls = [urls] if isinstance(urls, str) else urls
            # Only explicitly DOI-formatted URLs/fields, never a guessed DOI from a title.
            doi = normalize_doi(_first_text(row.get("doi"))) or next(
                (d for u in urls if (d := normalize_doi(u))), None)
            kind = row.get("publicationtype") or []
            kind = "; ".join(kind) if isinstance(kind, list) else str(kind)
            url = f"https://eric.ed.gov/?id={identifier}"
            relations = {"provider_peerreviewed": row.get("peerreviewed"), "source_urls": urls}
        elif provider == "arxiv":
            title, authors = _first_text(row.get("title")), row.get("authors") or []
            year = str(row.get("published") or "")[:4]
            abstract, url = _clean_abstract(row.get("abstract")), row.get("url")
            kind, version = "preprint", "preprint"
            # arXiv's DOI can identify a later publication, not this exact deposited version.
            relations = {"published_doi": normalize_doi(row.get("doi")), "arxiv_version": row.get("version"),
                         "updated": row.get("updated"), "journal_reference": row.get("journal_ref"),
                         "categories": row.get("categories", [])}
        elif provider == "openaire":
            title = _first_text(row.get("mainTitle"))
            authors = [a["fullName"] for a in (row.get("authors") or []) if isinstance(a, dict) and a.get("fullName")]
            year = str(row.get("publicationDate") or "")[:4]
            abstract = _clean_abstract("\n".join(row.get("descriptions") or []))
            pids = row.get("pids") or []
            # Multiple distinct DOI values require identity review; retain all upstream IDs.
            dois = sorted({d for p in pids if p.get("scheme", "").lower() == "doi" and (d := normalize_doi(p.get("value")))})
            doi = dois[0] if len(dois) == 1 else None
            for scheme in ("pmid", "pmc", "pmcid"):
                values = {str(p["value"]) for p in pids if p.get("scheme", "").lower() == scheme and p.get("value")}
                if len(values) == 1:
                    ids["pmcid" if scheme == "pmc" else scheme] = values.pop()
            kind = row.get("type")
            url = f"https://explore.openaire.eu/search/result?id={identifier}"
            journal = (row.get("container") or {}).get("name")
            relations = {"original_ids": row.get("originalIds", []), "pids": pids,
                         "instances": row.get("instances", []), "provider_type": kind,
                         "provider_is_peer_reviewed": row.get("isPeerReviewed")}
            id_groups = {}
            for p in pids:
                scheme = str(p.get("scheme", "")).lower()
                scheme = "pmcid" if scheme == "pmc" else scheme
                if scheme in {"doi", "pmid", "pmcid"} and p.get("value"):
                    id_groups.setdefault(scheme, set()).add(str(p["value"]).casefold())
            ambiguous = sorted(k for k, values in id_groups.items() if len(values) > 1)
            if ambiguous:
                relations["identity_ambiguity"] = "Multiple distinct primary identifiers in Graph aggregate: " + ", ".join(ambiguous)
            if len(dois) > 1:
                result.warnings.append(f"MULTIPLE_DOIS_REQUIRE_REVIEW:{provider}:{identifier}")
        else:
            raise ValueError("UNSUPPORTED_PROVIDER")
        if not identifier or not title:
            result.rejected_count += 1
            result.warnings.append(f"MALFORMED_RECORD:{provider}:{index}")
            continue
        result.candidates.append(PaperCandidate(provider, identifier, search_run_id, retrieved_at,
            raw_response_path, index, title, authors, int(year) if str(year).isdigit() else None,
            journal, doi, url, kind or None, version, abstract, source_ids=ids, relations=relations))
        if not abstract:
            result.warnings.append(f"MISSING_ABSTRACT:{provider}:{identifier}")
        if not doi:
            result.warnings.append(f"MISSING_DOI:{provider}:{identifier}")
    return result
