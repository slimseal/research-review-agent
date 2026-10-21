# SourceAnchor v1

Design before implementation: anchors bind to document SHA-256, immutable parser artifact SHA-256, parser version and 1-based PDF page. Exact nonempty text matching creates one span (`machine_located`), multiple spans (`ambiguous`, no arbitrarily chosen location), or no span (`unresolved`, no invented page/quote locator). A valid explicit start/end span can disambiguate repeated text. Fingerprint is SHA-256 of exact UTF-8 text.

Read-only lookup rechecks PDF bytes, parse artifact checksum and current parser implementation version, then checks the saved page/span/fingerprint. Mismatch reports `stale` or `unresolved`; it never redirects to another document. A fresh parser version requires a fresh parse and new anchors; old parse artifacts are retained. `human_confirmed` requires a separate named human attestation, never generated automatically. Printed page is null unless separately confirmed by that human with a locator note. Human confirmation is a location assertion, not scientific verification.

Section/caption detections are candidate strings, not verified scholarly structure. Visitor blocks/coordinates are tentative hints; exact offsets in frozen page text are the supported locator. OCR, table cells, equations and true visual reading order are out of scope.
