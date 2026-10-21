"""Internal worker. Never execute document actions, scripts, links or attachments."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def process(path: Path, extract: bool) -> dict:
    from pypdf import PdfReader, mult

    with path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            return {"error": "INVALID_PDF_SIGNATURE", "message": "File has no PDF signature."}
        handle.seek(max(0, path.stat().st_size - 1024))
        if b"%%EOF" not in handle.read():
            return {"error": "PDF_CORRUPT", "message": "PDF end marker is missing; truncated files are not accepted."}
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        return {"error": "PDF_ENCRYPTED", "message": "Encrypted PDFs are unsupported; supply an authorized unencrypted copy. No decryption attempted."}
    count = len(reader.pages)
    if not 0 < count <= 2000:
        return {"error": "PDF_PAGE_LIMIT", "message": "Page count is empty or exceeds 2000."}
    pages, sections, indicators = [], [], []
    extracted_characters = 0
    labels = reader.page_labels if "/PageLabels" in reader.trailer["/Root"] else [None] * count
    for number, page in enumerate(reader.pages, 1):
        # Resolve page objects even in integrity-only mode.
        width = float(page.mediabox.width)
        if not extract:
            continue
        fragments = []
        def visitor(text, cm, tm, font, size):
            if text.strip():
                transform = mult(tm, cm)
                fragments.append({"block_id": f"visitor-{len(fragments)+1}", "text": text, "x": round(transform[4], 3), "y": round(transform[5], 3), "coordinate_status": "unverified"})
        warnings = ["READING_ORDER_UNVERIFIED", "TABLES_EQUATIONS_NOT_INTERPRETED"]
        try:
            text = page.extract_text(visitor_text=visitor) or ""
            if len(text) > 2_000_000:
                raise ValueError("page text limit")
            state = "extracted" if text.strip() else "no_selectable_text_ocr_or_manual_required"
            if "\ufffd" in text:
                warnings.append("ENCODING_REPLACEMENT_CHARACTERS")
            left = any(f["x"] < width * .45 for f in fragments)
            right = any(f["x"] > width * .48 and len(f["text"].strip()) > 20 for f in fragments)
            if left and right:
                warnings.append("POSSIBLE_MULTI_COLUMN_OR_POSITIONED_TEXT")
            for line in text.splitlines():
                stripped = line.strip()
                if re.fullmatch(r"(?i)(?:\d+(?:\.\d+)*[ .]+)?(?:abstract|introduction|methods?|results?|discussion|conclusions?|references|summary|acknowledg(?:e)?ments)", stripped):
                    sections.append({"pdf_page": number, "text": stripped, "status": "candidate_heading"})
                if re.match(r"(?i)^(?:figure|fig\.|table)\s+\d+", stripped):
                    indicators.append({"pdf_page": number, "text": stripped[:200], "status": "candidate_caption_not_verified"})
        except Exception:
            text, fragments, state = "", [], "extraction_failed"
            warnings.append("PAGE_EXTRACTION_FAILED")
        pages.append({"pdf_page": number, "printed_page": None, "pdf_page_label": labels[number-1], "label_status": "metadata_only_not_verified_printed_page", "text": text, "blocks": fragments, "status": state, "warnings": warnings})
        extracted_characters += len(text)
        if extracted_characters > 8_000_000:
            return {"error": "PDF_TEXT_LIMIT", "message": "Extracted text exceeds the 8-million-character budget; process a smaller authorized source manually."}
    if not extract:
        return {"page_count": count, "status": "integrity_checked"}
    statuses = [p["status"] for p in pages]
    status = "parsed" if all(s == "extracted" for s in statuses) else ("ocr_or_manual_required" if all(s == "no_selectable_text_ocr_or_manual_required" for s in statuses) else "parsing_incomplete")
    return {"page_count": count, "pages": pages, "status": status, "sections": sections, "figure_table_indicators": indicators}


def main():
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (40, 40))
            if sys.platform.startswith("linux"):
                resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        except (ImportError, ValueError, OSError):
            pass
        result = process(Path(sys.argv[1]), sys.argv[2] == "extract")
    except Exception as error:
        from pypdf.errors import PdfReadError
        result = {"error": "PDF_CORRUPT" if isinstance(error, PdfReadError) else "PARSER_FAILED", "message": "PDF processing failed; inspect the authorized source and parser. No substitute text was generated."}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
