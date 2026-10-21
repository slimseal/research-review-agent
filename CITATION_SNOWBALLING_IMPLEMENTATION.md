# Citation snowballing implementation

Baseline: Round 2D 88/88 tests passed before edits. Recoverable archive created outside the repository: `research-review-agent-round2d-before2e-20261017.tar.gz`, SHA-256 `54b9af3d4d892d2042b482811ecfd138551e90428a75581da509f00abee3d812`. No Git repository was initialized and nothing was uploaded.

## Reused infrastructure

Existing `scholarly/transport.py` (stable failure codes, bounded transport), `normalization.py`, `registry.py` (identity reconciliation/version handling), `store.py` (immutable response bodies and hashes), `state.py` (checksummed event snapshots/recovery), CLI and workflow registry. Document acquisition/parser/anchors were not rebuilt.

## Added modules

- `citations/contracts.py`: four versioned contracts and supported directions.
- `citations/providers.py`: small official endpoint connectors; raw-byte-first parsing; no SDK.
- `citations/pipeline.py`: seed management, bounded rounds, identity enrichment, ordered edges, checkpoint resume, replay, validation, reports and review.
- `citations/cli.py`: existing argparse subcommands, separate lab mode, honest exit/error states.
- `tests/test_citations.py`: fictional deterministic fixtures and mocked transport tests.

The existing workflow state contains `citation_data`; no second phase controller exists. `persist_state` snapshots every reserved request, raw response, processed record and page checkpoint. Citation files are derived views; export hashes in state detect stale/modified views. `citations-recover` reuses `recover_state`, then regenerates those views. Raw files are not reconstructed from memory. Paper Registry uses its existing atomic persistence; citation recovery does not recreate a deleted Registry or raw response.

Request processing: verify authorization/seed → reserve bounded request → fetch → store immutable body/hash → journal page → parse directed relations → resolve explicit identifiers against the existing Registry or Crossref metadata → register candidate/edge → checkpoint row → next page/seed. Metadata failure keeps earlier rows and current raw page. Every candidate has literal source data even when unresolved. No scientific judgment is made.

Official Phase 4 extends its existing artifacts/validation rules without changing phase order, prerequisite edges or the three hard gates. Phase 5 still needs acquisition review; Phase 6 still needs screening artifacts; parsing/reading still requires Gate 1. Phase 4 cannot pass on file headers or one successful request alone.

## Compatibility fixes

Registry export previously reset PDF path, fulltext flag, license, hash and extension/custom fields when metadata was added. Managed exports now preserve these fields. New IDs skip unmanaged legacy IDs. Citation resolution refuses to duplicate a matching legacy CSV DOI without explicit reconciliation. Existing metadata normalization and scientific Evidence Schemas remain unchanged. These are additive safeguards, not an automatic legacy migration.

## Deliberate limits

One writer per project; concurrent mutation is unsupported. Full state snapshots are appropriate for this bounded prototype, not an unbounded graph warehouse. OpenCitations returns unpaginated lists: the processing cap cannot limit the upstream response size; production bulk workloads need a separately reviewed streaming/export strategy. Related recommendations, fuzzy unstructured identity resolution, non-DOI OC seed adapters, authenticated reviewer identities and automatic unresolved-node reconciliation are not implemented. No screening/reading/evidence/synthesis/writing feature was added.
