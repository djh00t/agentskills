from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xdk.stream.models import UpdateRulesRequest

from scripts._client import build_app_client
from scripts._common import (
    SkillConfigError,
    collect_pages,
    emit_json,
    ensure_positive,
    fail,
    parse_csv_option,
    to_plain,
)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for stream rules management."""
    parser = argparse.ArgumentParser(description="Get or update filtered stream rules")
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get", help="List stream rules")
    get_parser.add_argument("--ids", help="comma list of rule ids")
    get_parser.add_argument("--max-results", type=int, default=100)
    get_parser.add_argument("--pages", type=int, default=1)
    get_parser.add_argument("--out", help="Write JSON output to this path")

    update_parser = subparsers.add_parser("update", help="Update stream rules")
    update_parser.add_argument(
        "--add-json",
        help='JSON array of rule objects, e.g. [{"value":"OpenAI lang:en","tag":"openai"}]',
    )
    update_parser.add_argument("--delete-ids", help="comma list of rule ids")
    update_parser.add_argument("--delete-values", help="comma list of rule values")
    update_parser.add_argument("--dry-run", action="store_true")
    update_parser.add_argument("--delete-all", action="store_true")
    update_parser.add_argument("--out", help="Write JSON output to this path")
    return parser


def _parse_add_rules(raw: str | None) -> list[dict[str, Any]] | None:
    """Parse add-rules JSON payload into list form."""
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as err:
        fail("--add-json must be valid JSON", details=str(err))

    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    fail("--add-json must be a JSON object or JSON array of objects")


def _build_update_body(args: argparse.Namespace) -> dict[str, Any]:
    """Build request body payload for stream rule updates."""
    payload: dict[str, Any] = {}
    add_rules = _parse_add_rules(args.add_json)
    if add_rules:
        payload["add"] = add_rules

    delete_ids = parse_csv_option(args.delete_ids)
    delete_values = parse_csv_option(args.delete_values)
    if delete_ids or delete_values:
        delete_payload: dict[str, Any] = {}
        if delete_ids:
            delete_payload["ids"] = delete_ids
        if delete_values:
            delete_payload["values"] = delete_values
        payload["delete"] = delete_payload

    return payload


def handle_get(args: argparse.Namespace) -> None:
    """Handle stream rules listing operation."""
    ensure_positive(args.max_results, field_name="max-results")
    ensure_positive(args.pages, field_name="pages")

    client = build_app_client()
    iterator = client.stream.get_rules(
        ids=parse_csv_option(args.ids),
        max_results=args.max_results,
    )
    pages = collect_pages(iterator, page_limit=args.pages)
    emit_json(
        {
            "ok": True,
            "source": "stream.get_rules",
            "page_count": len(pages),
            "pages": pages,
        },
        out_path=args.out,
    )


def handle_update(args: argparse.Namespace) -> None:
    """Handle stream rules update operation."""
    body_payload = _build_update_body(args)
    if not body_payload and not args.delete_all:
        fail("Provide --add-json and/or delete options, or set --delete-all")

    client = build_app_client()
    body = UpdateRulesRequest(**body_payload)
    response = client.stream.update_rules(
        body=body,
        dry_run=args.dry_run,
        delete_all=args.delete_all,
    )
    emit_json(
        {
            "ok": True,
            "source": "stream.update_rules",
            "request": {
                "body": body_payload,
                "dry_run": args.dry_run,
                "delete_all": args.delete_all,
            },
            "response": to_plain(response),
        },
        out_path=args.out,
    )


def main() -> None:
    """Route stream rule command to handler."""
    args = build_parser().parse_args()
    try:
        if args.command == "get":
            handle_get(args)
            return
        handle_update(args)
    except SkillConfigError as err:
        fail(str(err))
    except Exception as err:  # pragma: no cover - network/API path
        fail("Stream rules operation failed", details=str(err), code=1)


if __name__ == "__main__":
    main()
