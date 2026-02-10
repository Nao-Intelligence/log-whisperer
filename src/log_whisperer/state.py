"""Persistent pattern database and baseline state management.

The pattern DB uses a JSON-lines format (one JSON object per line) for safe
storage — no delimiter collision issues unlike pipe-delimited formats.
File locking via ``fcntl.flock`` prevents corruption when overlapping
cron-invoked instances read/write the DB concurrently.
"""

from __future__ import annotations

import fcntl
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict


@dataclass
class PatternRecord:
    """A single pattern entry stored in the DB.

    Attributes:
        h: SHA-1 hash of the normalized pattern (primary key).
        first_seen: Epoch timestamp when this pattern was first observed.
        last_seen: Epoch timestamp of the most recent observation.
        total_seen: Cumulative count across all analysis runs.
        severity: Classified severity (ERROR / WARN / INFO).
        pattern: The normalized pattern string (with placeholders).
        sample: One raw log line that matched this pattern.
    """
    h: str
    first_seen: int
    last_seen: int
    total_seen: int
    severity: str
    pattern: str
    sample: str

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON encoding."""
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "PatternRecord":
        """Deserialize from a dict parsed from a JSON-lines DB entry."""
        return PatternRecord(
            h=d["h"],
            first_seen=int(d["first_seen"]),
            last_seen=int(d["last_seen"]),
            total_seen=int(d["total_seen"]),
            severity=d["severity"],
            pattern=d["pattern"],
            sample=d["sample"],
        )


class PatternDB:
    """JSON-lines backed pattern database with file-level locking.

    Each line in the DB file is a self-contained JSON object, making the
    format both human-readable (``jq`` friendly) and resilient to fields
    containing special characters.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def load(self) -> Dict[str, PatternRecord]:
        """Read all pattern records from the DB file.

        Acquires a shared lock (``LOCK_SH``) so concurrent readers don't
        block each other but writers wait until all readers finish.
        Malformed lines are silently skipped.
        """
        records: Dict[str, PatternRecord] = {}
        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        rec = PatternRecord.from_dict(d)
                        records[rec.h] = rec
                    except (json.JSONDecodeError, KeyError):
                        continue
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return records

    def save(self, records: Dict[str, PatternRecord]) -> None:
        """Write all pattern records to the DB file atomically.

        Acquires an exclusive lock (``LOCK_EX``) to prevent concurrent
        writes from interleaving lines. Records are sorted by hash for
        deterministic output.
        """
        with open(self.path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                for h in sorted(records.keys()):
                    f.write(json.dumps(records[h].to_dict(), separators=(",", ":")) + "\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def reset(self) -> None:
        """Delete the DB file entirely."""
        if self.path.exists():
            self.path.unlink()


@dataclass
class BaselineState:
    """Tracks whether baseline learning mode is active.

    During baseline learning, new patterns are recorded in the DB but
    no alerts are fired. This lets the tool "learn" normal log patterns
    before it starts flagging anomalies.
    """
    baseline_until: int = 0

    @staticmethod
    def load(path: Path) -> "BaselineState":
        """Load baseline state from a JSON file, or return defaults."""
        if not path.exists():
            return BaselineState()
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return BaselineState(baseline_until=int(d.get("baseline_until", 0)))
        except Exception:
            return BaselineState()

    def save(self, path: Path) -> None:
        """Persist baseline state to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @staticmethod
    def reset(path: Path) -> None:
        """Remove the baseline state file."""
        if path.exists():
            path.unlink()

    @staticmethod
    def enable_learning(path: Path, seconds: int) -> int:
        """Activate baseline learning for *seconds* from now.

        Returns the epoch timestamp when learning will expire.
        """
        until = int(time.time()) + seconds
        st = BaselineState.load(path)
        st.baseline_until = until
        st.save(path)
        return until


def parse_duration(s: str) -> int:
    """Parse a human-friendly duration string into seconds.

    Accepted formats: ``"30s"``, ``"10m"``, ``"2h"``, ``"1d"``.

    Raises:
        ValueError: If the string doesn't match ``<number><s|m|h|d>``.
    """
    m = re.fullmatch(r"(\d+)\s*([smhd])", s.strip().lower())
    if not m:
        raise ValueError('Invalid duration. Use e.g. "30m", "2h", "1d".')
    n = int(m.group(1))
    unit = m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return n * mult


def fmt_local_ts(epoch: int) -> str:
    """Format an epoch timestamp as a local ``YYYY-MM-DD HH:MM:SS`` string."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))


def now_epoch() -> int:
    """Return the current time as a Unix epoch integer."""
    return int(time.time())
