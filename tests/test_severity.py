"""Tests for logwhisperer.severity — keyword-based severity classification.

Validates that ``severity_of`` correctly classifies log lines as
``"ERROR"``, ``"WARN"``, or ``"INFO"`` based on the presence of known
keywords, with proper case-insensitivity and precedence rules.
"""

import pytest

from logwhisperer.severity import severity_of, ERROR_HINTS, WARN_HINTS


class TestSeverityOf:
    """Verify keyword detection, precedence, and edge cases in ``severity_of``."""

    @pytest.mark.parametrize("keyword", ERROR_HINTS)
    def test_error_keywords(self, keyword):
        """Every keyword in ERROR_HINTS (error, fatal, exception, etc.) should
        cause the line to be classified as ``"ERROR"``."""
        assert severity_of(f"something {keyword} happened") == "ERROR"

    @pytest.mark.parametrize("keyword", WARN_HINTS)
    def test_warn_keywords(self, keyword):
        """Every keyword in WARN_HINTS (warn, timeout, retry, etc.) should
        cause the line to be classified as ``"WARN"``."""
        assert severity_of(f"something {keyword} happened") == "WARN"

    def test_no_keyword_returns_info(self):
        """A line with no recognised severity keyword defaults to ``"INFO"``."""
        assert severity_of("normal log message") == "INFO"

    def test_case_insensitive(self):
        """Keyword matching should be case-insensitive — uppercase, mixed-case,
        and title-case variants must all be recognised."""
        assert severity_of("FATAL ERROR occurred") == "ERROR"
        assert severity_of("Warning: disk full") == "WARN"

    def test_error_precedence_over_warn(self):
        """When both an ERROR keyword and a WARN keyword appear in the same
        line, ERROR should take precedence because ``severity_of`` checks
        ERROR_HINTS first."""
        # "error" is ERROR, "retry" is WARN — ERROR should win
        assert severity_of("error after retry warning") == "ERROR"

    def test_empty_string_returns_info(self):
        """An empty string contains no keywords and should default to ``"INFO"``."""
        assert severity_of("") == "INFO"

    def test_substring_matching(self):
        """Keywords should be matched as substrings within larger words or
        phrases (e.g. 'failed' inside 'connection failed')."""
        assert severity_of("connection failed unexpectedly") == "ERROR"
        assert severity_of("request timed out") == "WARN"
