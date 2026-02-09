"""Shared pytest fixtures for the LogWhisperer test suite.

Provides reusable temporary directories, file paths, sample data, and
argument factories so individual test modules stay focused on assertions
rather than boilerplate setup.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """Create and return an isolated temporary directory for state files.

    Used as the parent directory for both the pattern database and the
    baseline state file, ensuring tests never touch the real XDG state
    directory.
    """
    d = tmp_path / "state"
    d.mkdir()
    return d


@pytest.fixture
def db_path(state_dir: Path) -> Path:
    """Return a path inside ``state_dir`` for a temporary patterns.db file.

    The file does not exist yet — PatternDB.__init__ will create it when
    a test instantiates the database.
    """
    return state_dir / "patterns.db"


@pytest.fixture
def baseline_path(state_dir: Path) -> Path:
    """Return a path inside ``state_dir`` for a temporary baseline.json file.

    Like ``db_path``, the file is not pre-created so tests can verify
    behaviour on both missing and existing baseline files.
    """
    return state_dir / "baseline.json"


@pytest.fixture
def sample_lines() -> list[str]:
    """Provide a list of realistic raw log lines with varied content.

    The lines cover multiple formats (ISO timestamps, syslog prefixes),
    severity levels (ERROR, warn, INFO), and variable tokens (IPs, UUIDs,
    paths, numbers) so normalizer and severity tests can exercise a range
    of real-world inputs.
    """
    return [
        # ISO-8601 timestamp with timezone offset and an IPv4 address
        "2024-01-15T10:30:45.123+00:00 Connection established from 192.168.1.100",
        # Classic syslog prefix with PID, contains "Failed" (ERROR keyword)
        "Jan 15 10:30:46 myhost sshd[12345]: Failed password for root from 10.0.0.1 port 22",
        # No timestamp prefix; bare ERROR keyword and a file path
        "ERROR: Disk usage critical on /dev/sda1 (95%)",
        # ISO timestamp with Zulu suffix; "warning" and "timeout" (WARN keywords)
        "2024-01-15T10:30:47.000Z warning: connection timeout for upstream server",
        # Contains a UUID and a bare number (42ms)
        "Request abc12345-dead-beef-cafe-123456789abc completed in 42ms",
        # INFO-level line with a number and a file path
        "INFO  Processing batch 1024 items from /var/log/app/data.csv",
        # Kernel-style log with brackets and numbers
        "kernel: [  123.456789] eth0: link up, speed 1000Mbps, duplex full",
        # Multiple ERROR keywords ("exception", "traceback")
        "ERROR: exception in handler - traceback follows",
        # WARN-level: "warn" and "retry" keywords with a bare number
        "warn: retry attempt 3 for service foo-bar",
        # Clean line with ISO timestamp; no severity keywords (INFO default)
        "2024-01-15T10:31:00.000Z normal operation log line without issues",
    ]


@pytest.fixture
def make_args():
    """Factory fixture that builds ``argparse.Namespace`` objects with sensible defaults.

    Callers pass keyword overrides for only the fields they care about;
    everything else gets a safe default (empty strings, False, etc.) that
    mirrors what ``parse_args`` would produce for an unconfigured run.

    Example::

        args = make_args(file="/tmp/app.log", min_severity="ERROR")
    """

    def _make(**overrides) -> argparse.Namespace:
        # Mirror every attribute that cli.parse_args sets on the Namespace
        # so tests never hit AttributeError on an unexpected missing field.
        defaults = dict(
            # Log source flags — exactly one must be truthy for normal runs
            docker="",
            compose="",
            compose_all=False,
            service="",
            file="",
            # Analysis parameters
            since="1h",
            lines=5000,
            show_new=False,
            min_severity="INFO",
            show_samples=False,
            json=False,
            # State file paths (tests override these with tmp_path derivatives)
            state_db="",
            baseline_state="",
            reset=False,
            baseline_learn="",
            # Notification channel settings — all disabled by default
            notify_ntfy_topic="",
            notify_ntfy_server="https://ntfy.sh",
            notify_telegram_token="",
            notify_telegram_chat_id="",
            notify_email_host="",
            notify_email_port=587,
            notify_email_user="",
            notify_email_pass="",
            notify_email_from="",
            notify_email_to="",
            notify_email_no_tls=False,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    return _make
