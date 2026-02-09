from __future__ import annotations

import hashlib
import re

_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_HASH_RE = re.compile(r"\b[0-9a-f]{32,64}\b", re.I)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC_RE = re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.I)
_HEX_RE = re.compile(r"\b0x[0-9a-f]+\b", re.I)
_NUM_RE = re.compile(r"\b\d+\b")
_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._-]+)+")

_SYSLOG_PREFIX_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[^ ]+\s+[^:]+:\s*")
_ISO_TS_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.+-]+\s*")


def normalize_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""

    line = _SYSLOG_PREFIX_RE.sub("", line)
    line = _ISO_TS_PREFIX_RE.sub("", line)

    line = _UUID_RE.sub("<UUID>", line)
    line = _HASH_RE.sub("<HASH>", line)
    line = _IP_RE.sub("<IP>", line)
    line = _MAC_RE.sub("<MAC>", line)
    line = _HEX_RE.sub("<HEX>", line)
    line = _PATH_RE.sub("<PATH>", line)
    line = _NUM_RE.sub("<N>", line)

    line = re.sub(r"\s+", " ", line).strip()
    return line


def pattern_hash(pattern: str) -> str:
    return hashlib.sha1(pattern.encode("utf-8")).hexdigest()
