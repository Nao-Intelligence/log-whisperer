"""Report data structures and output formatters (text and JSON)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class ReportItem:
    """One pattern entry in the analysis report.

    Attributes:
        tag: ``"NEW"`` if the pattern was never seen before, ``"seen"`` otherwise.
        count_window: How many times this pattern appeared in the current window.
        total_seen: Cumulative count across all runs (from the DB).
        severity: Classified severity level.
        pattern: Normalized pattern string with placeholders.
        sample: One raw log line that produced this pattern.
        hash: SHA-1 hash identifying this pattern.
    """
    tag: str
    count_window: int
    total_seen: int
    severity: str
    pattern: str
    sample: str
    hash: str


@dataclass
class Report:
    """Top-level report container with metadata and pattern items."""
    source: str
    since: str
    lines_limit: int
    state_db: str
    baseline_active: bool
    baseline_until: int
    generated_at: int
    items: List[ReportItem]


def print_text_report(report: Report, show_samples: bool) -> None:
    """Print a human-readable report to stdout."""
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
    """Serialize the full report to a pretty-printed JSON string."""
    return json.dumps(asdict(report), indent=2)
