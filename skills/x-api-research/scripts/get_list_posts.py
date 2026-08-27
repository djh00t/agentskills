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
    """Build argument parser for list timeline retrieval."""
    parser = argparse.ArgumentParser(description="Retrieve posts from a list timeline")
    parser.add_argument("--list-id", required=True)
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--tweet-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--expansions", action="append", help="comma list, repeatable")
    parser.add_argument("--media-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--user-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--out", help="Write JSON output to this path")
    return parser


def main() -> None:
    """Run list timeline retrieval and emit result pages."""
    args = build_parser().parse_args()
    ensure_positive(args.max_results, field_name="max-results")
    ensure_positive(args.pages, field_name="pages")

    try:
        client = build_app_client()
        iterator = client.lists.get_posts(
            id=args.list_id,
            max_results=args.max_results,
            tweet_fields=parse_optional_list(args.tweet_fields, default=DEFAULT_TWEET_FIELDS),
            expansions=parse_optional_list(args.expansions, default=DEFAULT_EXPANSIONS),
            media_fields=parse_optional_list(args.media_fields, default=DEFAULT_MEDIA_FIELDS),
            user_fields=parse_optional_list(args.user_fields, default=DEFAULT_USER_FIELDS),
        )
        pages = collect_pages(iterator, page_limit=args.pages)
        emit_json(
            {
                "ok": True,
                "source": "lists.get_posts",
                "list_id": args.list_id,
                "page_count": len(pages),
                "pages": pages,
            },
            out_path=args.out,
        )
    except SkillConfigError as err:
        fail(str(err))
    except Exception as err:  # pragma: no cover - network/API path
        fail("List timeline retrieval failed", details=str(err), code=1)


if __name__ == "__main__":
    main()
