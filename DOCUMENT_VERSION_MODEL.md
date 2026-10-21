# Document model v1 (Round 2D)

Design recorded before implementation. Additive contracts live in `research_review_agent/documents/contracts.py`; document contract version is `1.0.0`, independent of evidence Schema v1/v2. No existing research data or paper IDs are migrated.

`Paper identity (existing CSV) → DocumentVersion (many) → ParsedDocument (parser-specific) → SourceAnchor (many)`.

- DocumentVersion: document/paper identity (nullable paper only with explicit unresolved assertion), document type, version kind (version_of_record, accepted_manuscript, preprint, supplementary, unknown), source URL, method/provider/time, access basis, license status/URL, redistribution permission, managed relative path, SHA-256/bytes/MIME/pages, parsing status/version and verification status. Related document IDs are descriptive, never identity merges.
- AcquisitionAttempt: immutable operation ID, paper/provider/candidate, timestamp, HTTP/result/failure/access statuses, byte count/hash, warnings, rights assertion and final URL/redirect provenance. Errors never create successful DocumentVersions.
- ParsedDocument: document ID/hash, parser name/version, timestamp, page count, per-page extracted text and visitor fragments, candidate headings/captions, warnings/limitations. PDF page is 1-based. Printed page defaults null; PDF page labels are unverified hints, not printed-page evidence.
- SourceAnchor: document and paper IDs, PDF hash, parse artifact hash/version, page and exact character span, nullable printed page/section/block/caption, short-text fingerprint, verification state. Offset is into the recorded parser text, not a visual paragraph number.

Content-addressed PDF paths prevent replacement; identical bytes for the same paper/version deduplicate, differing bytes create separate versions. Identical bytes assigned a different identity/version require separate document records. Paper Registry is read-only to these tools, including legacy CSV-only identities without DOI. Its old `pdf_path`/availability fields are not a document-level source of truth and are not silently rewritten.

Document records use an atomic manifest and immutable checksummed transaction snapshots for recovery, not a second research workflow controller. In-progress attempt records survive interruptions. Recovery marks interrupted operations explicitly; it does not infer success or advance phases. Official phase decisions remain exclusively in the existing workflow controller.
