# Evidence-to-source traceability

Trace: EvidenceItem → exact ReadingNote revision → SourceAnchor → DocumentVersion → lawful local PDF → canonical PaperRecord.

Use `evidence-inspect --id <evidence-id> --project <path>`. The read-only result includes record/history, anchors, resolved PDF path/page/text, machine_located versus human_confirmed, stale reasons and unresolved links. `reading-inspect` and `anchor-lookup` resolve the earlier links.

## Dependency checks

Each record pins Protocol content hash, paper identity hash, document identity/version/access basis/SHA, parse reference and checksum, screening decision reference, and source-anchor snapshots. Evidence additionally pins its reading-note revision. Extraction closure pins the current note and entire per-paper evidence revision set.

Unknown paper/document/anchor IDs, wrong paper/document bindings, checksum mismatches, stale parser versions and unresolved anchors cannot be submitted as supported evidence. Changing the Protocol, eligible version, source PDF, parser or anchor makes dependent records stale; changing a note stales its evidence, and changed evidence invalidates its coverage closure. An unrelated evidence item does not stale another item's source trace.

Historical records remain auditable but are not counted as current. Even a human location confirmation changing the anchor snapshot conservatively requires dependent revalidation.

## Recovery and limits

reading-recover uses the existing workflow journal and regenerates projections. It cannot recreate missing source PDFs, parse artifacts or anchors, and does not manufacture semantic approval. Document recovery still uses the existing document transactions. Preserve unexpected manual projection edits before recovery.

Hash linkage establishes consistency, not trustworthy authorship, semantic entailment, authentic human identity, or immutable adversary-proof storage. One writer is required. Full state snapshots are suitable for this MVP, not claimed to scale to unrestricted corpora or concurrent writers.
