"""
Digest — turns stored articles into a readable Markdown report.

Pure formatting: give it a list of article dicts, get back a string. No I/O,
which makes it trivial to test and reuse (CLI output, Telegram, a file, ...).
"""

from __future__ import annotations

from datetime import datetime

_SENTIMENT_ICON = {
    "positive": "🟢",
    "neutral": "⚪",
    "negative": "🔴",
    "unknown": "⚫",
}


def _article_block(index: int, art: dict) -> list[str]:
    icon = _SENTIMENT_ICON.get(art.get("sentiment", "unknown"), "⚫")
    lines = [f"**{index}. {art['title']}**  {icon}"]
    if art.get("summary"):
        lines.append(f"> {art['summary']}")
    if art.get("why_it_matters"):
        lines.append(f"_Why it matters:_ {art['why_it_matters']}")
    if art.get("tags"):
        lines.append("`" + "` `".join(art["tags"]) + "`")
    if art.get("link"):
        lines.append(f"[Read more]({art['link']}) — _{art['source']}_")
    lines.append("")  # spacer
    return lines


def build_digest(articles: list[dict], title: str = "AI News Digest") -> str:
    """Render articles grouped by category into a Markdown digest."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 📰 {title} — {stamp}", ""]

    if not articles:
        lines.append("_No articles in this window._")
        return "\n".join(lines)

    by_category: dict[str, list[dict]] = {}
    for art in articles:
        by_category.setdefault(art.get("category", "other"), []).append(art)

    for category, items in by_category.items():
        lines.append(f"## {category.title()}")
        lines.append("")
        for i, art in enumerate(items, start=1):
            lines.extend(_article_block(i, art))

    lines.append(f"_{len(articles)} articles._")
    return "\n".join(lines)
