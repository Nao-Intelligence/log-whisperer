Yes — here’s a clean refactor into a proper package layout. This keeps the **same features** (docker/compose sources, normalization+clustering, baseline learning, JSON/text output, severity filtering, sample lines, notifications via ntfy/telegram/email), but splits the code so it’s maintainable and testable.

Below is the **full updated code** file-by-file.

---

## ✅ New project structure

```text
src/logwhisperer/
  __init__.py
  cli.py
  paths.py
  normalize.py
  severity.py
  state.py
  core.py
  report.py
  sources/
    __init__.py
    docker.py
    compose.py
    journal.py
    file.py
  notify/
    __init__.py
    ntfy.py
    telegram.py
    email_smtp.py
    dispatch.py
```

---

# `src/logwhisperer/__init__.py`

```python
__version__ = "0.2.0"
```

---

# `src/logwhisperer/paths.py`

```python
from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "logwhisperer"


def default_state_dir() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state_home) / APP_NAME
```

---

# `src/logwhisperer/normalize.py`

```python
from __future__ import annotations

import hashlib
import re

_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_HASH_RE = re.compile(r"\b[0-9a-f]{32,64}\b", re.I)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC_RE = re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.I)
_HEX_RE = re.compile(r"\b0x[0-9a-f]+\b", re.I)
_NUM_RE = re.compile(r"\b\d+\b")
_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._-]+)+")

_SYSLOG_PREFIX_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[^ ]+\s+[^:]+:\s*")
_ISO_TS_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.+-]+\s*")


def normalize_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""

    line = _SYSLOG_PREFIX_RE.sub("", line)
    line = _ISO_TS_PREFIX_RE.sub("", line)

    line = _UUID_RE.sub("<UUID>", line)
    line = _HASH_RE.sub("<HASH>", line)
    line = _IP_RE.sub("<IP>", line)
    line = _MAC_RE.sub("<MAC>", line)
    line = _HEX_RE.sub("<HEX>", line)
    line = _PATH_RE.sub("<PATH>", line)
    line = _NUM_RE.sub("<N>", line)

    line = re.sub(r"\s+", " ", line).strip()
    return line


def pattern_hash(pattern: str) -> str:
    return hashlib.sha1(pattern.encode("utf-8")).hexdigest()
```

---

# `src/logwhisperer/severity.py`

```python
from __future__ import annotations

ERROR_HINTS = (
    "error",
    "fatal",
    "exception",
    "traceback",
    "panic",
    "segfault",
    "failed",
    "failure",
    "critical",
)

WARN_HINTS = (
    "warn",
    "warning",
    "timeout",
    "timed out",
    "retry",
    "throttle",
    "rate limit",
    "deprecated",
    "slow",
    "unavailable",
)


def severity_of(text: str) -> str:
    t = text.lower()
    if any(h in t for h in ERROR_HINTS):
        return "ERROR"
    if any(h in t for h in WARN_HINTS):
        return "WARN"
    return "INFO"
```

---

# `src/logwhisperer/state.py`

```python
from __future__ import annotations

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

    @staticmethod
    def parse(line: str) -> "PatternRecord":
        parts = line.rstrip("\n").split("|", 6)
        if len(parts) != 7:
            raise ValueError("Bad DB line format")
        rec = PatternRecord(
            h=parts[0],
            first_seen=int(parts[1]),
            last_seen=int(parts[2]),
            total_seen=int(parts[3]),
            severity=parts[4],
            pattern=parts[5].replace("\\n", "\n"),
            sample=parts[6].replace("\\n", "\n"),
        )
        return rec

    def serialize(self) -> str:
        safe_pattern = self.pattern.replace("\n", "\\n")
        safe_sample = self.sample.replace("\n", "\\n")
        return f"{self.h}|{self.first_seen}|{self.last_seen}|{self.total_seen}|{self.severity}|{safe_pattern}|{safe_sample}\n"


class PatternDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("# h|first_seen|last_seen|total_seen|severity|pattern|sample\n", encoding="utf-8")

    def load(self) -> Dict[str, PatternRecord]:
        records: Dict[str, PatternRecord] = {}
        text = self.path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines(True):
            if not line or line.startswith("#"):
                continue
            rec = PatternRecord.parse(line)
            records[rec.h] = rec
        return records

    def save(self, records: Dict[str, PatternRecord]) -> None:
        header = "# h|first_seen|last_seen|total_seen|severity|pattern|sample\n"
        lines = [header] + [records[h].serialize() for h in sorted(records.keys())]
        self.path.write_text("".join(lines), encoding="utf-8")

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
```

