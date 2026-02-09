"""Tests for logwhisperer.report — text and JSON output formatters.

Validates that ``report_to_json`` produces valid, complete JSON and that
``print_text_report`` outputs the expected human-readable sections
(header, items, tips, baseline status) to stdout.
"""

import json

from logwhisperer.report import Report, ReportItem, print_text_report, report_to_json


def _make_report(items=None, baseline_active=False, baseline_until=0):
    """Helper: build a Report with sensible defaults and optional overrides."""
    return Report(
        source="test:src",
        since="1h",
        lines_limit=100,
        state_db="/tmp/db",
        baseline_active=baseline_active,
        baseline_until=baseline_until,
        generated_at=1700000000,
        items=items or [],
    )


def _make_item(tag="NEW", pattern="test pattern", severity="ERROR", count=3):
    """Helper: build a single ReportItem with configurable fields."""
    return ReportItem(
        tag=tag,
        count_window=count,
        total_seen=count,
        severity=severity,
        pattern=pattern,
        sample="raw sample line",
        hash="abc123",
    )


class TestReportToJson:
    """Verify JSON serialization of the full report."""

    def test_returns_valid_json(self):
        """``report_to_json`` should return a string that parses as valid JSON
        and contains the expected top-level fields."""
        report = _make_report(items=[_make_item()])
        result = report_to_json(report)
        parsed = json.loads(result)
        assert parsed["source"] == "test:src"
        assert len(parsed["items"]) == 1

    def test_all_fields_present(self):
        """Every Report and ReportItem field should be present in the JSON
        output so downstream consumers can rely on a stable schema."""
        report = _make_report(items=[_make_item()])
        parsed = json.loads(report_to_json(report))
        # Top-level report fields
        for field in ("source", "since", "lines_limit", "state_db",
                      "baseline_active", "baseline_until", "generated_at", "items"):
            assert field in parsed
        # Per-item fields
        item = parsed["items"][0]
        for field in ("tag", "count_window", "total_seen", "severity",
                      "pattern", "sample", "hash"):
            assert field in item


class TestPrintTextReport:
    """Verify human-readable text report output via stdout capture."""

    def test_outputs_header(self, capsys):
        """The text report should start with a header banner containing the
        report title and the source description."""
        report = _make_report(items=[_make_item()])
        print_text_report(report, show_samples=False)
        out = capsys.readouterr().out
        assert "Log Whisperer Report" in out
        assert "test:src" in out

    def test_empty_items_shows_no_patterns(self, capsys):
        """When there are no report items, the output should display a
        user-friendly 'No patterns to show.' message."""
        report = _make_report()
        print_text_report(report, show_samples=False)
        out = capsys.readouterr().out
        assert "No patterns to show." in out

    def test_show_samples_includes_sample(self, capsys):
        """With ``show_samples=True``, each pattern's raw sample line should
        be printed below the pattern summary."""
        report = _make_report(items=[_make_item()])
        print_text_report(report, show_samples=True)
        out = capsys.readouterr().out
        assert "sample:" in out
        assert "raw sample line" in out

    def test_tip_shown(self, capsys):
        """A usage tip mentioning ``--show-new`` should appear at the bottom
        of every text report to guide new users."""
        report = _make_report(items=[_make_item()])
        print_text_report(report, show_samples=False)
        out = capsys.readouterr().out
        assert "--show-new" in out

    def test_baseline_active_shown(self, capsys):
        """When baseline learning is active, the report header should include
        a ``'Baseline: ACTIVE'`` notice so users know alerts are suppressed."""
        report = _make_report(baseline_active=True, baseline_until=1700000000)
        print_text_report(report, show_samples=False)
        out = capsys.readouterr().out
        assert "Baseline: ACTIVE" in out
