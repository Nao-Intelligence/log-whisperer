"""Tests for log_whisperer.core — cluster, build_report, and format_alert_message.

Validates the core analysis pipeline: raw log lines are clustered into
deduplicated patterns, diffed against the persistent pattern DB to
produce NEW/seen tags, and formatted into alert messages for notification
dispatch.
"""

from log_whisperer.core import (
    WindowPattern,
    build_report,
    cluster,
    format_alert_message,
)
from log_whisperer.report import Report, ReportItem
from log_whisperer.state import BaselineState, PatternDB


# ---------------------------------------------------------------------------
# cluster.
# ---------------------------------------------------------------------------
class TestCluster:
    """Verify that ``cluster`` normalizes, deduplicates, and counts raw log lines."""

    def test_empty_input(self):
        """An empty iterable should produce an empty pattern dict."""
        assert cluster([]) == {}

    def test_blank_lines_skipped(self):
        """Lines that normalize to empty (blank, whitespace-only) should be
        silently ignored and not appear in the output."""
        assert cluster(["", "  ", "\n"]) == {}

    def test_duplicate_lines_counted(self):
        """Identical raw lines should collapse into a single pattern whose
        ``count`` reflects how many times the line appeared."""
        window = cluster(["hello world", "hello world", "hello world"])
        assert len(window) == 1
        wp = list(window.values())[0]
        assert wp.count == 3

    def test_different_lines_separate_patterns(self):
        """Lines with different normalized content should each get their own
        entry in the returned dict."""
        window = cluster(["alpha message", "beta message"])
        assert len(window) == 2

    def test_first_raw_line_kept_as_sample(self):
        """The ``sample`` field should preserve the first raw occurrence of
        a pattern, not the last, so users see the original log line."""
        window = cluster(["test line 1", "test line 1"])
        wp = list(window.values())[0]
        assert wp.sample == "test line 1"


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------
class TestBuildReport:
    """Verify report generation, DB diffing, tagging, and filtering logic."""

    def test_new_patterns_tagged_new(self, db_path, baseline_path):
        """A pattern not yet in the DB should appear in the report with tag ``'NEW'``."""
        window = {
            "h1": WindowPattern(h="h1", pattern="pat <N>", count=2, severity="INFO", sample="pat 1"),
        }
        report, alerted, _ = build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="INFO",
        )
        assert len(report.items) == 1
        assert report.items[0].tag == "NEW"

    def test_seen_patterns_tagged_seen(self, db_path, baseline_path):
        """A pattern already present in the DB (from a prior run) should be
        tagged ``'seen'`` on subsequent runs."""
        window = {
            "h1": WindowPattern(h="h1", pattern="pat <N>", count=2, severity="INFO", sample="pat 1"),
        }
        # First run seeds the DB with h1
        build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="INFO",
        )
        # Second run should recognise h1 as already known
        report, _, _ = build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="INFO",
        )
        assert report.items[0].tag == "seen"

    def test_db_updated_after_build(self, db_path, baseline_path):
        """After ``build_report`` completes, the pattern DB on disk should
        contain the window's patterns with correct cumulative counts."""
        window = {
            "h1": WindowPattern(h="h1", pattern="pat <N>", count=3, severity="INFO", sample="pat 1"),
        }
        build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="INFO",
        )
        # Reload DB independently and verify the persisted record
        records = PatternDB(db_path).load()
        assert "h1" in records
        assert records["h1"].total_seen == 3

    def test_show_new_only_filters_seen(self, db_path, baseline_path):
        """With ``show_new_only=True``, previously-seen patterns should be
        excluded from the report items but still have their DB counts updated."""
        window = {
            "h1": WindowPattern(h="h1", pattern="pat <N>", count=1, severity="INFO", sample="pat 1"),
        }
        # First run: h1 is NEW and gets recorded
        build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="INFO",
        )
        # Second run with show_new_only: h1 is now "seen" and should be filtered out
        report, _, _ = build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=True,
            min_severity="INFO",
        )
        assert len(report.items) == 0
        # The DB total should still accumulate (1 + 1 = 2)
        records = PatternDB(db_path).load()
        assert records["h1"].total_seen == 2

    def test_min_severity_filters(self, db_path, baseline_path):
        """With ``min_severity='ERROR'``, INFO-level patterns should be
        excluded from the report but still persisted to the DB."""
        window = {
            "h1": WindowPattern(h="h1", pattern="info msg", count=1, severity="INFO", sample="info msg"),
            "h2": WindowPattern(h="h2", pattern="error msg", count=1, severity="ERROR", sample="error msg"),
        }
        report, _, _ = build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="ERROR",
        )
        # Only the ERROR pattern should appear in the report
        assert len(report.items) == 1
        assert report.items[0].severity == "ERROR"
        # The INFO pattern was still saved silently to the DB
        records = PatternDB(db_path).load()
        assert "h1" in records

    def test_baseline_active_suppresses_alerts(self, db_path, baseline_path):
        """When baseline learning is active, ``alerted_items`` should be empty
        even for NEW patterns, because no alerts should fire during learning."""
        # Activate baseline learning for 1 hour
        BaselineState.enable_learning(baseline_path, 3600)
        window = {
            "h1": WindowPattern(h="h1", pattern="pat <N>", count=1, severity="ERROR", sample="pat 1"),
        }
        _, alerted, baseline_active = build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="INFO",
        )
        assert baseline_active is True
        assert len(alerted) == 0

    def test_patterns_sorted_by_count_desc(self, db_path, baseline_path):
        """Report items should be sorted by window count in descending order
        so the most frequent patterns appear first."""
        window = {
            "h1": WindowPattern(h="h1", pattern="low", count=1, severity="INFO", sample="low"),
            "h2": WindowPattern(h="h2", pattern="high", count=10, severity="INFO", sample="high"),
            "h3": WindowPattern(h="h3", pattern="mid", count=5, severity="INFO", sample="mid"),
        }
        report, _, _ = build_report(
            src_desc="test",
            since="1h",
            lines_limit=100,
            db_path=db_path,
            baseline_path=baseline_path,
            window=window,
            show_new_only=False,
            min_severity="INFO",
        )
        counts = [it.count_window for it in report.items]
        assert counts == [10, 5, 1]


