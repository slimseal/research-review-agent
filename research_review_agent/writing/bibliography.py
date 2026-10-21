"""Conservative BibTeX reconciliation. No network, fuzzy merges or metadata overwrites."""
import re
from ..scholarly.registry import PaperRegistry


def parse_bib(text):
    entries, errors = [], []
    # Balanced delimiters handle nested TeX groups. Macros/concatenation are explicitly unsupported.
    pos = 0
    while match := re.search(r"@(\w+)\s*\{", text[pos:]):
        start = pos + match.end()
        depth, quoted, escaped, end = 1, False, False, start
        while end < len(text) and depth:
            c = text[end]
            if not escaped:
                if c == '"':
                    quoted = not quoted
                if not quoted:
                    depth += (c == "{") - (c == "}")
            escaped = c == "\\" and not escaped
            end += 1
        if depth:
            errors.append("MALFORMED_BIBTEX")
            break
        body = text[start:end - 1]
        pos = end
        if match.group(1).lower() == "comment":
            continue
        if match.group(1).lower() in {"string", "preamble"} or "," not in body:
            errors.append("UNSUPPORTED_BIBTEX_MACRO")
            continue
        key, fields_text = body.split(",", 1)
        fields, idx = {}, 0
        while idx < len(fields_text):
            field = re.match(r"[\s,]*([\w-]+)\s*=\s*", fields_text[idx:])
            if not field:
                if fields_text[idx:].strip(" \n\r\t,"):
                    errors.append("MALFORMED_BIBTEX_FIELD:" + key.strip())
                break
            idx += field.end()
            begin = idx
            delim = fields_text[idx:idx + 1]
            if delim in {'{', '"'}:
                idx += 1
                inner, level, esc = idx, 1, False
                while idx < len(fields_text):
                    c = fields_text[idx]
                    if not esc:
                        if delim == '{':
                            level += (c == '{') - (c == '}')
                        elif c == '"':
                            level = 0
                    esc = c == "\\" and not esc
                    if level == 0:
                        break
                    idx += 1
                if level:
                    errors.append("UNBALANCED_BIBTEX_FIELD:" + key.strip())
                    break
                value = fields_text[inner:idx]
                idx += 1
            else:
                while idx < len(fields_text) and fields_text[idx] != ',':
                    idx += 1
                value = fields_text[begin:idx].strip()
                if not value.isdigit():
                    errors.append("UNSUPPORTED_BIBTEX_VALUE:" + key.strip())
            fields[field.group(1).lower()] = value
        entries.append({"key": key.strip(), "fields": fields, "raw": text[start - match.end():end]})
    return entries, errors


def normalized(value):
    return re.sub(r"\s+", " ", str(value or "").replace(r"\&", "&").replace(r"\{", "{").replace(r"\}", "}")).strip().casefold()


def doi(value):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", normalized(value)).rstrip(".")


def reconcile(root, citations, supported_papers):
    registry = PaperRegistry(root)
    records = registry.data["records"]
    path = root / "03_library/references.bib"
    entries, errors = parse_bib(path.read_text() if path.exists() else "")
    findings, by_key, seen_doi, seen_title = [], {}, {}, {}
    def issue(code, key, severity="error"):
        findings.append({"type": code, "citation_key": key, "severity": severity})
    for error in errors:
        issue(error, "")
    for entry in entries:
        key, fields = entry["key"], entry["fields"]
        if key in by_key:
            issue("DUPLICATE_BIBLIOGRAPHY_KEY", key)
        by_key[key] = entry
        for field, seen, norm in (("doi", seen_doi, doi), ("title", seen_title, normalized)):
            value = norm(fields.get(field))
            if value and value in seen and seen[value] != key:
                issue("DUPLICATE_REFERENCE_" + field.upper(), key)
            seen[value] = key
        if key not in citations:
            issue("UNUSED_BIBLIOGRAPHY_ENTRY", key, "warning")
        if key in records:
            expected, _ = parse_bib(registry._bib_entry(records[key]))
            for field in ("title", "author", "year", "doi"):
                left, right = fields.get(field), expected[0]["fields"].get(field)
                if (doi(left) if field == "doi" else normalized(left)) != (doi(right) if field == "doi" else normalized(right)):
                    issue(field.upper() + "_MISMATCH", key)
    for key in citations:
        if key not in records:
            issue("UNKNOWN_CITATION_KEY", key)
            continue
        if key not in by_key:
            issue("MISSING_BIBLIOGRAPHY_ENTRY", key)
        if key not in supported_papers:
            issue("EXCLUDED_OR_UNSUPPORTED_SOURCE", key)
        rec = records[key]
        if not all(rec.get(k) for k in ("title", "authors", "publication_year")):
            issue("INCOMPLETE_METADATA", key)
        if rec.get("conflict_notes") or rec.get("conflicts") or rec.get("identity_status") == "ambiguous" or rec.get("verification_status") == "conflict":
            issue("AMBIGUOUS_BIBLIOGRAPHIC_IDENTITY", key)
    return {"valid": not any(f["severity"] == "error" for f in findings), "findings": findings,
            "citation_keys": sorted(citations), "metadata_only": True, "semantic_verification": False,
            "bibtex": "\n\n".join(registry._bib_entry(records[k]) for k in sorted(citations) if k in records)}
