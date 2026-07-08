"""
Notifier — optional Telegram delivery for the daily digest.

Dependency-free: uses the standard library (urllib) so there's nothing extra
to install. Telegram is entirely optional — if the bot token / chat id aren't
configured, send_telegram() is a no-op that just says so.

Setup (one time):
  1. Message @BotFather on Telegram, /newbot, copy the token.
  2. Message your new bot once (say "hi"), then open
     https://api.telegram.org/bot<TOKEN>/getUpdates and read the chat id.
  3. Put TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from config import settings

# Telegram messages cap at 4096 chars; leave a little headroom.
_MAX_LEN = 4000


def send_telegram(text: str) -> bool:
    """Send `text` to the configured chat. Returns True on success."""
    if not settings.telegram_enabled:
        print("  (Telegram not configured — skipping send)")
        return False

    if len(text) > _MAX_LEN:
        text = text[:_MAX_LEN] + "\n… (truncated)"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }
    ).encode()

    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as resp:
            body = json.loads(resp.read())
        if body.get("ok"):
            return True
        print(f"  ! Telegram API error: {body.get('description')}")
        return False
    except urllib.error.URLError as exc:
        print(f"  ! Telegram send failed: {exc}")
        return False


def test_telegram() -> bool:
    """Send a one-off hello message to confirm the bot is wired up correctly."""
    if not settings.telegram_enabled:
        print(
            "Telegram is not configured. Set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID in your .env (see notifier.py for how to get them)."
        )
        return False

    ok = send_telegram("✅ *AI News Fetcher* is connected. Telegram delivery works!")
    print("Test message sent — check your Telegram." if ok else "Test message failed.")
    return ok
