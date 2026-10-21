"""Synthetic PDF bytes for software validation only; no real papers/findings."""
from io import BytesIO


def pdf_bytes(*, text="SYNTHETIC SOFTWARE TEST ONLY", columns=False, scanned=False, encrypted=False, printed_label=False):
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, TextStringObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 12 Tf 50 740 Td ({escaped}) Tj ET\nBT /F1 12 Tf 50 700 Td (Introduction) Tj ET\n".encode()
    if columns:
        content += b"BT /F1 12 Tf 50 650 Td (Synthetic left column text for layout checks.) Tj ET\nBT /F1 12 Tf 330 650 Td (Synthetic right column text for layout checks.) Tj ET\n"
    if printed_label:
        content += b"BT /F1 10 Tf 300 20 Td (41) Tj ET\n"
        writer._root_object[NameObject("/PageLabels")] = DictionaryObject({NameObject("/Nums"): ArrayObject([NumberObject(0), DictionaryObject({NameObject("/S"): NameObject("/D"), NameObject("/St"): NumberObject(41)})])})
    if scanned:
        picture = DecodedStreamObject()
        picture.set_data(b"\x00\xff\x00\xff")
        picture.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"), NameObject("/Width"): NumberObject(2), NameObject("/Height"): NumberObject(2), NameObject("/ColorSpace"): NameObject("/DeviceGray"), NameObject("/BitsPerComponent"): NumberObject(8)})
        resources[NameObject("/XObject")] = DictionaryObject({NameObject("/I1"): writer._add_object(picture)})
        content = b"q 200 0 0 200 50 500 cm /I1 Do Q\n"
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata({"/Title": "Synthetic test fixture - not scientific evidence"})
    if encrypted:
        writer.encrypt("synthetic-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
