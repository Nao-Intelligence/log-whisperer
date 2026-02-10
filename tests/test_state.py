"""Tests for log_whisperer.state — PatternRecord, PatternDB, BaselineState, and helpers.

Covers serialization round-trips for PatternRecord, file-backed CRUD
operations for PatternDB (including malformed-data resilience), baseline
learning activation/persistence, and the ``parse_duration`` /
``fmt_local_ts`` utility functions.
"""

import json
import time

import pytest

from log_whisperer.state import (
    PatternRecord,
    PatternDB,
    BaselineState,
    parse_duration,
    fmt_local_ts,
)


# ---------------------------------------------------------------------------
# PatternRecord
# ---------------------------------------------------------------------------
class TestPatternRecord:
    """Verify serialization and deserialization of individual pattern records."""

    def _make_record(self):
        """Helper: build a representative PatternRecord for reuse across tests."""
        return PatternRecord(
            h="abc123",
            first_seen=1000,
            last_seen=2000,
            total_seen=5,
            severity="ERROR",
            pattern="test <N>",
            sample="test 42",
        )

    def test_to_dict_round_trip(self):
        """Serializing a record with ``to_dict()`` and deserializing it back
        with ``from_dict()`` should produce an identical record."""
        rec = self._make_record()
        d = rec.to_dict()
        rec2 = PatternRecord.from_dict(d)
        assert rec == rec2

    def test_from_dict_coerces_ints(self):
        """``from_dict`` should coerce string values to int for numeric fields
        (first_seen, last_seen, total_seen) to handle JSON data that was
        stored or edited as strings."""
        d = {
            "h": "abc",
            "first_seen": "100",   # string, not int
            "last_seen": "200",
            "total_seen": "3",
            "severity": "INFO",
            "pattern": "p",
            "sample": "s",
        }
        rec = PatternRecord.from_dict(d)
        assert rec.first_seen == 100
        assert rec.last_seen == 200
        assert rec.total_seen == 3


# ---------------------------------------------------------------------------
# PatternDB
# ---------------------------------------------------------------------------
class TestPatternDB:
    """Verify JSON-lines database creation, persistence, and reset semantics."""

    def test_init_creates_parent_and_file(self, tmp_path):
        """Constructing a PatternDB should create all missing parent directories
        and an empty DB file if none exists."""
        p = tmp_path / "sub" / "deep" / "patterns.db"
        PatternDB(p)
        assert p.exists()
        assert p.read_text() == ""

    def test_load_empty_file(self, db_path):
        """Loading from a freshly-created (empty) DB file should return an
        empty dict — no records yet."""
        db = PatternDB(db_path)
        assert db.load() == {}

    def test_save_then_load_round_trips(self, db_path):
        """Records saved to disk should be identical when loaded back."""
        db = PatternDB(db_path)
        rec = PatternRecord("h1", 1, 2, 3, "INFO", "pat", "sam")
        db.save({"h1": rec})
        loaded = db.load()
        assert "h1" in loaded
        assert loaded["h1"] == rec

    def test_malformed_json_lines_skipped(self, db_path):
        """If a DB file contains corrupt lines (e.g. partial writes), those
        lines should be silently skipped and valid records still loaded."""
        db = PatternDB(db_path)
        rec = PatternRecord("h1", 1, 2, 3, "INFO", "pat", "sam")
        db.save({"h1": rec})
        # Simulate corruption by appending invalid JSON
        with open(db_path, "a") as f:
            f.write("NOT VALID JSON\n")
        loaded = db.load()
        assert len(loaded) == 1
        assert "h1" in loaded

    def test_records_sorted_by_hash(self, db_path):
        """Saved records should appear in lexicographic order of their hash
        key so output is deterministic across runs."""
        db = PatternDB(db_path)
        records = {
            "zzz": PatternRecord("zzz", 1, 2, 1, "INFO", "z", "z"),
            "aaa": PatternRecord("aaa", 1, 2, 1, "INFO", "a", "a"),
            "mmm": PatternRecord("mmm", 1, 2, 1, "INFO", "m", "m"),
        }
        db.save(records)
        # Parse the raw file to check on-disk ordering
        lines = db_path.read_text().strip().splitlines()
        hashes = [json.loads(line)["h"] for line in lines]
        assert hashes == ["aaa", "mmm", "zzz"]

    def test_reset_removes_file(self, db_path):
        """``reset()`` should delete the DB file from disk."""
        db = PatternDB(db_path)
        assert db_path.exists()
        db.reset()
        assert not db_path.exists()

    def test_reset_nonexistent_is_noop(self, tmp_path):
        """Calling ``reset()`` when the file has already been deleted should
        not raise an exception — it is a safe no-op."""
        p = tmp_path / "nope.db"
        db = PatternDB(p)
        db.reset()   # First reset removes the file created by __init__
        db.reset()   # Second reset on a missing file should be silent


