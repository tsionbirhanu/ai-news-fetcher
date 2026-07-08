"""
Fetcher — pulls raw articles from RSS feeds. No AI here.

This layer knows nothing about Claude, SQLite, or scheduling. It just turns
RSS/Atom feeds into plain Python dicts. Keeping it isolated is what makes the
rest of the pipeline independently testable.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import feedparser

from config import load_feeds, settings


def clean_html(raw: str) -> str:
    """Strip HTML tags from an RSS summary/description field."""
    return re.sub(r"<[^>]+>", "", raw or "").strip()


def _published(entry) -> str:
    """Best-effort ISO timestamp for an entry (falls back to 'now')."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def fetch_feed(name: str, url: str, category: str, limit: int) -> list[dict]:
    """Fetch and parse a single RSS feed, returning up to `limit` raw articles."""
    parsed = feedparser.parse(url)
    articles: list[dict] = []

    for entry in parsed.entries[:limit]:
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        articles.append(
            {
                "source": name,
                "category": category,
                "title": entry.get("title", "Untitled").strip(),
                "link": entry.get("link", "").strip(),
                "published": _published(entry),
                "raw_summary": clean_html(raw_summary),
            }
        )

    return articles


def fetch_all(category: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Fetch every configured feed (or just one category).

    A single failing feed never aborts the run — automation scripts run
    unattended, so they must survive individual failures.
    """
    limit = settings.articles_per_feed if limit is None else limit
    collected: list[dict] = []

    for name, url, cat in load_feeds(category):
        try:
            collected.extend(fetch_feed(name, url, cat, limit))
        except Exception as exc:  # noqa: BLE001 — never let one feed kill the batch
            print(f"  ! could not fetch {name}: {exc}")

    return collected
