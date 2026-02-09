"""Log line normalizer that replaces variable data with stable placeholders.

The normalizer strips timestamp prefixes and substitutes runtime-specific
values (IPs, UUIDs, hex literals, file paths, bare numbers) so that
structurally identical log lines collapse into a single pattern string.

Substitution order matters: UUIDs and long hashes are matched before the
generic number regex to avoid partial replacements.
"""

from __future__ import annotations

import hashlib
import re

# --- Variable-data patterns (matched in this order) --------------------------
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_HASH_RE = re.compile(r"\b[0-9a-f]{32,64}\b", re.I)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC_RE = re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.I)
_HEX_RE = re.compile(r"\b0x[0-9a-f]+\b", re.I)
_NUM_RE = re.compile(r"\b\d+\b")
_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._-]+)+")

# --- Timestamp prefixes to strip before normalizing --------------------------
_SYSLOG_PREFIX_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[^ ]+\s+[^:]+:\s*")
_ISO_TS_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.+-]+\s*")


def normalize_line(line: str) -> str:
    """Strip timestamps and replace variable tokens with placeholders.

    Returns the normalized pattern string, or ``""`` for blank lines.
    """
    line = line.strip()
    if not line:
        return ""

    # Strip leading timestamp so it doesn't affect pattern identity
    line = _SYSLOG_PREFIX_RE.sub("", line)
    line = _ISO_TS_PREFIX_RE.sub("", line)

    # Replace specific types before generic numbers to avoid partial matches
    line = _UUID_RE.sub("<UUID>", line)
    line = _HASH_RE.sub("<HASH>", line)
    line = _IP_RE.sub("<IP>", line)
    line = _MAC_RE.sub("<MAC>", line)
    line = _HEX_RE.sub("<HEX>", line)
    line = _PATH_RE.sub("<PATH>", line)
    line = _NUM_RE.sub("<N>", line)

    # Collapse whitespace runs into a single space
    line = re.sub(r"\s+", " ", line).strip()
    return line


def pattern_hash(pattern: str) -> str:
    """Return a stable SHA-1 hex digest for a normalized pattern string."""
    return hashlib.sha1(pattern.encode("utf-8")).hexdigest()
