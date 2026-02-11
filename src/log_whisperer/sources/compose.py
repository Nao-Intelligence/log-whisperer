"""Read logs from Docker Compose services via ``docker compose logs``."""

from __future__ import annotations

from typing import List

from ._subprocess import run_cmd


def read_compose(service: str, since: str, limit: int) -> List[str]:
    """Fetch the last *limit* log lines from a single Compose *service*."""
    out = run_cmd(["docker", "compose", "logs", "--since", since, "--no-color", service], merge_stderr=True)
    return out.splitlines()[-limit:]


def read_compose_all(since: str, limit: int) -> List[str]:
    """Fetch the last *limit* log lines from all Compose services."""
    out = run_cmd(["docker", "compose", "logs", "--since", since, "--no-color"], merge_stderr=True)
    return out.splitlines()[-limit:]