# ---------------------------------------------------------------------------
# BaselineState
# ---------------------------------------------------------------------------
class TestBaselineState:
    """Verify baseline learning state persistence and lifecycle."""

    def test_load_missing_file_returns_defaults(self, baseline_path):
        """Loading from a non-existent file should return default state
        (baseline_until=0, meaning baseline is not active)."""
        bs = BaselineState.load(baseline_path)
        assert bs.baseline_until == 0

    def test_load_corrupted_file_returns_defaults(self, baseline_path):
        """If the baseline file contains invalid JSON, ``load`` should
        gracefully fall back to default state instead of crashing."""
        baseline_path.write_text("NOT JSON AT ALL")
        bs = BaselineState.load(baseline_path)
        assert bs.baseline_until == 0

    def test_save_then_load_round_trips(self, baseline_path):
        """A saved baseline_until value should persist and be recoverable."""
        bs = BaselineState(baseline_until=9999)
        bs.save(baseline_path)
        loaded = BaselineState.load(baseline_path)
        assert loaded.baseline_until == 9999

    def test_reset_removes_file(self, baseline_path):
        """``reset()`` should delete the baseline JSON file from disk."""
        bs = BaselineState(baseline_until=100)
        bs.save(baseline_path)
        assert baseline_path.exists()
        BaselineState.reset(baseline_path)
        assert not baseline_path.exists()

    def test_enable_learning_sets_future_timestamp(self, baseline_path):
        """``enable_learning(path, seconds)`` should write a baseline_until
        timestamp that is ``seconds`` in the future (±1 s for clock jitter)."""
        before = int(time.time())
        until = BaselineState.enable_learning(baseline_path, 3600)
        after = int(time.time())
        # The written timestamp should be now + 3600, within the test window
        assert before + 3600 <= until <= after + 3600
        # The file on disk should match what was returned
        loaded = BaselineState.load(baseline_path)
        assert loaded.baseline_until == until


# ---------------------------------------------------------------------------
# parse_duration
# ---------------------------------------------------------------------------
class TestParseDuration:
    """Verify human-friendly duration string parsing into seconds."""

    def test_seconds(self):
        """``'30s'`` should parse to 30 seconds."""
        assert parse_duration("30s") == 30

    def test_minutes(self):
        """``'10m'`` should parse to 600 seconds (10 * 60)."""
        assert parse_duration("10m") == 600

    def test_hours(self):
        """``'2h'`` should parse to 7200 seconds (2 * 3600)."""
        assert parse_duration("2h") == 7200

    def test_days(self):
        """``'1d'`` should parse to 86400 seconds (1 * 86400)."""
        assert parse_duration("1d") == 86400

    def test_whitespace_tolerance(self):
        """Leading/trailing whitespace around the duration string should be
        stripped before parsing."""
        assert parse_duration(" 10m ") == 600

    @pytest.mark.parametrize("bad", ["25q", "", "abc", "m10", "  "])
    def test_invalid_raises_value_error(self, bad):
        """Invalid duration strings (unknown unit, empty, reversed order,
        blank) should raise ``ValueError``."""
        with pytest.raises(ValueError):
            parse_duration(bad)


# ---------------------------------------------------------------------------
# fmt_local_ts
# ---------------------------------------------------------------------------
class TestFmtLocalTs:
    """Verify epoch-to-local-time formatting."""

    def test_format(self):
        """``fmt_local_ts`` should return a 19-character string matching the
        pattern ``YYYY-MM-DD HH:MM:SS`` regardless of the local timezone."""
        result = fmt_local_ts(0)
        # Verify structural positions of delimiters
        assert len(result) == 19
        assert result[4] == "-"    # YYYY-
        assert result[7] == "-"    # MM-
        assert result[10] == " "   # DD<space>
        assert result[13] == ":"   # HH:
        assert result[16] == ":"   # MM:
