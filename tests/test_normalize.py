"""Tests for logwhisperer.normalize — line normalization and pattern hashing.

Validates that ``normalize_line`` correctly strips timestamp prefixes and
replaces variable tokens (UUIDs, hashes, IPs, MACs, hex literals, paths,
bare numbers) with stable placeholders.  Also verifies that
``pattern_hash`` produces consistent, collision-resistant SHA-1 digests.
"""

from logwhisperer.normalize import normalize_line, pattern_hash


class TestNormalizeLine:
    """Verify placeholder substitution and timestamp stripping in ``normalize_line``."""

    def test_empty_input(self):
        """An empty string should normalize to an empty string."""
        assert normalize_line("") == ""

    def test_whitespace_only(self):
        """A string containing only whitespace/newlines should normalize to empty."""
        assert normalize_line("   \t  \n") == ""

    def test_iso_timestamp_stripped(self):
        """An ISO-8601 timestamp prefix (e.g. 2024-01-15T10:30:45.123+00:00)
        should be removed so it does not affect pattern identity."""
        result = normalize_line("2024-01-15T10:30:45.123+00:00 hello world")
        assert "2024" not in result
        assert "hello world" in result

    def test_syslog_prefix_stripped(self):
        """A classic syslog prefix (month day time host program:) should be
        fully removed, leaving only the log message body."""
        result = normalize_line("Jan 15 10:30:46 myhost sshd[12345]: login attempt")
        # Both the date portion and hostname should be gone
        assert "Jan" not in result
        assert "myhost" not in result
        # The actual message after the colon must survive
        assert "login attempt" in result

    def test_uuid_replaced(self):
        """Standard UUIDs (8-4-4-4-12 hex groups) should become ``<UUID>``."""
        result = normalize_line("id=abc12345-dead-beef-cafe-123456789abc done")
        assert "<UUID>" in result
        assert "abc12345-dead-beef-cafe-123456789abc" not in result

    def test_hash_replaced(self):
        """Hex strings of 32-64 characters (e.g. SHA-1 commit hashes) should
        become ``<HASH>``."""
        result = normalize_line("commit a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2 merged")
        assert "<HASH>" in result

    def test_ipv4_replaced(self):
        """Dotted-quad IPv4 addresses should become ``<IP>``."""
        result = normalize_line("connection from 192.168.1.100 accepted")
        assert "<IP>" in result
        assert "192.168.1.100" not in result

    def test_mac_replaced(self):
        """Colon-separated MAC addresses (aa:bb:cc:dd:ee:ff) should become ``<MAC>``."""
        result = normalize_line("device aa:bb:cc:dd:ee:ff connected")
        assert "<MAC>" in result
        assert "aa:bb:cc:dd:ee:ff" not in result

    def test_hex_literal_replaced(self):
        """C-style hex literals (0x...) should become ``<HEX>``."""
        result = normalize_line("address 0xDEADBEEF accessed")
        assert "<HEX>" in result
        assert "0xDEADBEEF" not in result

    def test_path_replaced(self):
        """Unix file paths (sequences of /component segments) should become ``<PATH>``."""
        result = normalize_line("reading /var/log/syslog failed")
        assert "<PATH>" in result
        assert "/var/log/syslog" not in result

    def test_bare_numbers_replaced(self):
        """Standalone decimal numbers should become ``<N>``.
        Multiple numbers in the same line should each be replaced."""
        result = normalize_line("processed 1024 items in 42 seconds")
        assert "<N>" in result
        assert "1024" not in result
        assert "42" not in result

    def test_multiple_substitutions(self):
        """A line containing an IP, a number, a path, *and* a timestamp prefix
        should have all variable parts replaced in a single pass."""
        line = "2024-01-15T10:30:00Z 192.168.1.1 sent 500 bytes to /tmp/out"
        result = normalize_line(line)
        # Each token type should be replaced
        assert "<IP>" in result
        assert "<N>" in result
        assert "<PATH>" in result
        # Timestamp prefix should have been stripped
        assert "2024" not in result

    def test_whitespace_collapsed(self):
        """Runs of spaces and tabs should be collapsed into single spaces so
        patterns remain stable regardless of log formatting quirks."""
        result = normalize_line("hello   world\t\tfoo")
        assert result == "hello world foo"


class TestPatternHash:
    """Verify that ``pattern_hash`` produces stable SHA-1 hex digests."""

    def test_returns_hex_digest(self):
        """The hash should be a 40-character lowercase hex string (SHA-1)."""
        h = pattern_hash("some pattern")
        assert len(h) == 40
        assert all(c in "0123456789abcdef" for c in h)

    def test_consistent(self):
        """Hashing the same input twice must return the exact same digest."""
        assert pattern_hash("test") == pattern_hash("test")

    def test_different_patterns_different_hashes(self):
        """Two distinct inputs should produce different digests (no collisions
        for trivially different strings)."""
        assert pattern_hash("pattern A") != pattern_hash("pattern B")
