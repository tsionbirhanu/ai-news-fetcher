"""
Central configuration for the AI News Fetcher.

Everything tunable lives here: secrets and knobs come from environment
variables (loaded from a local `.env` file), and the feed list comes from
`feeds.json`. Import `settings` / `load_feeds()` from this module instead of
reading os.environ scattered across the codebase — one place to look.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # no-op if .env is missing


@dataclass(frozen=True)
class Settings:
    # --- AI (the part that makes this "AI automation") ---
    # Which LLM enriches each article. "auto" picks based on which key is set:
    # Gemini first (free tier!), then Claude, else the offline summarizer.
    # Force one explicitly with LLM_PROVIDER=gemini|claude|offline.
    llm_provider: str = os.getenv("LLM_PROVIDER", "auto")

    # Google Gemini — free tier at https://aistudio.google.com/apikey
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Anthropic Claude — https://console.anthropic.com/
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

    # --- storage & fetching ---
    db_file: str = os.getenv("DB_FILE", "news.db")
    articles_per_feed: int = int(os.getenv("ARTICLES_PER_FEED", "5"))
    max_workers: int = int(os.getenv("MAX_WORKERS", "4"))

    # --- automation / scheduling ---
    fetch_interval_minutes: int = int(os.getenv("FETCH_INTERVAL_MINUTES", "30"))
    digest_hour: int = int(os.getenv("DIGEST_HOUR", "8"))  # 24h clock, local time

    # --- optional Telegram delivery ---
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")

    @property
    def db_path(self) -> Path:
        return BASE_DIR / self.db_file

    @property
    def provider(self) -> str:
        """Resolved LLM provider: 'gemini', 'claude', or 'offline'."""
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.gemini_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "claude"
        return "offline"

    @property
    def use_llm(self) -> bool:
        """True when a cloud LLM is available — otherwise we degrade to offline LSA."""
        return self.provider in ("gemini", "claude")

    @property
    def engine_label(self) -> str:
        """Human-readable name of the active summarization engine."""
        return {
            "gemini": f"Gemini ({self.gemini_model})",
            "claude": f"Claude ({self.claude_model})",
        }.get(self.provider, "offline LSA (no API key set)")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


settings = Settings()

_FEEDS_PATH = BASE_DIR / "feeds.json"


def _read_feeds() -> dict[str, dict[str, str]]:
    return json.loads(_FEEDS_PATH.read_text(encoding="utf-8"))


def categories() -> list[str]:
    """All configured category names, e.g. ['world', 'tech', 'business', 'science']."""
    return list(_read_feeds())


def load_feeds(category: str | None = None) -> list[tuple[str, str, str]]:
    """
    Return a flat list of (source_name, url, category) tuples.

    Pass `category` to restrict to one section; omit it for every feed.
    Raises ValueError for an unknown category so the CLI can fail loudly.
    """
    data = _read_feeds()
    if category is not None and category not in data:
        raise ValueError(
            f"Unknown category '{category}'. Known: {', '.join(data) or '(none)'}"
        )

    feeds: list[tuple[str, str, str]] = []
    for cat, sources in data.items():
        if category is not None and cat != category:
            continue
        for name, url in sources.items():
            feeds.append((name, url, cat))
    return feeds
