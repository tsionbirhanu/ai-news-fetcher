"""
AI News Fetcher — command-line entry point.

    python main.py fetch                 # fetch + summarize + store, all categories
    python main.py fetch --category tech # just one category
    python main.py list                  # show what's stored
    python main.py list --category world --limit 5
    python main.py digest                # build (and optionally send) the last-24h digest
    python main.py digest --send         # also push it to Telegram
    python main.py run                   # start the always-on scheduler

Run `python main.py -h` (or `<command> -h`) for the full option list.
"""

from __future__ import annotations

import argparse
import sys

# The digest uses emoji; make sure printing them never crashes on a Windows
# console whose default code page (cp1252) can't encode them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import scheduler
from config import categories, settings
from digest import build_digest
from notifier import send_telegram, test_telegram
from pipeline import fetch_and_store


def cmd_fetch(args: argparse.Namespace) -> None:
    scope = args.category or "all categories"
    print(f"Fetching {scope} — summarizing with {settings.engine_label}…\n")

    stats = fetch_and_store(args.category)
    print(
        f"\nDone: fetched {stats['fetched']}, stored {stats['new']} new, "
        f"skipped {stats['duplicates']} duplicates."
    )


def cmd_list(args: argparse.Namespace) -> None:
    conn = db.connect()
    try:
        articles = db.list_articles(conn, args.category, args.limit)
    finally:
        conn.close()

    if not articles:
        print("Nothing stored yet — run `python main.py fetch` first.")
        return

    print(build_digest(articles, title="Stored Articles"))


def cmd_digest(args: argparse.Namespace) -> None:
    conn = db.connect()
    try:
        articles = db.recent(conn, hours=args.hours)
    finally:
        conn.close()

    report = build_digest(articles, title="Daily AI News Digest")
    print(report)

    if args.send:
        print("\nSending to Telegram…")
        ok = send_telegram(report)
        print("Sent." if ok else "Not sent.")


def cmd_run(_args: argparse.Namespace) -> None:
    scheduler.run()


def cmd_test_telegram(_args: argparse.Namespace) -> None:
    test_telegram()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI News Fetcher & Summarizer")
    sub = parser.add_subparsers(dest="command", required=True)

    cat_choices = categories()

    p_fetch = sub.add_parser("fetch", help="fetch, summarize, and store articles")
    p_fetch.add_argument("--category", choices=cat_choices, help="limit to one category")
    p_fetch.set_defaults(func=cmd_fetch)

    p_list = sub.add_parser("list", help="show stored articles")
    p_list.add_argument("--category", choices=cat_choices, help="limit to one category")
    p_list.add_argument("--limit", type=int, default=20, help="max rows (default 20)")
    p_list.set_defaults(func=cmd_list)

    p_digest = sub.add_parser("digest", help="build the recent digest")
    p_digest.add_argument("--hours", type=int, default=24, help="look-back window (default 24)")
    p_digest.add_argument("--send", action="store_true", help="also push to Telegram")
    p_digest.set_defaults(func=cmd_digest)

    p_run = sub.add_parser("run", help="start the always-on scheduler")
    p_run.set_defaults(func=cmd_run)

    p_tg = sub.add_parser("test-telegram", help="send a test message to your Telegram")
    p_tg.set_defaults(func=cmd_test_telegram)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
