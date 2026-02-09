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
    h: str
    first_seen: int
    last_seen: int
    total_seen: int
    severity: str
    pattern: str
    sample: str

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "PatternRecord":
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
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def load(self) -> Dict[str, PatternRecord]:
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
        with open(self.path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                for h in sorted(records.keys()):
                    f.write(json.dumps(records[h].to_dict(), separators=(",", ":")) + "\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()


@dataclass
class BaselineState:
    baseline_until: int = 0

    @staticmethod
    def load(path: Path) -> "BaselineState":
        if not path.exists():
            return BaselineState()
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return BaselineState(baseline_until=int(d.get("baseline_until", 0)))
        except Exception:
            return BaselineState()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @staticmethod
    def reset(path: Path) -> None:
        if path.exists():
            path.unlink()

    @staticmethod
    def enable_learning(path: Path, seconds: int) -> int:
        until = int(time.time()) + seconds
        st = BaselineState.load(path)
        st.baseline_until = until
        st.save(path)
        return until


def parse_duration(s: str) -> int:
    """
    Parse duration like: 30m, 2h, 1d, 10s  -> seconds
    """
    m = re.fullmatch(r"(\d+)\s*([smhd])", s.strip().lower())
    if not m:
        raise ValueError('Invalid duration. Use e.g. "30m", "2h", "1d".')
    n = int(m.group(1))
    unit = m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return n * mult


def fmt_local_ts(epoch: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))


def now_epoch() -> int:
    return int(time.time())
