"""
Summarizer — the AI part.

For each article we ask an LLM for a structured enrichment: a short summary, a
sentiment label, topic tags, and a one-line "why it matters". We force valid
JSON with each provider's structured-output feature so the rest of the code can
rely on the shape instead of parsing free-form text.

Two cloud providers are supported — Google Gemini (free tier) and Anthropic
Claude — selected automatically by which API key is set (see config.provider).

Graceful degradation is the whole point of automation code: if there's no key,
or a call fails, we fall back to an *offline* extractive summary (LSA via sumy)
rather than crashing the pipeline. That offline path is the same technique the
project used before it grew an LLM integration.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from config import settings

_SYSTEM_PROMPT = (
    "You are a news desk assistant. Given one article's title and text, produce "
    "a tight, neutral 1-2 sentence summary, a sentiment label for the tone of the "
    "news itself (not your opinion), 2-4 lowercase topic tags, and a single short "
    "sentence on why a reader should care. Be factual and concise."
)

# Structured-output schema. Claude requires `additionalProperties: false`;
# Gemini rejects that key, so it gets a variant without it (below).
_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "why_it_matters": {"type": "string"},
    },
    "required": ["summary", "sentiment", "tags", "why_it_matters"],
    "additionalProperties": False,
}

# Gemini's response_schema is an OpenAPI subset — it doesn't understand
# `additionalProperties`, so strip it for the Gemini call.
_GEMINI_SCHEMA = {k: v for k, v in _SCHEMA.items() if k != "additionalProperties"}

_USER_PROMPT = "Title: {title}\n\nText: {text}"


# ---------------------------------------------------------------------------
# Gemini path (free tier)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _gemini_client():
    """Lazily build one Gemini client (only imported when a key is set)."""
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


_GEMINI_MAX_RETRIES = 3


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _retry_delay(exc: Exception, default: float = 30.0) -> float:
    """Pull Google's suggested wait out of the error message, capped to 60s."""
    match = re.search(r"retry in ([\d.]+)s", str(exc))
    delay = float(match.group(1)) if match else default
    return min(delay + 1.0, 60.0)  # +1s cushion


def _summarize_with_gemini(title: str, text: str) -> dict:
    for attempt in range(_GEMINI_MAX_RETRIES):
        try:
            resp = _gemini_client().models.generate_content(
                model=settings.gemini_model,
                contents=_USER_PROMPT.format(title=title, text=text),
                config={
                    "system_instruction": _SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": _GEMINI_SCHEMA,
                },
            )
            data: dict = json.loads(resp.text)
            data["engine"] = "gemini"
            return data
        except Exception as exc:  # noqa: BLE001
            if _is_rate_limit(exc) and attempt < _GEMINI_MAX_RETRIES - 1:
                wait = _retry_delay(exc)
                print(f"  Gemini rate-limited (free tier = 5/min); waiting {wait:.0f}s…")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")  # loop either returns or raises


# ---------------------------------------------------------------------------
# Claude path
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _claude_client():
    """Lazily build one Anthropic client (only imported when a key is set)."""
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _summarize_with_claude(title: str, text: str) -> dict:
    resp = _claude_client().messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[
            {"role": "user", "content": _USER_PROMPT.format(title=title, text=text)}
        ],
    )
    # With output_config.format the first text block is guaranteed valid JSON.
    payload = next(b.text for b in resp.content if b.type == "text")
    data: dict = json.loads(payload)
    data["engine"] = "claude"
    return data


# ---------------------------------------------------------------------------
# Offline path (fallback) — extractive LSA summary, no API key required
# ---------------------------------------------------------------------------

_LSA_SENTENCES = 2
_LANGUAGE = "english"


def _summarize_offline(text: str) -> dict:
    """
    Local extractive summary using LSA (Latent Semantic Analysis) via sumy.
    Used when Claude is unavailable. Sentiment/tags can't be inferred offline,
    so we mark them as unknown rather than guessing.
    """
    summary = text.strip()
    if len(text.split()) >= 15:
        try:
            from sumy.nlp.stemmers import Stemmer
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.parsers.plaintext import PlaintextParser
            from sumy.summarizers.lsa import LsaSummarizer
            from sumy.utils import get_stop_words

            parser = PlaintextParser.from_string(text, Tokenizer(_LANGUAGE))
            summarizer = LsaSummarizer(Stemmer(_LANGUAGE))
            summarizer.stop_words = get_stop_words(_LANGUAGE)
            sentences = summarizer(parser.document, _LSA_SENTENCES)
            summary = " ".join(str(s) for s in sentences) or text.strip()
        except Exception:  # noqa: BLE001 — offline summary is best-effort
            pass

    return {
        "summary": summary,
        "sentiment": "unknown",
        "tags": [],
        "why_it_matters": "",
        "engine": "offline-lsa",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_PROVIDERS = {
    "gemini": _summarize_with_gemini,
    "claude": _summarize_with_claude,
}


def summarize_and_tag(article: dict) -> dict:
    """
    Enrich one raw article (from fetcher) into an article ready for storage.
    Never raises — falls back to the offline summarizer on any provider error.
    """
    text = article.get("raw_summary", "") or article.get("title", "")
    provider_fn = _PROVIDERS.get(settings.provider)

    if provider_fn is not None:
        try:
            enrichment = provider_fn(article["title"], text)
        except Exception as exc:  # noqa: BLE001 — degrade, don't crash
            print(
                f"  ! {settings.provider} failed for '{article['title'][:50]}': "
                f"{exc}; using offline summary"
            )
            enrichment = _summarize_offline(text)
    else:
        enrichment = _summarize_offline(text)

    return {**article, **enrichment}


def _effective_workers() -> int:
    """
    How many articles to summarize at once.

    Gemini's free tier is rate-limited (5 req/min) and its client isn't
    thread-safe, so we run it sequentially (=1) and lean on retry-on-429.
    Claude parallelizes fine, so it uses the configured MAX_WORKERS.
    """
    if settings.provider == "gemini":
        return 1
    if settings.provider == "claude":
        return settings.max_workers
    return 1  # offline is CPU-bound; no benefit from threads


def summarize_batch(articles: list[dict]) -> list[dict]:
    """
    Enrich many articles. Output order always matches input order.

    Note: free API tiers have per-minute request limits. Gemini runs one at a
    time and waits out any rate-limit; if a big batch is slow, lower
    ARTICLES_PER_FEED in .env.
    """
    if not articles:
        return []

    workers = _effective_workers()
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(summarize_and_tag, articles))

    return [summarize_and_tag(a) for a in articles]
