from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._client import build_app_client
from scripts._common import (
    SkillConfigError,
    emit_json,
    ensure_positive,
    fail,
    parse_optional_list,
    to_plain,
)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for news search and lookup."""
    parser = argparse.ArgumentParser(description="Lookup news/headlines from X news API")
    lookup_group = parser.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument("--query", help="News search query")
    lookup_group.add_argument("--news-id", help="Lookup news item by id")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--max-age-hours", type=int)
    parser.add_argument("--news-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--out", help="Write JSON output to this path")
    return parser


def main() -> None:
    """Run news query or lookup and emit one JSON response payload."""
    args = build_parser().parse_args()
    if args.query:
        ensure_positive(args.max_results, field_name="max-results")

    try:
        client = build_app_client()
        news_fields = parse_optional_list(args.news_fields)
        if args.query:
            response = client.news.search(
                query=args.query,
                max_results=args.max_results,
                max_age_hours=args.max_age_hours,
                news_fields=news_fields,
            )
            source = "news.search"
        else:
            response = client.news.get(id=args.news_id, news_fields=news_fields)
            source = "news.get"

        emit_json(
            {
                "ok": True,
                "source": source,
                "response": to_plain(response),
            },
            out_path=args.out,
        )
    except SkillConfigError as err:
        fail(str(err))
    except Exception as err:  # pragma: no cover - network/API path
        fail("News lookup failed", details=str(err), code=1)


if __name__ == "__main__":
    main()
