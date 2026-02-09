"""Fan-out notification dispatcher.

Checks CLI args / env vars for each configured channel (ntfy, Telegram,
email) and sends the alert message to all that are configured.  Failures
are collected rather than raised so one broken channel doesn't block others.
"""

from __future__ import annotations

from typing import List

from .ntfy import notify_ntfy
from .telegram import notify_telegram
from .email_smtp import notify_email_smtp


def dispatch_notifications(args, message: str) -> List[str]:
    """Send *message* to every notification channel configured in *args*.

    Returns a list of human-readable failure descriptions (empty on success).
    Each channel is attempted independently — a failure in one does not
    prevent delivery to the others.
    """
    failures: List[str] = []

    if getattr(args, "notify_ntfy_topic", ""):
        try:
            notify_ntfy(
                topic=args.notify_ntfy_topic,
                message=message,
                server=args.notify_ntfy_server,
                title="Log Whisperer Alert",
            )
        except Exception as e:
            failures.append(f"ntfy: {e}")

    if getattr(args, "notify_telegram_token", "") and getattr(args, "notify_telegram_chat_id", ""):
        try:
            notify_telegram(args.notify_telegram_token, args.notify_telegram_chat_id, message)
        except Exception as e:
            failures.append(f"telegram: {e}")

    # Email requires at minimum a host, sender, and recipient
    email_ready = all(
        [
            getattr(args, "notify_email_host", ""),
            getattr(args, "notify_email_from", ""),
            getattr(args, "notify_email_to", ""),
        ]
    )
    if email_ready:
        try:
            notify_email_smtp(
                host=args.notify_email_host,
                port=args.notify_email_port,
                username=args.notify_email_user,
                password=args.notify_email_pass,
                sender=args.notify_email_from,
                recipient=args.notify_email_to,
                subject="Log Whisperer Alert: New log patterns detected",
                body=message,
                use_tls=not args.notify_email_no_tls,
            )
        except Exception as e:
            failures.append(f"email: {e}")

    return failures
