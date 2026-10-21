"""FICTIONAL fixtures only; no research data or human approvals are created."""
import json
import os
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest.mock import patch

from research_review_agent import journal_tail as tail
from research_review_agent.screening.pipeline import ScreeningPipeline
from research_review_agent.state import (
    canonical_json, load_state, new_state, persist_state, recover_state, write_json_atomic,
)


def legacy(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return json.loads(next(line for line in reversed(lines) if line.strip()))


class JournalTailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / ".review/events.jsonl"
        self.path.parent.mkdir()
        tail._tails.clear()

    def tearDown(self):
        tail._tails.clear()
        self.temp.cleanup()

    def state(self):
        s = new_state("fictional-journal-test", "FICTIONAL SOFTWARE TEST ONLY", "test")
        persist_state(self.root, s, "fixture")
        return s

    def pipe(self):
        # Only exercise the actual journal/state comparison, not fake phase approval.
        p = object.__new__(ScreeningPipeline)
        p.root = self.root
        return p

    def test_stream_equivalent_to_old_splitlines(self):
        for data in [
            b'{"v":1}\n{"v":2}\n', b'{"v":1}\r\n \r\n{"v":2}\r',
            '{"v":"中文"}\n'.encode(), b'\n\t {"v":3} \n \n',
            '{"v":1}\u2028{"v":2}\u2029  '.encode(),
            b'{"v":1}\x0b{"v":2}\x1c{"v":3}',
            b'{"v":1}', b'', b' \n', b'{"v":1}\n{"broken":',
            b'\xff\n{"v":2}\n', '{"v":"bad\u2028separator"}\n'.encode(),
        ]:
            with self.subTest(data=data[:40]):
                self.path.write_bytes(data)
                try:
                    expected = legacy(self.path)
                except Exception as exc:
                    with self.assertRaises(type(exc)):
                        tail.last_event(self.path)
                else:
                    self.assertEqual(expected, tail.last_event(self.path))

    def test_no_whole_file_read_and_warm_cache(self):
        self.path.write_text('{"v":1}\n', encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=AssertionError("whole-file read")), \
             patch.object(tail, "_stream_last_line", wraps=tail._stream_last_line) as scan:
            self.assertEqual(tail.last_event(self.path), {"v": 1})
            self.assertEqual(tail.last_event(self.path), {"v": 1})
            self.assertEqual(scan.call_count, 1)

    def test_known_append_reuses_prefix_without_rewriting_history(self):
        s = self.state()
        tail.last_event(self.path)
        prefix = self.path.read_bytes()
        with patch.object(tail, "_stream_last_line", wraps=tail._stream_last_line) as scan:
            for _ in range(3):
                persist_state(self.root, s, "fixture_append")
                self.pipe().check_journal()
            self.assertEqual(scan.call_count, 0)
        self.assertTrue(self.path.read_bytes().startswith(prefix))
        self.assertEqual(legacy(self.path), tail.last_event(self.path))

    def test_unknown_append_forces_complete_scan(self):
        self.path.write_text('{"v":1}\n', encoding="utf-8")
        tail.last_event(self.path)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write('{"v":2}\n')
        with patch.object(tail, "_stream_last_line", wraps=tail._stream_last_line) as scan:
            self.assertEqual(tail.last_event(self.path), {"v": 2})
            self.assertEqual(scan.call_count, 1)

    def test_old_prefix_corruption_even_with_restored_mtime_is_detected(self):
        self.path.write_bytes(b'{"v":1}\n{"v":2}\n')
        tail.last_event(self.path)
        old = self.path.stat()
        with self.path.open("r+b") as handle:
            handle.write(b"\xff")
        os.utime(self.path, ns=(old.st_atime_ns, old.st_mtime_ns))
        with self.assertRaises(UnicodeDecodeError):
            tail.last_event(self.path)

    def test_prefix_change_before_known_append_cannot_be_cached_away(self):
        s = self.state()
        tail.last_event(self.path)
        with self.path.open("r+b") as handle:
            handle.write(b"\xff")
        persist_state(self.root, s, "fixture_append_after_external_damage")
        with self.assertRaises(UnicodeDecodeError):
            self.pipe().check_journal()

    def test_truncate_and_same_size_replace_invalidate(self):
        self.path.write_bytes(b'{"v":1}\n{"v":2}\n')
        tail.last_event(self.path)
        self.path.write_bytes(b'{"v":3}\n')
        self.assertEqual(tail.last_event(self.path), {"v": 3})
        other = self.root / "replacement"
        other.write_bytes(b'{"v":4}\n')
        other.replace(self.path)
        self.assertEqual(tail.last_event(self.path), {"v": 4})

    def test_partial_final_line_is_not_silently_ignored(self):
        self.state()
        tail.last_event(self.path)
        with self.path.open("a") as handle:
            handle.write('{"interrupted":')
        with self.assertRaises(json.JSONDecodeError):
            self.pipe().check_journal()

    def test_unterminated_prefix_append_retains_old_failure(self):
        s = self.state()
        self.path.write_bytes(self.path.read_bytes().rstrip(b"\n"))
        tail.last_event(self.path)
        persist_state(self.root, s, "fixture_append")
        with self.assertRaises(json.JSONDecodeError):
            self.pipe().check_journal()

    def test_unicode_separator_in_new_event_not_hidden_by_append_cache(self):
        s = self.state()
        tail.last_event(self.path)
        s["fictional"] = "a\u2028b"
        persist_state(self.root, s, "fixture_separator")
        with self.assertRaises(json.JSONDecodeError):
            legacy(self.path)
        with self.assertRaises(json.JSONDecodeError):
            self.pipe().check_journal()

    def test_persisted_state_rehashed_even_when_tail_is_cached(self):
        self.state()
        self.pipe().check_journal()
        s = load_state(self.root)
        s["research_question"] = "FICTIONAL conflicting revision"
        write_json_atomic(self.root / ".review/state.json", s)
        with self.assertRaisesRegex(ValueError, "STATE_JOURNAL_MISMATCH"):
            self.pipe().check_journal()

    def test_last_event_payload_checksum_still_checked(self):
        self.state()
        self.pipe().check_journal()
        value = legacy(self.path)
        value["state"]["research_question"] = "FICTIONAL corrupt payload"
        self.path.write_text(canonical_json(value) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "STATE_JOURNAL_MISMATCH"):
            self.pipe().check_journal()

    def test_returned_value_is_not_mutable_cache_state(self):
        self.path.write_text('{"nested":{"v":1}}\n', encoding="utf-8")
        returned = tail.last_event(self.path)
        returned["nested"]["v"] = 99
        self.assertEqual(tail.last_event(self.path)["nested"]["v"], 1)

    def test_cache_loss_rebuilds_from_authoritative_bytes(self):
        self.state()
        expected = tail.last_event(self.path)
        tail._tails.clear()
        self.assertEqual(tail.last_event(self.path), expected)
        self.pipe().check_journal()

    def test_interruption_after_journal_fsync_then_recovery(self):
        s = self.state()
        self.pipe().check_journal()
        original = write_json_atomic
        def interrupt(path, value):
            if path == self.root / ".review/state.json":
                raise OSError("FICTIONAL interruption before state replacement")
            return original(path, value)
        with patch("research_review_agent.state.write_json_atomic", side_effect=interrupt):
            with self.assertRaises(OSError):
                persist_state(self.root, s, "fixture_interrupted")
        with self.assertRaisesRegex(ValueError, "STATE_JOURNAL_MISMATCH"):
            self.pipe().check_journal()
        recovered = recover_state(self.root)
        self.assertEqual(recovered["seq"], s["seq"])
        self.pipe().check_journal()

    def test_change_during_scan_fails_closed(self):
        self.path.write_text('{"v":1}\n', encoding="utf-8")
        original = tail._stream_last_line
        def changed(handle):
            result = original(handle)
            with self.path.open("a") as out:
                out.write('{"v":2}\n')
            return result
        with patch.object(tail, "_stream_last_line", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "CHANGED_DURING_READ"):
                tail.last_event(self.path)

    def test_cache_is_bounded_and_eviction_does_not_change_result(self):
        paths = []
        for i in range(tail._LIMIT + 3):
            path = self.root / str(i)
            path.write_text(json.dumps({"v": i}) + "\n")
            tail.last_event(path)
            paths.append(path)
        self.assertLessEqual(len(tail._tails), tail._LIMIT)
        self.assertEqual(tail.last_event(paths[0]), {"v": 0})

    def test_large_log_has_bounded_python_allocation(self):
        record = (json.dumps({"fictional_test_only": "x" * (256 * 1024)}) + "\n").encode()
        with self.path.open("wb") as out:
            for _ in range(256):
                out.write(record)
        tracemalloc.start()
        try:
            value = tail.last_event(self.path)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(len(value["fictional_test_only"]), 256 * 1024)
        self.assertLess(peak, 8 * 1024 * 1024)


class ScreeningCacheIntegrationTests(unittest.TestCase):
    def setUp(self):
        import test_screening
        self.fixture = test_screening.ScreeningTests()
        self.fixture.setUp()
        self.p = self.fixture.p

    def tearDown(self):
        self.fixture.tearDown()

    def test_replay_keeps_decision_and_history_exact(self):
        from test_screening import proposal
        packet = self.fixture.context()
        value = proposal(self.p, packet)
        first = self.p.propose(value)
        history = canonical_json(self.p.data["decisions"])
        event_bytes = (self.p.root / ".review/events.jsonl").read_bytes()
        replay = self.p.propose(value)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["decision_id"], first["decision_id"])
        self.assertEqual(canonical_json(self.p.data["decisions"]), history)
        self.assertEqual((self.p.root / ".review/events.jsonl").read_bytes(), event_bytes)
        self.assertTrue(self.p.validate()["valid"])

    def test_warm_cache_does_not_hide_source_packet_tamper(self):
        decision = self.fixture.submit()
        self.assertTrue(self.p.validate()["valid"])
        ref = self.p.data["packets"][decision["packet_id"]]
        with (self.p.root / ref["path"]).open("a") as handle:
            handle.write(" ")
        self.assertFalse(self.p.validate()["valid"])
        self.assertFalse(self.p.gate()["allowed"])

    def test_warm_cache_does_not_hide_export_tamper(self):
        self.fixture.submit()
        with (self.p.root / "04_screening/SCREENING_MASTER.csv").open("a") as handle:
            handle.write("fictional tamper\n")
        with self.assertRaisesRegex(ValueError, "EXPORT_CHANGED"):
            self.fixture.context()

    def test_version_conflict_still_rejected(self):
        from test_screening import config, proposal
        packet = self.fixture.context()
        self.p.register(config(self.p), "FICTIONAL revision")
        with self.assertRaisesRegex(ValueError, "NEW_CONTEXT_REQUIRED"):
            self.p.propose(proposal(self.p, packet))

    def test_interrupted_export_recovery_keeps_history(self):
        from test_screening import proposal
        packet = self.fixture.context()
        with patch.object(self.p, "export", side_effect=OSError("FICTIONAL interrupted export")):
            with self.assertRaises(OSError):
                self.p.propose(proposal(self.p, packet))
        history = canonical_json(self.p.data["decisions"])
        self.p.recover()
        self.assertEqual(canonical_json(self.p.data["decisions"]), history)
        self.assertTrue(self.p.validate()["valid"])
        self.assertFalse(self.p.gate()["allowed"])
