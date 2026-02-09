"""Tests for logwhisperer.sources — file reader and read_lines dispatcher.

Validates that ``read_file`` correctly reads the tail of a file and
handles edge cases (missing files, empty files, fewer lines than the
limit).  Also verifies that the ``read_lines`` dispatcher routes CLI
arguments to the correct log source reader and produces the expected
source description string.
"""

import pytest

from logwhisperer.sources.file import read_file
from logwhisperer.sources import read_lines


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------
class TestReadFile:
    """Verify plain text file reading with line-limit slicing."""

    def test_reads_last_n_lines(self, tmp_path):
        """When the file has more lines than the limit, only the last N
        lines should be returned (tail behaviour)."""
        f = tmp_path / "test.log"
        f.write_text("\n".join(f"line{i}" for i in range(20)))
        result = read_file(str(f), limit=5)
        assert len(result) == 5
        # The very last line of the file should be the last element
        assert result[-1] == "line19"

    def test_fewer_lines_than_limit(self, tmp_path):
        """When the file has fewer lines than the limit, all lines should
        be returned without error."""
        f = tmp_path / "test.log"
        f.write_text("one\ntwo\nthree")
        result = read_file(str(f), limit=100)
        assert len(result) == 3

    def test_nonexistent_file_raises(self):
        """Attempting to read a file that does not exist should raise
        RuntimeError with a ``'File not found'`` message."""
        with pytest.raises(RuntimeError, match="File not found"):
            read_file("/tmp/does_not_exist_xyz_12345.log", limit=10)

    def test_empty_file(self, tmp_path):
        """An empty file should return an empty list, not an error."""
        f = tmp_path / "empty.log"
        f.write_text("")
        result = read_file(str(f), limit=10)
        assert result == []


# ---------------------------------------------------------------------------
# read_lines dispatcher
# ---------------------------------------------------------------------------
class TestReadLines:
    """Verify that ``read_lines`` routes to the correct source reader based
    on CLI arguments and returns a ``(lines, src_desc)`` tuple."""

    def test_file_dispatches_correctly(self, tmp_path, make_args):
        """When ``args.file`` is set, ``read_lines`` should call ``read_file``
        and return the file's contents along with a ``'file:<path>'`` descriptor."""
        f = tmp_path / "test.log"
        f.write_text("hello\nworld\n")
        args = make_args(file=str(f))
        lines, src_desc = read_lines(args)
        assert lines == ["hello", "world"]
        assert src_desc == f"file:{f}"

    def test_no_source_raises(self, make_args):
        """When no source flag is set, ``read_lines`` should raise RuntimeError
        because there is nothing to read."""
        args = make_args()
        with pytest.raises(RuntimeError, match="No log source"):
            read_lines(args)

    def test_src_desc_format_file(self, tmp_path, make_args):
        """The source description for file sources should start with the
        ``'file:'`` prefix."""
        f = tmp_path / "app.log"
        f.write_text("log line\n")
        args = make_args(file=str(f))
        _, src_desc = read_lines(args)
        assert src_desc.startswith("file:")

    def test_docker_src_desc(self, make_args, monkeypatch):
        """When ``args.docker`` is set, the dispatcher should call
        ``read_docker`` and produce a ``'docker:<container>'`` descriptor.

        Uses monkeypatch to replace ``read_docker`` so no real Docker
        daemon is needed.
        """
        import logwhisperer.sources as sources_mod
        # Replace the real reader with a stub that returns canned output
        monkeypatch.setattr(
            sources_mod, "read_docker",
            lambda container, since, limit: ["docker line"],
        )
        args = make_args(docker="mycontainer")
        lines, src_desc = read_lines(args)
        assert lines == ["docker line"]
        assert src_desc == "docker:mycontainer"

    def test_service_src_desc(self, make_args, monkeypatch):
        """When ``args.service`` is set, the dispatcher should call
        ``read_journal`` and produce a ``'journal:<unit>'`` descriptor.

        Uses monkeypatch to replace ``read_journal`` so no real
        journalctl binary is needed.
        """
        import logwhisperer.sources as sources_mod
        # Replace the real reader with a stub that returns canned output
        monkeypatch.setattr(
            sources_mod, "read_journal",
            lambda service, since, limit: ["journal line"],
        )
        args = make_args(service="sshd")
        lines, src_desc = read_lines(args)
        assert lines == ["journal line"]
        assert src_desc == "journal:sshd"
