"""Tests for log_whisperer.sources._subprocess — shared subprocess helper.

Validates that ``run_cmd`` correctly captures stdout from successful
commands, raises ``RuntimeError`` with descriptive messages for missing
binaries and non-zero exits, and handles empty output gracefully.
"""

import pytest

from log_whisperer.sources._subprocess import run_cmd


class TestRunCmd:
    """Verify subprocess execution, error handling, and output capture."""

    def test_successful_command(self):
        """A command that exits 0 should return its stdout as a string."""
        result = run_cmd(["echo", "hello"])
        assert result.strip() == "hello"

    def test_command_not_found(self):
        """Attempting to run a non-existent binary should raise RuntimeError
        with a ``'Command not found'`` message referencing the binary name."""
        with pytest.raises(RuntimeError, match="Command not found"):
            run_cmd(["nonexistent_binary_xyz_12345"])

    def test_nonzero_exit_raises(self):
        """A command that exits with a non-zero status (e.g. ``false``) should
        raise RuntimeError with a ``'Command failed'`` message that includes
        the return code."""
        with pytest.raises(RuntimeError, match="Command failed"):
            run_cmd(["false"])

    def test_empty_stdout(self):
        """A command that produces no output (e.g. ``true``) should return
        an empty string rather than None."""
        result = run_cmd(["true"])
        assert result == ""

    # -- merge_stderr ---------------------------------------------------------

    def test_merge_stderr_captures_stderr(self):
        """When ``merge_stderr=True``, output written to stderr by the child
        process should appear in the returned string."""
        result = run_cmd(
            ["sh", "-c", "echo out; echo err >&2"],
            merge_stderr=True,
        )
        assert "out" in result
        assert "err" in result

    def test_default_does_not_include_stderr(self):
        """By default (``merge_stderr=False``), only stdout is returned and
        stderr content should be absent."""
        result = run_cmd(["sh", "-c", "echo out; echo err >&2"])
        assert "out" in result
        assert "err" not in result

    def test_merge_stderr_error_reports_combined_output(self):
        """When ``merge_stderr=True`` and the command fails, the RuntimeError
        message should include the combined output (since stderr is merged
        into stdout)."""
        with pytest.raises(RuntimeError, match="fail msg") as exc_info:
            run_cmd(
                ["sh", "-c", "echo 'fail msg' >&2; exit 1"],
                merge_stderr=True,
            )