---

# `src/logwhisperer/report.py`

```python
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class ReportItem:
    tag: str
    count_window: int
    total_seen: int
    severity: str
    pattern: str
    sample: str
    hash: str


@dataclass
class Report:
    source: str
    since: str
    lines_limit: int
    state_db: str
    baseline_active: bool
    baseline_until: int
    generated_at: int
    items: List[ReportItem]


def print_text_report(report: Report, show_samples: bool) -> None:
    print("\n=== Log Whisperer Report ===")
    print(f"Source: {report.source} | since={report.since} | lines<={report.lines_limit}")
    print(f"State: {report.state_db}")

    if report.baseline_active:
        until = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(report.baseline_until))
        print(f"Baseline: ACTIVE (learning) until {until}")
    print()

    if not report.items:
        print("No patterns to show.")
        print("\nTip: use --show-new to only display never-seen patterns.")
        return

    for it in report.items:
        print(f"[{it.tag}][{it.severity}] x{it.count_window:<5} total={it.total_seen:<7}  {it.pattern}")
        if show_samples:
            print(f"  sample: {it.sample}")

    print("\nTip: use --show-new to only display never-seen patterns.")


def report_to_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2)
```

---

# `src/logwhisperer/core.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .normalize import normalize_line, pattern_hash
from .severity import severity_of
from .state import BaselineState, PatternDB, PatternRecord, now_epoch
from .report import Report, ReportItem


@dataclass
class WindowPattern:
    h: str
    pattern: str
    count: int
    severity: str
    sample: str


def cluster(lines: Iterable[str]) -> Dict[str, WindowPattern]:
    counts: Dict[str, int] = {}
    patterns: Dict[str, str] = {}
    samples: Dict[str, str] = {}
    severities: Dict[str, str] = {}

    for raw in lines:
        raw = raw.rstrip("\n")
        pat = normalize_line(raw)
        if not pat:
            continue
        h = pattern_hash(pat)
        counts[h] = counts.get(h, 0) + 1
        patterns[h] = pat
        samples.setdefault(h, raw)
        severities[h] = severity_of(pat)

    out: Dict[str, WindowPattern] = {}
    for h, c in counts.items():
        out[h] = WindowPattern(
            h=h,
            pattern=patterns[h],
            count=c,
            severity=severities[h],
            sample=samples[h],
        )
    return out


def build_report(
    src_desc: str,
    since: str,
    lines_limit: int,
    db_path: Path,
    baseline_path: Path,
    window: Dict[str, WindowPattern],
    show_new_only: bool,
    min_severity: str,
) -> Tuple[Report, List[ReportItem], bool]:
    db = PatternDB(db_path)
    records = db.load()
    now = now_epoch()

    baseline = BaselineState.load(baseline_path)
    baseline_active = baseline.baseline_until > now

    severity_rank = {"INFO": 0, "WARN": 1, "ERROR": 2}
    min_rank = severity_rank.get(min_severity, 0)

    items_sorted = sorted(window.values(), key=lambda w: w.count, reverse=True)

    report_items: List[ReportItem] = []
    alerted_items: List[ReportItem] = []

    for w in items_sorted:
        old = records.get(w.h)
        is_new = old is None

        if severity_rank.get(w.severity, 0) < min_rank:
            # still update DB
            if old is None:
                records[w.h] = PatternRecord(
                    h=w.h,
                    first_seen=now,
                    last_seen=now,
                    total_seen=w.count,
                    severity=w.severity,
                    pattern=w.pattern,
                    sample=w.sample,
                )
            else:
                old.last_seen = now
                old.total_seen += w.count
                records[w.h] = old
            continue

        if show_new_only and not is_new:
            old.last_seen = now
            old.total_seen += w.count
            records[w.h] = old
            continue

        if is_new:
            rec = PatternRecord(
                h=w.h,
                first_seen=now,
                last_seen=now,
                total_seen=w.count,
                severity=w.severity,
                pattern=w.pattern,
                sample=w.sample,
            )
            tag = "NEW"
        else:
            rec = PatternRecord(
                h=w.h,
                first_seen=old.first_seen,
                last_seen=now,
                total_seen=old.total_seen + w.count,
                severity=old.severity or w.severity,
                pattern=w.pattern,
                sample=old.sample or w.sample,
            )
            tag = "seen"

        item = ReportItem(
            tag=tag,
            count_window=w.count,
            total_seen=rec.total_seen,
            severity=w.severity,
            pattern=w.pattern,
            sample=w.sample,
            hash=w.h,
        )
        report_items.append(item)

        if (not baseline_active) and (tag == "NEW"):
            alerted_items.append(item)

        records[w.h] = rec

    db.save(records)

    report = Report(
        source=src_desc,
        since=since,
        lines_limit=lines_limit,
        state_db=str(db_path),
        baseline_active=baseline_active,
        baseline_until=baseline.baseline_until,
        generated_at=now,
        items=report_items,
    )
    return report, alerted_items, baseline_active


