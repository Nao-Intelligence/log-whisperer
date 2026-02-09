from __future__ import annotations

from typing import List

from ._subprocess import run_cmd


def read_docker(container: str, since: str, limit: int) -> List[str]:
    out = run_cmd(["docker", "logs", "--since", since, container])
    return out.splitlines()[-limit:]
