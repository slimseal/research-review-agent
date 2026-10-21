"""Run with a freshly installed Python, preferably `python -I`, outside the repo.

Writes only to a new specified output folder. Synthetic data, no network or research.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-parser-missing", action="store_true")
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    records = []
    def run(*command, expected=0):
        process = subprocess.run([sys.executable, "-I", "-m", "research_review_agent", *map(str, command)], cwd=root, capture_output=True, text=True)
        records.append({"arguments": list(map(str, command)), "exit_code": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
        (root / "CLI_RESULTS.json").write_text(json.dumps(records, indent=2))
        assert process.returncode == expected, records[-1]
        return json.loads(process.stdout) if process.stdout else None
    run("capabilities")
    run("document-schema")
    review = root / "review"
    run("init", "--question", "Synthetic portability test only", "--output", review)
    run("validate", "--project", review)
    run("next", "--project", review)
    run("phase-context", "--project", review, "--phase", "7")
    run("gate", "--project", review, "--phase", "7", expected=2)
    (review / ".review/state.json").write_text("intentional synthetic corruption")
    run("recover", "--project", review)
    run("validate", "--project", review)
    catalog = root / "catalog.json"
    catalog.write_text(json.dumps([{"paper_id": "SYNTHETIC", "title": "Synthetic fixture only", "authors": ["Test generator"], "year": 2099, "identity_source": "synthetic software test", "example_data": True}]))
    auth = root / "authorization.json"
    auth.write_text(json.dumps({"access_basis": "researcher_asserted_authorized", "asserted_by": "Synthetic test operator", "reason": "Generated software fixture only"}))
    lab = root / "lab"
    run("document-lab-init", "--project", lab, "--catalog", catalog)
    pdf = root / "synthetic.pdf"
    if args.expect_parser_missing:
        pdf.write_bytes(b"%PDF-not-a-real-document")
        result = run("document-import", "--project", lab, "--paper-id", "SYNTHETIC", "--file", pdf, "--authorization", auth, expected=2)
        assert result["error"]["code"] == "PARSER_UNAVAILABLE"
    else:
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 50 740 Td (Synthetic portability fixture only) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.write(pdf)
        imported = run("document-import", "--project", lab, "--paper-id", "SYNTHETIC", "--file", pdf, "--authorization", auth)
        document_id = imported["document"]["document_id"]
        run("document-parse", "--project", lab, "--document-id", document_id)
        anchor = run("anchor-create", "--project", lab, "--document-id", document_id, "--quote", "Synthetic portability fixture only", "--pdf-page", 1)
        run("anchor-lookup", "--project", lab, "--anchor-id", anchor["anchor_id"])
        run("documents-validate", "--project", lab)
        (lab / "03_library/documents/manifest.json").write_text("intentional synthetic corruption")
        run("documents-recover", "--project", lab)
        run("documents-validate", "--project", lab)
        run("document-parse", "--project", lab, "--document-id", document_id)
    run("document-import", "--project", review, "--paper-id", "SYNTHETIC", "--file", pdf, "--authorization", auth, expected=2)
    print(json.dumps({"passed": len(records), "parser_missing_mode": args.expect_parser_missing, "log": str(root / "CLI_RESULTS.json")}, indent=2))


if __name__ == "__main__":
    main()
