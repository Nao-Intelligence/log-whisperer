from __future__ import annotations

from typing import List

from ._subprocess import run_cmd


def read_compose(service: str, since: str, limit: int) -> List[str]:
    out = run_cmd(["docker", "compose", "logs", "--since", since, "--no-color", service])
    return out.splitlines()[-limit:]


def read_compose_all(since: str, limit: int) -> List[str]:
    out = run_cmd(["docker", "compose", "logs", "--since", since, "--no-color"])
    return out.splitlines()[-limit:]
