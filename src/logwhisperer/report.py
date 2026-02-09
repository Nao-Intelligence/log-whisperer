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
