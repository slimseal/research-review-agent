# Screening journal read optimization

The workflow journal remains the source of truth. This change does not migrate,
compact, rewrite, or remove events or state backups. No screening criteria,
proposal, source-validation, human-review, or Gate requirement changes.

## What changed

Previously `ScreeningPipeline.check_journal()` decoded and split the entire event
file on every call, although it deserialized only the last nonblank record. The
same operation occurred repeatedly during context creation, proposal submission
and validation. Each native context/proposal also retains its existing state and
projection transactions, including full snapshots and backups.

`journal_tail.last_event()` now streams a cold journal. Within one process, it
retains at most eight immutable last-record strings. Reuse requires an unchanged
device/inode/size/mtime/ctime fingerprint. `persist_state()` can notify this cache
only after a known append has been flushed and fsynced, against an already
validated prefix and the exact expected byte growth.

Unknown appends, file replacement, truncation, external changes or loss of the
cache cause another full streaming read. No persistent index, database, or
sidecar file is introduced. Cached dictionaries are never returned by reference:
the last record is deserialized again, and both its state checksum and the
persisted state checksum are checked every time. All source, projection,
criteria, approval and upstream validations continue to run.

## Guarantees and limits

- Cold reads remain O(journal bytes), with memory proportional to the largest
  physical line/record rather than the whole journal.
- Warm reads in the same process avoid rescanning validated historical bytes.
  A separate CLI process starts cold. A sequential batch using the native
  `ScreeningPipeline` interface can reuse the process-local cache.
- Existing malformed UTF-8 and last-record errors remain errors. This is not a
  new validator of every historical JSON object: the old screening check also
  parsed only the last record. Existing recovery still checks journal snapshots.
- The existing single-writer/local-filesystem contract remains mandatory.
  File fingerprints are not cryptographic authentication and do not provide
  concurrent-writer coordination or protection against privileged filesystem
  tampering.
- A crash between journal fsync and state replacement still produces a mismatch
  until existing recovery runs. The cache cannot authorize a mismatching state.
- Full state snapshots, backups and export transactions still accumulate. This
  patch deliberately does not change their format or remove historical data.

## Offline verification

`tests/test_journal_tail.py` uses fictional temporary fixtures. It covers legacy
read equivalence, cache invalidation, corruption, interrupted commits, recovery,
duplicate submissions, version conflicts, unchanged source/export checks and a
64 MiB allocation test. It creates no real human approvals.

`scripts/benchmark_screening_journal.py` supports:

- `--operation check`: two read-only checks of an existing project/snapshot;
- `--operation proposal`: one native context-plus-proposal operation, only in an
  isolated screening lab with no existing decision for its first candidate.

Select the before/after implementation using `PYTHONPATH`, and use separate
fresh processes. The script reports actual wall time and OS `ru_maxrss` for the
whole worker, including startup and validation. These are not estimates or
`tracemalloc` measurements. Keep fictional benchmark copies outside real
research projects. A benchmark does not establish scientific screening validity
or waive a failing regression test.
