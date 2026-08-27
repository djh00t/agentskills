from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._client import build_app_client
from scripts._common import (
    DEFAULT_EXPANSIONS,
    DEFAULT_MEDIA_FIELDS,
    DEFAULT_TWEET_FIELDS,
    DEFAULT_USER_FIELDS,
    SkillConfigError,
    ensure_positive,
    fail,
    parse_optional_list,
    to_plain,
)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for filtered stream posts."""
    parser = argparse.ArgumentParser(description="Stream near real-time posts from filtered stream")
    parser.add_argument("--backfill-minutes", type=int)
    parser.add_argument("--start-time", help="RFC3339 timestamp")
    parser.add_argument("--end-time", help="RFC3339 timestamp")
    parser.add_argument("--max-events", type=int, default=0, help="0 means unlimited")
    parser.add_argument("--tweet-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--expansions", action="append", help="comma list, repeatable")
    parser.add_argument("--media-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--user-fields", action="append", help="comma list, repeatable")
    parser.add_argument("--out", help="Write JSONL stream to this path")
    return parser


def _write_line(line: str, file_handle: TextIO | None) -> None:
    """Write one line to stdout and optional file handle."""
    print(line, flush=True)
    if file_handle:
        file_handle.write(line + "\n")
        file_handle.flush()


def main() -> None:
    """Open filtered stream and print each event as JSONL."""
    args = build_parser().parse_args()
    if args.backfill_minutes is not None:
        ensure_positive(args.backfill_minutes, field_name="backfill-minutes")
    if args.max_events < 0:
        fail("max-events must be >= 0")

    out_handle: TextIO | None = None
    try:
        client = build_app_client()
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_handle = out_path.open("w", encoding="utf-8")

        stream = client.stream.posts(
            backfill_minutes=args.backfill_minutes,
            start_time=args.start_time,
            end_time=args.end_time,
            tweet_fields=parse_optional_list(args.tweet_fields, default=DEFAULT_TWEET_FIELDS),
            expansions=parse_optional_list(args.expansions, default=DEFAULT_EXPANSIONS),
            media_fields=parse_optional_list(args.media_fields, default=DEFAULT_MEDIA_FIELDS),
            user_fields=parse_optional_list(args.user_fields, default=DEFAULT_USER_FIELDS),
        )

        count = 0
        for event in stream:
            payload = to_plain(event)
            rendered = json.dumps(payload, separators=(",", ":"), sort_keys=True)
            _write_line(rendered, out_handle)
            count += 1
            if args.max_events and count >= args.max_events:
                break
    except KeyboardInterrupt:
        # Allow controlled shutdown without a stack trace.
        return
    except SkillConfigError as err:
        fail(str(err))
    except Exception as err:  # pragma: no cover - network/API path
        fail("Filtered stream failed", details=str(err), code=1)
    finally:
        if out_handle:
            out_handle.close()


if __name__ == "__main__":
    main()
