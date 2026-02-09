from __future__ import annotations

from pathlib import Path
from typing import List


def read_file(path: str, limit: int) -> List[str]:
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"File not found: {p}")
    return p.read_text(errors="ignore").splitlines()[-limit:]
