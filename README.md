# 📰 AI News Fetcher

> Pulls live headlines from RSS feeds, uses an **LLM** to summarize, tag, and
> sentiment-score each article, stores them in **SQLite**, and can run on a
> **schedule** with a daily **Telegram** digest.

A small, readable AI-automation project built to learn the patterns that show up
in almost every real automation: turning model output into structured data,
surviving failures unattended, and running on a timer.

**Works with whatever you've got:**

| You provide…                | It uses…                                  |
| --------------------------- | ----------------------------------------- |
| A Google **Gemini** key     | Gemini 2.5 Flash (**free tier**) — default |
| An Anthropic **Claude** key | Claude                                    |
| No key at all               | An **offline** LSA summarizer (never fails) |

The provider is picked automatically from whichever key is present.

---

## ✨ Features

- **Structured AI enrichment** — each article gets a summary, a sentiment label
  (🟢/⚪/🔴), 2–4 topic tags, and a one-line "why it matters", returned as
  guaranteed-valid JSON.
- **Graceful degradation** — a failed API call never crashes the run; it falls
  back to a local extractive summary.
- **Automatic deduplication** — the same article is never stored twice.
- **Category feeds** — world / tech / business / science, configured in
  `feeds.json` (no code changes to add sources).
- **Daily Telegram digest** — optional, zero extra dependencies.
- **Always-on scheduler** — fetch every N minutes, digest once a day.

---

## 🧱 How the pieces fit together

```
fetcher.py     -> pulls raw articles from RSS feeds            (no AI)
summarizer.py  -> LLM: summary + sentiment + tags + "why"      (the AI part;
                  Gemini or Claude, auto-picked by key; falls
                  back to offline LSA when no key / API fails)
db.py          -> stores/reads articles in SQLite (news.db), deduped by URL
digest.py      -> formats stored articles into a Markdown digest
notifier.py    -> optional Telegram delivery (standard library only)
pipeline.py    -> one fetch cycle: fetch -> summarize -> store
scheduler.py   -> automation: runs the pipeline on a timer + daily digest
main.py        -> the CLI you actually run
config.py      -> all settings (.env) and the feed list (feeds.json)
```

Data flow for one cycle:

```
RSS feeds --(fetcher)--> raw articles --(summarizer, LLM)--> enriched --(db)--> news.db
```

Each layer knows nothing about the ones above it — `fetcher`/`summarizer`/`db`
have no idea scheduling exists, which is what makes them easy to test in
isolation.

---

## 🚀 Quickstart (Windows / PowerShell)

```powershell
# 1. Create a virtual environment and install dependencies
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. Download the tokenizer data used by the offline fallback (one time)
python setup_nltk.py

# 3. Create your .env from the template, then edit it
copy .env.example .env
notepad .env                     # paste your GEMINI_API_KEY here

# 4. Fetch, summarize, and store your first articles
python main.py fetch --category tech
```

> **macOS / Linux:** use `source venv/bin/activate` and `cp .env.example .env`.

Get a **free** Gemini key at <https://aistudio.google.com/apikey>. No key? The
app still runs — it uses the offline summarizer automatically.

> ⚠️ Put real keys **only in `.env`** — never in `.env.example` (that file is a
> shareable template, and `.env` is the one the app actually reads).

---

## 🕹️ Commands

| Command                              | What it does                                  |
| ------------------------------------ | --------------------------------------------- |
| `python main.py fetch`               | Fetch + summarize + store, all categories     |
| `python main.py fetch --category tech` | Just one category                           |
| `python main.py list`                | Show what's stored                            |
| `python main.py list --category world --limit 5` | Filtered listing                  |
| `python main.py digest`              | Build the last-24h digest                     |
| `python main.py digest --send`       | Build it **and** push to Telegram             |
| `python main.py test-telegram`       | Send a one-off test message                   |
| `python main.py run`                 | Start the always-on scheduler (Ctrl+C to stop)|

Add `-h` to any command for its options.

---

## 📤 Example output

```
## Tech

1. Crypto VC firm Paradigm raises $1.2B to invest in 'technical frontier' startups  ⚪
> Paradigm, a venture capital firm focused on crypto, has raised $1.2 billion
  for its third fund to invest in "technical frontier" startups.
Why it matters: Signals continued investment and confidence in the crypto sector.
`crypto` `venture capital` `fundraising` `startups`
Read more — TechCrunch
```

