from __future__ import annotations

import requests


def notify_telegram(token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
