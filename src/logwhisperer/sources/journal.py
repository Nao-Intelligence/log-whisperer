"""Read logs from a systemd unit via ``journalctl``."""

from __future__ import annotations

from typing import List

from ._subprocess import run_cmd


def read_journal(service: str, since: str, limit: int) -> List[str]:
    """Fetch the last *limit* journal lines for systemd unit *service*.

    Uses ``-o cat`` to output bare log messages without journal metadata.
    """
    out = run_cmd(["journalctl", "-u", service, "--since", since, "-o", "cat", "--no-pager"])
    return out.splitlines()[-limit:]
