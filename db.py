"""
Storage — a thin SQLite layer.

Deduplication is done with a UNIQUE constraint on the article URL rather than
a "have I seen this?" check in Python: we just try to insert and let SQLite
reject duplicates. Simpler, and free of races.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source         TEXT NOT NULL,
    category       TEXT NOT NULL,
    title          TEXT NOT NULL,
    link           TEXT NOT NULL UNIQUE,
    published      TEXT,
    summary        TEXT,
    sentiment      TEXT,
    tags           TEXT,          -- JSON-encoded list
    why_it_matters TEXT,
    engine         TEXT,          -- 'claude' or 'offline-lsa'
    fetched_at     TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def save_article(conn: sqlite3.Connection, article: dict) -> bool:
    """
    Insert one enriched article. Returns True if stored, False if it was a
    duplicate (same link already present).
    """
    try:
        conn.execute(
            """
            INSERT INTO articles
                (source, category, title, link, published,
                 summary, sentiment, tags, why_it_matters, engine, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article["source"],
                article["category"],
                article["title"],
                article["link"],
                article.get("published"),
                article.get("summary"),
                article.get("sentiment"),
                json.dumps(article.get("tags", [])),
                article.get("why_it_matters"),
                article.get("engine"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate link — the UNIQUE constraint did its job


def save_many(conn: sqlite3.Connection, articles: list[dict]) -> int:
    """Save a batch; returns the count of newly-inserted (non-duplicate) rows."""
    inserted = sum(save_article(conn, a) for a in articles)
    conn.commit()
    return inserted


def _rows_to_dicts(rows) -> list[dict]:
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
        out.append(d)
    return out


def list_articles(
    conn: sqlite3.Connection, category: str | None = None, limit: int = 20
) -> list[dict]:
    """Most recently fetched articles, optionally filtered by category."""
    if category:
        rows = conn.execute(
            "SELECT * FROM articles WHERE category = ? ORDER BY fetched_at DESC LIMIT ?",
            (category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY fetched_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return _rows_to_dicts(rows)


def recent(conn: sqlite3.Connection, hours: int = 24) -> list[dict]:
    """Articles fetched within the last `hours` — used to build the digest."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT * FROM articles WHERE fetched_at >= ? ORDER BY category, fetched_at DESC",
        (cutoff,),
    ).fetchall()
    return _rows_to_dicts(rows)
