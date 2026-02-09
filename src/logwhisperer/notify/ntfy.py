"""Send push notifications via the ntfy pub/sub service."""

from __future__ import annotations

import requests


def notify_ntfy(topic: str, message: str, server: str = "https://ntfy.sh", title: str = "Log Whisperer") -> None:
    """POST *message* to an ntfy *topic*.

    Uses the ntfy REST API: ``POST /<topic>`` with the message as body
    and the notification title in an HTTP header.
    """
    url = f"{server.rstrip('/')}/{topic}"
    headers = {"Title": title}
    r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=10)
    r.raise_for_status()
