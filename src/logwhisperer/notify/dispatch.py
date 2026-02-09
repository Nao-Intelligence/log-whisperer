from __future__ import annotations

from typing import List

from .ntfy import notify_ntfy
from .telegram import notify_telegram
from .email_smtp import notify_email_smtp


def dispatch_notifications(args, message: str) -> List[str]:
    failures: List[str] = []

    # ntfy
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

    # Telegram
    if getattr(args, "notify_telegram_token", "") and getattr(args, "notify_telegram_chat_id", ""):
        try:
            notify_telegram(args.notify_telegram_token, args.notify_telegram_chat_id, message)
        except Exception as e:
            failures.append(f"telegram: {e}")

    # Email
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
