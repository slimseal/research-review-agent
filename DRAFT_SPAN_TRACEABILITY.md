# Draft Span Traceability

`writing-trace --id SPAN-…` follows:

`Span → Claim/Gap → normalized links/parent claims → EvidenceItem → ReadingNote → SourceAnchor → DocumentVersion → PaperRecord`

Source locators, full document checksums, note revisions, link relations, citation identities and exact span text are retained. `writing-impact --id EV-…` returns current affected Claim/Gap and span IDs. The document text consists only of traced spans joined by two newlines; offsets are Unicode codepoints, not bytes or rendered-PDF coordinates.

Text edits change SHA-256 and draft versions. Claim/link/review changes alter source bindings. Evidence, notes, anchors, documents, protocol and screening changes are checked through the existing reading/synthesis dependencies. Bibliographic identity changes alter span bindings; bibliography-file changes invalidate reconciliation and the current audit. A brief revision invalidates its section. Unchanged spans retain IDs, text hashes and history.

Conservative limitation: upstream corpus-wide version checks can block an entire formal review after an evidence/protocol/screening change, even when reverse impact identifies a smaller direct set. Direct impact does not grant permission to bypass that global re-review. Whole-draft audit and final QC intentionally become stale when any audited draft section changes.

Partial drafting and partial audits are saved. `writing-recover` first restores the existing checksummed state journal, then rebuilds managed projections. It cannot reconstruct missing PDFs, sources or human decisions. Preserve unexpected edits before recovery; one writer per project. All prior versions and audit findings remain inspectable in WRITING_HISTORY.

Traceability proves neither interpretive correctness nor independent scientific validation.
