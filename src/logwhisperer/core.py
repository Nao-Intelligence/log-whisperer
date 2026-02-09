"""Core analysis pipeline: normalize, cluster, diff against DB, and report.

This module ties together normalization, severity classification, and the
persistent pattern database to produce a report of observed patterns with
NEW/seen tags and optional alert items for notification dispatch.
"""

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
    """Aggregated pattern data from the current analysis window (one run)."""
    h: str
    pattern: str
    count: int
    severity: str
    sample: str


def cluster(lines: Iterable[str]) -> Dict[str, WindowPattern]:
    """Normalize and group raw log lines into deduplicated patterns.

    Each unique normalized pattern gets a count, severity, and one raw
    sample line. Returns a dict keyed by pattern hash.
    """
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
        samples.setdefault(h, raw)  # keep the first occurrence as sample
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
    """Diff the current window against the DB and produce a report.

    For each pattern in the window:
      1. Check if it already exists in the DB (seen vs NEW).
      2. Update cumulative counts in the DB regardless of filters.
      3. Build report items honoring ``show_new_only`` and ``min_severity``.
      4. Collect alert-worthy items (NEW patterns outside baseline mode).

    Returns:
        A 3-tuple of (report, alerted_items, baseline_active).
    """
    db = PatternDB(db_path)
    records = db.load()
    now = now_epoch()

    baseline = BaselineState.load(baseline_path)
    baseline_active = baseline.baseline_until > now

    severity_rank = {"INFO": 0, "WARN": 1, "ERROR": 2}
    min_rank = severity_rank.get(min_severity, 0)

    # Show highest-count patterns first in the report
    items_sorted = sorted(window.values(), key=lambda w: w.count, reverse=True)

    report_items: List[ReportItem] = []
    alerted_items: List[ReportItem] = []

    for w in items_sorted:
        old = records.get(w.h)
        is_new = old is None

        if severity_rank.get(w.severity, 0) < min_rank:
            # Below severity threshold — update DB silently, skip report
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
            # User only wants NEW patterns — update DB, skip report
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

        # Only alert on NEW patterns when baseline learning is inactive
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
    """Build a plain-text alert message for notification dispatch."""
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
