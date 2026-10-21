"""Bounded-memory last-event reader; the journal remains authoritative.

Cold reads consume the ENTIRE UTF-8 file, preserving the old read_text/splitlines
semantics (including errors in earlier bytes). This is not a history validator:
as before, screening compares the last event payload with persisted state.

Only this process's unchanged file or a confirmed persist_state append may reuse
a checked prefix. Any other stat change causes a full streaming read. Nothing is
stored on disk. This retains the existing single-writer/local-filesystem contract;
stat metadata is not cryptographic authentication or concurrent-write support.
"""
from __future__ import annotations

import json
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

_LIMIT = 8


def fingerprint(stat: os.stat_result) -> tuple[int, ...]:
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@dataclass(frozen=True)
class _Tail:
    signature: tuple[int, ...]
    text: str
    newline_terminated: bool


_tails: OrderedDict[Path, _Tail] = OrderedDict()


def _remember(path: Path, tail: _Tail) -> None:
    _tails[path] = tail
    _tails.move_to_end(path)
    while len(_tails) > _LIMIT:
        _tails.popitem(last=False)


def _stream_last_line(handle: TextIO) -> tuple[str, bool]:
    last = None
    physical = ""
    for physical in handle:
        # str.splitlines also recognizes Unicode separators, unlike file iteration.
        # Preserve that behavior, even when a separator appears inside JSON text.
        for line in physical.splitlines():
            if line.strip():
                last = line
    if last is None:
        raise StopIteration
    return last, physical.endswith("\n")


def last_event(path: Path) -> dict:
    """Read-only; never trust the cache for state, approval, or evidence checks."""
    path = Path(path).resolve()
    try:
        with path.open(encoding="utf-8") as handle:
            before = fingerprint(os.fstat(handle.fileno()))
            cached = _tails.get(path)
            if cached is not None and cached.signature == before:
                text, terminated = cached.text, cached.newline_terminated
            else:
                text, terminated = _stream_last_line(handle)
            value = json.loads(text)
            after = fingerprint(os.fstat(handle.fileno()))
            if after != before or fingerprint(path.stat()) != after:
                raise ValueError("SCREENING_JOURNAL_CHANGED_DURING_READ")
        _remember(path, _Tail(after, text, terminated))
        return value
    except BaseException:
        _tails.pop(path, None)
        raise


def remember_append(path: Path, before: os.stat_result, after: os.stat_result, text: str) -> None:
    """Best-effort notification ONLY after persist_state writes/flushes/fsyncs.

Reuse a previously read prefix, never an unknown external append. Changed,
truncated/replaced, unterminated, noncanonical or concurrently extended files
fall back to last_event's complete streaming read. No cache failure affects
the authoritative journal/state transaction.
    """
    path = Path(path).resolve()
    try:
        cached = _tails.get(path)
        lines = text.splitlines()
        encoded_size = len(text.replace("\n", os.linesep).encode("utf-8"))
        if (
            cached is None
            or cached.signature != fingerprint(before)
            or not cached.newline_terminated
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or after.st_size != before.st_size + encoded_size
            or fingerprint(path.stat()) != fingerprint(after)
            or len(lines) != 1
            or not text.endswith("\n")
        ):
            _tails.pop(path, None)
            return
        # Immutable serialized bytes, not a reference to the caller's mutable state.
        _remember(path, _Tail(fingerprint(after), lines[0], True))
    except (OSError, ValueError, UnicodeError):
        _tails.pop(path, None)