def format_alert_message(report: Report, alerted: List[ReportItem], max_items: int = 10) -> str:
    lines: List[str] = []
    lines.append(f"Log Whisperer ALERT ({len(alerted)} new patterns)")
    lines.append(f"Source: {report.source} | since={report.since}")
    lines.append("")

    for it in alerted[:max_items]:
        lines.append(f"[NEW][{it.severity}] x{it.count_window}  {it.pattern}")
        lines.append(f"sample: {it.sample}")
        lines.append("")

    if len(alerted) > max_items:
        lines.append(f"...and {len(alerted) - max_items} more.")
    return "\n".join(lines).rstrip() + "\n"
```

---

## Sources

### `src/logwhisperer/sources/__init__.py`

```python
from __future__ import annotations

from typing import List, Tuple

from .docker import read_docker
from .compose import read_compose, read_compose_all
from .journal import read_journal
from .file import read_file


def read_lines(args) -> Tuple[List[str], str]:
    """
    Returns (lines, src_desc)
    """
    if args.docker:
        return read_docker(args.docker, args.since, args.lines), f"docker:{args.docker}"

    if args.compose:
        return read_compose(args.compose, args.since, args.lines), f"compose:{args.compose}"

    if args.compose_all:
        return read_compose_all(args.since, args.lines), "compose:all"

    if args.service:
        return read_journal(args.service, args.since, args.lines), f"journal:{args.service}"

    if args.file:
        return read_file(args.file, args.lines), f"file:{args.file}"

    raise RuntimeError("No log source provided.")
```

### `src/logwhisperer/sources/docker.py`

```python
from __future__ import annotations

import subprocess
from typing import List


def _run_cmd(cmd: List[str]) -> str:
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}")
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def read_docker(container: str, since: str, limit: int) -> List[str]:
    out = _run_cmd(["docker", "logs", "--since", since, container])
    return out.splitlines()[-limit:]
```

### `src/logwhisperer/sources/compose.py`

```python
from __future__ import annotations

import subprocess
from typing import List


def _run_cmd(cmd: List[str]) -> str:
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}")
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def read_compose(service: str, since: str, limit: int) -> List[str]:
    out = _run_cmd(["docker", "compose", "logs", "--since", since, "--no-color", service])
    return out.splitlines()[-limit:]


def read_compose_all(since: str, limit: int) -> List[str]:
    out = _run_cmd(["docker", "compose", "logs", "--since", since, "--no-color"])
    return out.splitlines()[-limit:]
```

### `src/logwhisperer/sources/journal.py`

```python
from __future__ import annotations

import subprocess
from typing import List


def _run_cmd(cmd: List[str]) -> str:
    try:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}")
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def read_journal(service: str, since: str, limit: int) -> List[str]:
    out = _run_cmd(["journalctl", "-u", service, "--since", since, "-o", "cat", "--no-pager"])
    return out.splitlines()[-limit:]
```

### `src/logwhisperer/sources/file.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import List


def read_file(path: str, limit: int) -> List[str]:
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"File not found: {p}")
    return p.read_text(errors="ignore").splitlines()[-limit:]
