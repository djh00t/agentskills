from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._client import build_app_client
from scripts._common import (
    DEFAULT_EXPANSIONS,
    DEFAULT_MEDIA_FIELDS,
    DEFAULT_TWEET_FIELDS,
    DEFAULT_USER_FIELDS,
    SkillConfigError,
    collect_pages,
    emit_json,
    ensure_positive,
    fail,
    parse_optional_list,
)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for post search operations."""
    parser = argparse.ArgumentParser(description="Search X posts by topic query")
    parser.add_argument("--query", required=True, help="X search query")
    parser.add_argument("--scope", choices=["recent", "all"], default="recent")
    parser.add_argument("--start-time", help="RFC3339 timestamp")
    parser.add_argument("--end-time", help="RFC3339 timestamp")
    parser.add_argument("--since-id")
    parser.add_argument("--until-id")
    parser.add_argument("--sort-order", choices=["recency", "relevancy"])
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--tweet-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--expansions", action="append", help="comma list, repeatable")
    parser.add_argument("--media-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--user-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--out", help="Write JSON output to this path")
    return parser


def main() -> None:
    """Run post search and emit collected pages as JSON."""
    args = build_parser().parse_args()
    ensure_positive(args.max_results, field_name="max-results")
    ensure_positive(args.pages, field_name="pages")

    try:
        client = build_app_client()
        tweet_fields = parse_optional_list(args.tweet_fields, default=DEFAULT_TWEET_FIELDS)
        expansions = parse_optional_list(args.expansions, default=DEFAULT_EXPANSIONS)
        media_fields = parse_optional_list(args.media_fields, default=DEFAULT_MEDIA_FIELDS)
        user_fields = parse_optional_list(args.user_fields, default=DEFAULT_USER_FIELDS)

        search_kwargs = {
            "query": args.query,
            "start_time": args.start_time,
            "end_time": args.end_time,
            "since_id": args.since_id,
            "until_id": args.until_id,
            "max_results": args.max_results,
            "sort_order": args.sort_order,
            "tweet_fields": tweet_fields,
            "expansions": expansions,
            "media_fields": media_fields,
            "user_fields": user_fields,
        }
        if args.scope == "recent":
            iterator = client.posts.search_recent(**search_kwargs)
        else:
            iterator = client.posts.search_all(**search_kwargs)

        pages = collect_pages(iterator, page_limit=args.pages)
        emit_json(
            {
                "ok": True,
                "source": "posts.search_recent" if args.scope == "recent" else "posts.search_all",
                "query": args.query,
                "scope": args.scope,
                "page_count": len(pages),
                "pages": pages,
            },
            out_path=args.out,
        )
    except SkillConfigError as err:
        fail(str(err))
    except Exception as err:  # pragma: no cover - network/API path
        fail("X post search failed", details=str(err), code=1)


if __name__ == "__main__":
    main()
