from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "logwhisperer"


def default_state_dir() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state_home) / APP_NAME