# ---------------------------------------------------------------------------
# format_alert_message
# ---------------------------------------------------------------------------
class TestFormatAlertMessage:
    """Verify plain-text alert message formatting for notification dispatch."""

    def _make_report(self):
        """Helper: build a minimal Report object for alert formatting tests."""
        return Report(
            source="test:src",
            since="1h",
            lines_limit=100,
            state_db="/tmp/db",
            baseline_active=False,
            baseline_until=0,
            generated_at=0,
            items=[],
        )

    def _make_item(self, pattern="pat", severity="ERROR", count=1):
        """Helper: build a single NEW ReportItem with configurable fields."""
        return ReportItem(
            tag="NEW",
            count_window=count,
            total_seen=count,
            severity=severity,
            pattern=pattern,
            sample=f"raw {pattern}",
            hash="h",
        )

    def test_includes_count_and_source(self):
        """The alert header should contain the number of new patterns and
        the source description so recipients know what triggered the alert."""
        report = self._make_report()
        items = [self._make_item()]
        msg = format_alert_message(report, items)
        assert "1 new patterns" in msg
        assert "test:src" in msg

    def test_truncates_with_more_message(self):
        """When the number of alerted items exceeds ``max_items``, the
        message should be truncated with an ``'...and N more.'`` footer."""
        report = self._make_report()
        items = [self._make_item(pattern=f"p{i}") for i in range(15)]
        msg = format_alert_message(report, items, max_items=5)
        # 15 items with max_items=5 → 10 more
        assert "...and 10 more" in msg

    def test_ends_with_newline(self):
        """The message should always end with exactly one newline so
        notification channels can append it cleanly."""
        report = self._make_report()
        items = [self._make_item()]
        msg = format_alert_message(report, items)
        assert msg.endswith("\n")
