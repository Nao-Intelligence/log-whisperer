"""Tests for logwhisperer.notify.dispatch — notification fan-out dispatcher.

Validates that ``dispatch_notifications`` correctly routes alert messages
to configured channels (ntfy, Telegram, email), skips unconfigured ones,
collects per-channel failures independently, and returns an empty list on
full success.  All external network calls are mocked to keep tests fast
and isolated.
"""

from unittest.mock import patch

from logwhisperer.notify.dispatch import dispatch_notifications


class TestDispatchNotifications:
    """Verify notification channel routing, error collection, and skip logic."""

    def test_no_channels_returns_empty(self, make_args):
        """When no notification channels are configured (all settings empty),
        the dispatcher should do nothing and return an empty failures list."""
        args = make_args()
        failures = dispatch_notifications(args, "test alert")
        assert failures == []

    def test_ntfy_failure_appended(self, make_args):
        """When the ntfy channel is configured but the send fails, the error
        should be captured in the failures list with an ``'ntfy'`` prefix."""
        args = make_args(notify_ntfy_topic="test-topic")
        # Mock notify_ntfy to simulate a network error
        with patch("logwhisperer.notify.dispatch.notify_ntfy", side_effect=Exception("connection error")):
            failures = dispatch_notifications(args, "test alert")
        assert len(failures) == 1
        assert "ntfy" in failures[0]

    def test_telegram_skipped_if_chat_id_missing(self, make_args):
        """Telegram requires both a bot token *and* a chat ID.  If the chat ID
        is missing, the channel should be silently skipped (no failure)."""
        args = make_args(notify_telegram_token="tok123", notify_telegram_chat_id="")
        failures = dispatch_notifications(args, "test alert")
        assert failures == []

    def test_email_skipped_if_host_missing(self, make_args):
        """Email requires a host, sender, and recipient.  If the SMTP host is
        missing, the channel should be silently skipped even when sender and
        recipient are provided."""
        args = make_args(
            notify_email_host="",
            notify_email_from="a@b.com",
            notify_email_to="c@d.com",
        )
        failures = dispatch_notifications(args, "test alert")
        assert failures == []

    def test_all_channels_fail_independently(self, make_args):
        """When all three channels are configured and all three raise, each
        failure should be captured independently — one broken channel must
        not prevent the others from being attempted."""
        args = make_args(
            notify_ntfy_topic="topic",
            notify_telegram_token="tok",
            notify_telegram_chat_id="123",
            notify_email_host="smtp.example.com",
            notify_email_from="a@b.com",
            notify_email_to="c@d.com",
        )
        # Mock all three senders to raise
        with (
            patch("logwhisperer.notify.dispatch.notify_ntfy", side_effect=Exception("ntfy fail")),
            patch("logwhisperer.notify.dispatch.notify_telegram", side_effect=Exception("tg fail")),
            patch("logwhisperer.notify.dispatch.notify_email_smtp", side_effect=Exception("email fail")),
        ):
            failures = dispatch_notifications(args, "test alert")
        # All three channels should have reported a failure
        assert len(failures) == 3

    def test_successful_dispatch_returns_empty(self, make_args):
        """When all three channels are configured and all succeed, the
        failures list should be empty."""
        args = make_args(
            notify_ntfy_topic="topic",
            notify_telegram_token="tok",
            notify_telegram_chat_id="123",
            notify_email_host="smtp.example.com",
            notify_email_from="a@b.com",
            notify_email_to="c@d.com",
        )
        # Mock all three senders to succeed (default mock returns None)
        with (
            patch("logwhisperer.notify.dispatch.notify_ntfy"),
            patch("logwhisperer.notify.dispatch.notify_telegram"),
            patch("logwhisperer.notify.dispatch.notify_email_smtp"),
        ):
            failures = dispatch_notifications(args, "test alert")
        assert failures == []
