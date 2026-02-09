from __future__ import annotations

ERROR_HINTS = (
    "error",
    "fatal",
    "exception",
    "traceback",
    "panic",
    "segfault",
    "failed",
    "failure",
    "critical",
)

WARN_HINTS = (
    "warn",
    "warning",
    "timeout",
    "timed out",
    "retry",
    "throttle",
    "rate limit",
    "deprecated",
    "slow",
    "unavailable",
)


def severity_of(text: str) -> str:
    t = text.lower()
    if any(h in t for h in ERROR_HINTS):
        return "ERROR"
    if any(h in t for h in WARN_HINTS):
        return "WARN"
    return "INFO"
