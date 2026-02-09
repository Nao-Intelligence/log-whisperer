from __future__ import annotations

from typing import List

from ._subprocess import run_cmd


def read_journal(service: str, since: str, limit: int) -> List[str]:
    out = run_cmd(["journalctl", "-u", service, "--since", since, "-o", "cat", "--no-pager"])
    return out.splitlines()[-limit:]