```

---

## Notifications

### `src/logwhisperer/notify/__init__.py`

```python
# namespace package for notifiers
```

### `src/logwhisperer/notify/ntfy.py`

```python
from __future__ import annotations

import requests


def notify_ntfy(topic: str, message: str, server: str = "https://ntfy.sh", title: str = "Log Whisperer") -> None:
    url = f"{server.rstrip('/')}/{topic}"
    headers = {"Title": title}
    r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=10)
    r.raise_for_status()
```

### `src/logwhisperer/notify/telegram.py`

```python
from __future__ import annotations

import requests


def notify_telegram(token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
```

### `src/logwhisperer/notify/email_smtp.py`

```python
from __future__ import annotations

import smtplib
from email.message import EmailMessage


def notify_email_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    use_tls: bool = True,
) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=15) as s:
        if use_tls:
            s.starttls()
        if username:
            s.login(username, password)
        s.send_message(msg)
```

### `src/logwhisperer/notify/dispatch.py`

```python
from __future__ import annotations

from typing import List

from .ntfy import notify_ntfy
from .telegram import notify_telegram
from .email_smtp import notify_email_smtp


def dispatch_notifications(args, message: str) -> List[str]:
    failures: List[str] = []

    # ntfy
    if getattr(args, "notify_ntfy_topic", ""):
        try:
            notify_ntfy(
                topic=args.notify_ntfy_topic,
                message=message,
                server=args.notify_ntfy_server,
                title="Log Whisperer Alert",
            )
        except Exception as e:
            failures.append(f"ntfy: {e}")

    # Telegram
    if getattr(args, "notify_telegram_token", "") and getattr(args, "notify_telegram_chat_id", ""):
        try:
            notify_telegram(args.notify_telegram_token, args.notify_telegram_chat_id, message)
        except Exception as e:
            failures.append(f"telegram: {e}")

    # Email
    email_ready = all(
        [
            getattr(args, "notify_email_host", ""),
            getattr(args, "notify_email_from", ""),
            getattr(args, "notify_email_to", ""),
        ]
    )
    if email_ready:
        try:
            notify_email_smtp(
                host=args.notify_email_host,
                port=args.notify_email_port,
                username=args.notify_email_user,
                password=args.notify_email_pass,
                sender=args.notify_email_from,
                recipient=args.notify_email_to,
                subject="Log Whisperer Alert: New log patterns detected",
                body=message,
                use_tls=not args.notify_email_no_tls,
            )
        except Exception as e:
            failures.append(f"email: {e}")

    return failures
```

---

# ✅ The new `src/logwhisperer/cli.py` (short + clean)

```python
from __future__ import annotations

import argparse
import os
import sys

from pathlib import Path