The `⚪` is the sentiment icon (🟢 positive · ⚪ neutral · 🔴 negative · ⚫ offline/unknown).

---

## 📲 Telegram daily digest (optional)

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the **bot token**.
2. Send your new bot any message (e.g. "hi") so it may reply to you.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
   copy the `chat.id` from the JSON.
4. Put both in **`.env`**:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=987654321
   ```
5. Verify:
   ```powershell
   python main.py test-telegram      # sends a hello message
   python main.py digest --send      # pushes the real digest
   ```

Once set, `python main.py run` sends the digest automatically each day at
`DIGEST_HOUR`.

---

## ⚙️ Configuration (`.env`)

| Variable                 | Default            | Purpose                                        |
| ------------------------ | ------------------ | ---------------------------------------------- |
| `LLM_PROVIDER`           | `auto`             | `auto` \| `gemini` \| `claude` \| `offline`    |
| `GEMINI_API_KEY`         | —                  | Google Gemini key (free tier)                  |
| `GEMINI_MODEL`           | `gemini-2.5-flash` | Gemini model id                                |
| `ANTHROPIC_API_KEY`      | —                  | Anthropic Claude key                           |
| `CLAUDE_MODEL`           | `claude-opus-4-8`  | Claude model id                                |
| `ARTICLES_PER_FEED`      | `5`                | How many items to pull per feed                |
| `MAX_WORKERS`            | `4`                | Parallel requests (Claude only; see note)      |
| `FETCH_INTERVAL_MINUTES` | `30`               | Scheduler fetch interval                       |
| `DIGEST_HOUR`            | `8`                | Hour (0–23) the daily digest is sent           |
| `TELEGRAM_BOT_TOKEN`     | —                  | Telegram bot token                             |
| `TELEGRAM_CHAT_ID`       | —                  | Your Telegram chat id                          |

Feeds live in `feeds.json`, grouped by category — edit that file to add or
remove sources, no code changes needed.

> **Gemini free-tier note:** the free tier allows ~5 requests/minute, so Gemini
> runs **one article at a time** and automatically waits out any rate-limit.
> Keep `ARTICLES_PER_FEED` small (3–5) for quick runs.

---

## 🧠 Patterns worth studying

- **Structured output** (`summarizer.py`) — the response is constrained to a JSON
  schema so the code can trust its shape instead of parsing free-form text. The
  single most useful pattern in AI automation. (Note: Gemini and Claude each want
  a slightly different schema dialect — see `_GEMINI_SCHEMA`.)
- **Graceful degradation** — `summarize_and_tag()` catches any provider error and
  falls back to a real offline summary. Unattended scripts must survive failures.
- **Dedup via constraints** (`db.py`) — a `UNIQUE(link)` column does the work; we
  just catch the integrity error. Simpler and race-free.
- **Separation of concerns** — fetch / summarize / store are independent layers;
  the scheduler is a thin wrapper on top.
- **Rate-limit-aware batching** (`summarizer.py`) — parallel for Claude,
  sequential-with-retry for Gemini's free tier.

---

## 🩹 Troubleshooting

| Symptom                                             | Fix                                                        |
| --------------------------------------------------- | ---------------------------------------------------------- |
| `Telegram is not configured`                        | Your values are in `.env.example`, not `.env`. Put them in `.env`. |
| `The module 'env' could not be loaded`              | You typed `env\Scripts` — it's `venv\Scripts` (with the `v`). |
| `429 RESOURCE_EXHAUSTED` from Gemini                | Free-tier limit. It auto-retries; lower `ARTICLES_PER_FEED`. |
| A feed returns 0 articles                           | That feed may be down (the NASA/science feed sometimes is). Use another category. |
| Emoji look garbled in the terminal                  | Handled — `main.py` forces UTF-8 output on Windows.        |

---

## 🌱 Ideas to extend it

- Add NewsAPI.org as a second source alongside RSS.
- Ask the LLM to **cluster** articles from different sources about the same story.
- Swap SQLite for Postgres + SQLAlchemy if this grows into a real service.
- Wrap it in **FastAPI** and expose `/articles` and `/digest` endpoints.
- Add an email digest alongside Telegram.
