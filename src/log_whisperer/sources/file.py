"""Read logs from a plain text file."""

from __future__ import annotations

from pathlib import Path
from typing import List


def read_file(path: str, limit: int) -> List[str]:
    """Read the last *limit* lines from the file at *path*.

    Raises:
        RuntimeError: If *path* does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"File not found: {p}")
    return p.read_text(errors="ignore").splitlines()[-limit:]
