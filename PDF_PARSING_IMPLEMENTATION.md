# PDF parsing implementation

Optional dependency: `pypdf==6.20.1`, BSD-3-Clause, reviewed and installed in an isolated venv. Core remains stdlib-only. Reviewed sources: [installation](https://pypdf.readthedocs.io/en/stable/user/installation.html), [extraction limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html), [license](https://github.com/py-pdf/pypdf/blob/main/LICENSE). No third-party acquisition script or Skill is copied or invoked by the package.

Integrity checks PDF header/EOF, strict pypdf structure/page-tree access, encryption, and 1–2000 pages. This is not complete malicious-file sanitization. Extraction uses a subprocess with 45-second parent timeout, CPU limits where supported, and Linux-only address-space limit. PDF size limit: 25 MiB. Mac/Windows lack equivalent memory caps here; this is not a hardened OS sandbox. DNS latency is OS-controlled; connect/read work has a 20-second budget. Hostile/high-volume deployment needs additional isolation.

Public `pypdf.mult` combines matrices for tentative visitor coordinates. Text is frozen in checksummed JSON. Parser identity includes library and implementation version. Fresh parse JSON timestamps are not promised byte-identical; frozen-artifact replay is checksum-verified and idempotent. Original document bytes remain unchanged.

`parsed` means every page yielded nonempty selectable text, not accuracy, reading-order correctness or scientific understanding. Empty text returns `ocr_or_manual_required` (could be blank/vector-only, not necessarily scanned). Mixed failures return `parsing_incomplete`. Corrupt/encrypted/timeout/parser failures return explicit errors, never replacement text. Started and failed operations are logged.

PDF indexes are 1-based. Page labels are metadata hints; printed_page stays null until separate human confirmation. Heading/caption patterns are candidates only. Multi-column detection is a heuristic with false positives/negatives; every page warns that order is unverified. OCR, structured tables, equations, figure interpretation, semantic paragraphs and robust complex layouts remain unsupported. Coordinates are unverified; anchors use exact offsets in frozen page text.

`document-schema` exports JSON Schema. `documents-validate` checks contracts, paper references, managed paths, checksums and anchor resolution. It does not populate or migrate Evidence Schema v1/v2.
