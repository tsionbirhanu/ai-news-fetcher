
"""
Pipeline — glues the layers together for one fetch cycle.

    fetch (RSS)  ->  summarize (Claude / offline)  ->  store (SQLite, deduped)

Both the CLI and the scheduler call into here, so the "what happens in a cycle"
logic lives in exactly one place.
"""

from __future__ import annotations

import db
from fetcher import fetch_all
from summarizer import summarize_batch


def fetch_and_store(category: str | None = None) -> dict:
    """Run one full cycle and return a small stats summary."""
    raw = fetch_all(category)
    if not raw:
        return {"fetched": 0, "new": 0, "duplicates": 0}

    enriched = summarize_batch(raw)

    conn = db.connect()
    try:
        new = db.save_many(conn, enriched)
    finally:
        conn.close()

    return {"fetched": len(raw), "new": new, "duplicates": len(raw) - new}
