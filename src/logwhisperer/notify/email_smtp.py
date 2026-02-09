"""Send alert emails via SMTP (with optional STARTTLS)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage


def notify_email_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    use_tls: bool = True,
) -> None:
    """Send a plain-text email from *sender* to *recipient* via SMTP.

    Connects to *host*:*port*, optionally upgrades to TLS with STARTTLS,
    and authenticates if *username* is non-empty.
    """
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=15) as s:
        if use_tls:
            s.starttls()
        if username:
            s.login(username, password)
        s.send_message(msg)
