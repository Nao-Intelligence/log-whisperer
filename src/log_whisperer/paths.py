"""XDG-compliant state directory resolution."""

from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "logwhisperer"


def default_state_dir() -> Path:
    """Return the directory for persistent state (pattern DB, baseline).

    Follows the XDG Base Directory Specification: uses ``$XDG_STATE_HOME``
    if set, otherwise falls back to ``~/.local/state/logwhisperer``.
    """
    state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state_home) / APP_NAME
