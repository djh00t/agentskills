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
    emit_json,
    fail,
    parse_csv_option,
    parse_optional_list,
    to_plain,
)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for post lookup by id or ids."""
    parser = argparse.ArgumentParser(description="Retrieve post details by ID or IDs")
    lookup_group = parser.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument("--id", dest="single_id", help="Single post id")
    lookup_group.add_argument("--ids", help="Comma-separated post ids")
    parser.add_argument("--tweet-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--expansions", action="append", help="comma list, repeatable")
    parser.add_argument("--media-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--user-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--out", help="Write JSON output to this path")
    return parser


def main() -> None:
    """Run post lookup and emit one JSON response payload."""
    args = build_parser().parse_args()

    try:
        client = build_app_client()
        common_kwargs = {
            "tweet_fields": parse_optional_list(args.tweet_fields, default=DEFAULT_TWEET_FIELDS),
            "expansions": parse_optional_list(args.expansions, default=DEFAULT_EXPANSIONS),
            "media_fields": parse_optional_list(args.media_fields, default=DEFAULT_MEDIA_FIELDS),
            "user_fields": parse_optional_list(args.user_fields, default=DEFAULT_USER_FIELDS),
        }

        if args.single_id:
            response = client.posts.get_by_id(id=args.single_id, **common_kwargs)
            source = "posts.get_by_id"
            request_ids = [args.single_id]
        else:
            ids = parse_csv_option(args.ids)
            if not ids:
                fail("--ids must contain at least one id")
            response = client.posts.get_by_ids(ids=ids, **common_kwargs)
            source = "posts.get_by_ids"
            request_ids = ids

        emit_json(
            {
                "ok": True,
                "source": source,
                "request_ids": request_ids,
                "response": to_plain(response),
            },
            out_path=args.out,
        )
    except SkillConfigError as err:
        fail(str(err))
    except Exception as err:  # pragma: no cover - network/API path
        fail("Post lookup failed", details=str(err), code=1)


if __name__ == "__main__":
    main()