from .paths import default_state_dir
from .sources import read_lines
from .core import cluster, build_report, format_alert_message
from .report import print_text_report, report_to_json
from .notify.dispatch import dispatch_notifications
from .state import BaselineState, PatternDB, parse_duration, fmt_local_ts


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="log-whisperer",
        description="Cluster logs into patterns, detect new patterns, and optionally notify.",
    )

    src = parser.add_argument_group("Sources (choose one)")
    src.add_argument("--docker", help="docker logs --since <since> <container>")
    src.add_argument("--compose", help="docker compose logs --since <since> <service>")
    src.add_argument("--compose-all", action="store_true", help="docker compose logs --since <since> (all services)")
    src.add_argument("--service", help="journalctl -u <service> --since <since>")
    src.add_argument("--file", help="Read last N lines from a file")

    parser.add_argument("--since", default="1h", help='Time window: e.g. "10m", "1h", "today"')
    parser.add_argument("--lines", type=int, default=5000, help="Max lines to process")
    parser.add_argument("--show-new", action="store_true", help="Only show never-seen patterns")
    parser.add_argument("--min-severity", choices=["INFO", "WARN", "ERROR"], default="INFO", help="Filter by severity")
    parser.add_argument("--show-samples", action="store_true", help="Print one raw sample line per pattern")
    parser.add_argument("--json", action="store_true", help="Output report as JSON (still updates DB)")

    state_dir = default_state_dir()
    parser.add_argument("--state-db", default=str(state_dir / "patterns.db"), help="Pattern DB path")
    parser.add_argument("--baseline-state", default=str(state_dir / "baseline.json"), help="Baseline state path")
    parser.add_argument("--reset", action="store_true", help="Reset pattern DB and baseline state")

    parser.add_argument("--baseline-learn", type=str, default="", help='Start baseline learning like "24h", "30m"')

    notify = parser.add_argument_group("Notifications")
    notify.add_argument("--notify-ntfy-topic", default=os.getenv("LOGWHISPER_NTFY_TOPIC", ""), help="ntfy topic")
    notify.add_argument("--notify-ntfy-server", default=os.getenv("LOGWHISPER_NTFY_SERVER", "https://ntfy.sh"), help="ntfy server")
    notify.add_argument("--notify-telegram-token", default=os.getenv("LOGWHISPER_TELEGRAM_TOKEN", ""), help="Telegram bot token")
    notify.add_argument("--notify-telegram-chat-id", default=os.getenv("LOGWHISPER_TELEGRAM_CHAT_ID", ""), help="Telegram chat id")
    notify.add_argument("--notify-email-host", default=os.getenv("LOGWHISPER_SMTP_HOST", ""), help="SMTP host")
    notify.add_argument("--notify-email-port", type=int, default=int(os.getenv("LOGWHISPER_SMTP_PORT", "587")), help="SMTP port")
    notify.add_argument("--notify-email-user", default=os.getenv("LOGWHISPER_SMTP_USER", ""), help="SMTP username")
    notify.add_argument("--notify-email-pass", default=os.getenv("LOGWHISPER_SMTP_PASS", ""), help="SMTP password")
    notify.add_argument("--notify-email-from", default=os.getenv("LOGWHISPER_EMAIL_FROM", ""), help="Email From")
    notify.add_argument("--notify-email-to", default=os.getenv("LOGWHISPER_EMAIL_TO", ""), help="Email To")
    notify.add_argument("--notify-email-no-tls", action="store_true", help="Disable STARTTLS for SMTP")

    args = parser.parse_args(argv)

    chosen = sum(bool(x) for x in [args.docker, args.compose, args.compose_all, args.service, args.file])
    if chosen != 1 and not args.reset:
        parser.error("Choose exactly one source: --docker, --compose, --compose-all, --service, or --file")

    return args


def main(argv=None) -> None:
    args = parse_args(argv)

    db_path = Path(args.state_db)
    baseline_path = Path(args.baseline_state)

    if args.reset:
        PatternDB(db_path).reset()
        BaselineState.reset(baseline_path)
        print(f"Reset: removed {db_path} and {baseline_path}")
        return

    if args.baseline_learn:
        try:
            seconds = parse_duration(args.baseline_learn)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
        until = BaselineState.enable_learning(baseline_path, seconds)
        print(f"Baseline learning enabled until {fmt_local_ts(until)}. (No alerts during this period)")

    try:
        lines, src_desc = read_lines(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    window = cluster(lines)
    report, alerted_items, baseline_active = build_report(
        src_desc=src_desc,
        since=args.since,
        lines_limit=args.lines,
        db_path=db_path,
        baseline_path=baseline_path,
        window=window,
        show_new_only=args.show_new,
        min_severity=args.min_severity,
    )

    if args.json:
        print(report_to_json(report))
    else:
        print_text_report(report, show_samples=args.show_samples)

    if baseline_active or not alerted_items:
        return

    alert_msg = format_alert_message(report, alerted_items)
    failures = dispatch_notifications(args, alert_msg)
    if failures:
        print("Notification failures:", file=sys.stderr)
        for f in failures:
            print(f" - {f}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

---

## Quick check: nothing else needs to change

Your `pyproject.toml` entry point stays:

```toml
[project.scripts]
log-whisperer = "logwhisperer.cli:main"
```

Then install locally with pipx:

```bash
pipx install .
```

---

## Two tiny improvements (optional but recommended)

1. In `sources/*`, you can deduplicate `_run_cmd` into a shared utility later (`utils/subprocess.py`).
2. Add tests: `tests/test_normalize.py`, `tests/test_severity.py`, `tests/test_state_db.py`.

If you want, I can also provide a **pytest suite** for these modules so you can confidently extend it.
