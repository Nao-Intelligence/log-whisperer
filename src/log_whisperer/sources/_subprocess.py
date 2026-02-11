"""Shared subprocess helper used by docker, compose, and journal sources.

Centralises command execution so error handling (missing binary, non-zero
exit) is consistent and not duplicated across source modules.
"""

from __future__ import annotations

import subprocess
from typing import List


def run_cmd(cmd: List[str], *, merge_stderr: bool = False) -> str:
    """Run *cmd* and return its stdout as a string.

    Args:
        cmd: Command and arguments to execute.
        merge_stderr: If *True*, stderr is merged into stdout so that
            both streams are included in the returned string.

    Raises:
        RuntimeError: If the executable is not found or exits non-zero.
    """
    try:
        p = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}")
    if p.returncode != 0:
        err = p.stdout.strip() if merge_stderr else p.stderr.strip()
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{err}")
    return p.stdout
