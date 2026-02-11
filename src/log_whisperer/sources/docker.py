"""Read logs from a single Docker container via ``docker logs``."""

from __future__ import annotations

from typing import List

from ._subprocess import run_cmd


def read_docker(container: str, since: str, limit: int) -> List[str]:
    """Fetch the last *limit* log lines from *container* since *since*."""
    out = run_cmd(["docker", "logs", "--since", since, container], merge_stderr=True)
    return out.splitlines()[-limit:]
