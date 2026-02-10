"""Log source dispatcher — routes CLI args to the appropriate reader."""

from __future__ import annotations

from typing import List, Tuple

from .docker import read_docker
from .compose import read_compose, read_compose_all
from .journal import read_journal
from .file import read_file


def read_lines(args) -> Tuple[List[str], str]:
    """Dispatch to the correct log source based on parsed CLI arguments.

    Returns:
        A tuple of ``(lines, source_description)`` where *lines* is a list
        of raw log strings and *source_description* identifies the source
        for report metadata (e.g. ``"docker:myapp"``).

    Raises:
        RuntimeError: If no source flag was set on *args*.
    """
    if args.docker:
        return read_docker(args.docker, args.since, args.lines), f"docker:{args.docker}"

    if args.compose:
        return read_compose(args.compose, args.since, args.lines), f"compose:{args.compose}"

    if args.compose_all:
        return read_compose_all(args.since, args.lines), "compose:all"

    if args.service:
        return read_journal(args.service, args.since, args.lines), f"journal:{args.service}"

    if args.file:
        return read_file(args.file, args.lines), f"file:{args.file}"

    raise RuntimeError("No log source provided.")
