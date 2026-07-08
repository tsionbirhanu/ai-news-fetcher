"""
Scheduler — the "always-on automation" layer.

A thin loop on top of the pipeline: fetch every N minutes, and send a digest
once a day at a configured hour. Deliberately dependency-free (just time.sleep)
so there's nothing to learn beyond the standard library. Ctrl+C to stop.
"""

from __future__ import annotations

import time
from datetime import date, datetime

import db
from config import settings
from digest import build_digest
from notifier import send_telegram
from pipeline import fetch_and_store


def _send_daily_digest() -> None:
    conn = db.connect()
    try:
        articles = db.recent(conn, hours=24)
    finally:
        conn.close()

    report = build_digest(articles, title="Daily AI News Digest")
    print("\n" + report + "\n")
    send_telegram(report)


def run() -> None:
    interval = settings.fetch_interval_minutes
    print(
        f"Scheduler started — fetching every {interval} min using "
        f"{settings.engine_label}, daily digest at {settings.digest_hour:02d}:00. "
        f"Ctrl+C to stop.\n"
    )

    last_digest_day: date | None = None

    try:
        while True:
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] fetch cycle…")
            stats = fetch_and_store()
            print(
                f"  fetched {stats['fetched']}, "
                f"new {stats['new']}, duplicates {stats['duplicates']}"
            )

            now = datetime.now()
            if now.hour >= settings.digest_hour and last_digest_day != now.date():
                print(f"[{stamp}] sending daily digest…")
                _send_daily_digest()
                last_digest_day = now.date()

            time.sleep(interval * 60)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
