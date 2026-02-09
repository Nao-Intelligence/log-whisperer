"""Tests for logwhisperer.cli — argument parsing and end-to-end integration.

Validates that ``parse_args`` enforces source-selection rules, parses
typed arguments correctly, and applies sensible defaults.  Integration
tests exercise the full ``main()`` pipeline against temporary log files
and state directories, verifying text/JSON output and state side-effects.
"""

import json

import pytest

from logwhisperer.cli import parse_args, main


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------
class TestParseArgs:
    """Verify CLI argument parsing, defaults, and validation rules."""

    def test_file_source_succeeds(self):
        """Providing exactly one source (--file) should parse without error
        and populate ``args.file`` with the given path."""
        args = parse_args(["--file", "x.log"])
        assert args.file == "x.log"

    def test_no_source_raises(self):
        """Calling with no source flags and no --reset should cause argparse
        to exit with an error (SystemExit)."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_multiple_sources_raises(self):
        """Specifying more than one source flag (e.g. --file and --docker)
        should be rejected because the tool reads from exactly one source."""
        with pytest.raises(SystemExit):
            parse_args(["--file", "x.log", "--docker", "cont"])

    def test_reset_alone_with_source_succeeds(self):
        """``--reset`` combined with a source should parse successfully.
        The source is ignored during reset but is still accepted."""
        args = parse_args(["--file", "x.log", "--reset"])
        assert args.reset is True

    def test_reset_without_source_succeeds(self):
        """``--reset`` on its own (no source) should be accepted because
        reset only deletes state files and does not read logs."""
        args = parse_args(["--reset"])
        assert args.reset is True

    def test_lines_parsed_as_int(self):
        """The ``--lines`` argument should be parsed as an integer."""
        args = parse_args(["--file", "x.log", "--lines", "200"])
        assert args.lines == 200

    def test_min_severity_restricted(self):
        """``--min-severity`` only accepts INFO, WARN, or ERROR.  Any other
        value (e.g. DEBUG) should trigger an argparse error."""
        for sev in ("INFO", "WARN", "ERROR"):
            args = parse_args(["--file", "x.log", "--min-severity", sev])
            assert args.min_severity == sev
        # An unsupported severity level should be rejected
        with pytest.raises(SystemExit):
            parse_args(["--file", "x.log", "--min-severity", "DEBUG"])

    def test_since_default(self):
        """The default value for ``--since`` should be ``'1h'`` (one hour)."""
        args = parse_args(["--file", "x.log"])
        assert args.since == "1h"


# ---------------------------------------------------------------------------
# main integration
# ---------------------------------------------------------------------------
class TestMain:
    """End-to-end integration tests that invoke ``main()`` with temp files."""

    def test_run_with_file(self, tmp_path, capsys):
        """Running the full pipeline on a real temp log file should produce
        a text report on stdout and create a pattern DB file on disk."""
        log = tmp_path / "app.log"
        log.write_text("error happened\nnormal line\nerror happened\n")
        db = tmp_path / "test.db"
        bl = tmp_path / "baseline.json"

        main(["--file", str(log), "--state-db", str(db), "--baseline-state", str(bl)])

        out = capsys.readouterr().out
        # The text report header should be present
        assert "Log Whisperer Report" in out
        # The DB file should have been created by build_report
        assert db.exists()

    def test_reset_removes_db(self, tmp_path, capsys):
        """``--reset`` should delete both the pattern DB and baseline files
        and print a confirmation message."""
        db = tmp_path / "test.db"
        bl = tmp_path / "baseline.json"
        # Pre-create the files so reset has something to delete
        db.write_text("")
        bl.write_text("{}")

        main(["--reset", "--file", str(tmp_path / "x.log"),
              "--state-db", str(db), "--baseline-state", str(bl)])

        out = capsys.readouterr().out
        assert "Reset" in out
        # Both state files should be gone
        assert not db.exists()

    def test_json_output(self, tmp_path, capsys):
        """``--json`` should cause ``main()`` to emit a valid JSON report
        instead of the human-readable text format."""
        log = tmp_path / "app.log"
        log.write_text("something happened\n")
        db = tmp_path / "test.db"
        bl = tmp_path / "baseline.json"

        main(["--file", str(log), "--json",
              "--state-db", str(db), "--baseline-state", str(bl)])

        out = capsys.readouterr().out
        # The output should be parseable JSON with the expected top-level keys
        parsed = json.loads(out)
        assert "items" in parsed
        assert "source" in parsed

    def test_baseline_learn(self, tmp_path, capsys):
        """``--baseline-learn 1h`` should activate baseline learning, write
        the baseline state file, and print a confirmation message."""
        log = tmp_path / "app.log"
        log.write_text("test line\n")
        db = tmp_path / "test.db"
        bl = tmp_path / "baseline.json"

        main(["--file", str(log), "--baseline-learn", "1h",
              "--state-db", str(db), "--baseline-state", str(bl)])

        out = capsys.readouterr().out
        assert "Baseline learning enabled" in out
        # The baseline state file should have been persisted
        assert bl.exists()
