from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

DEFAULT_TWEET_FIELDS = [
    "id",
    "text",
    "author_id",
    "created_at",
    "edit_history_tweet_ids",
    "public_metrics",
    "lang",
]
DEFAULT_EXPANSIONS = ["author_id", "referenced_tweets.id", "attachments.media_keys"]
DEFAULT_USER_FIELDS = ["id", "name", "username", "verified"]
DEFAULT_MEDIA_FIELDS = ["media_key", "type", "url", "preview_image_url"]


class SkillConfigError(ValueError):
    """Raised when required environment configuration is missing."""


def parse_csv_option(value: str | None) -> list[str] | None:
    """Split one comma-delimited option value into a clean list."""
    if value is None:
        return None
    parts = [item.strip() for item in value.split(",") if item.strip()]
    return parts or None


def parse_csv_options(values: list[str] | None) -> list[str] | None:
    """Split repeated comma-delimited options into one list."""
    if not values:
        return None
    merged: list[str] = []
    for value in values:
        parts = parse_csv_option(value)
        if parts:
            merged.extend(parts)
    return merged or None


def to_plain(value: Any) -> Any:
    """Convert model objects into JSON-serializable Python values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return to_plain(model_dump(exclude_none=True))

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_plain(to_dict())

    as_dict = getattr(value, "__dict__", None)
    if isinstance(as_dict, dict):
        return {
            str(key): to_plain(item) for key, item in as_dict.items() if not key.startswith("_")
        }

    return str(value)


def collect_pages(iterator: Iterator[Any], page_limit: int) -> list[Any]:
    """Collect up to page_limit pages from an iterator response."""
    pages: list[Any] = []
    for index, page in enumerate(iterator, start=1):
        pages.append(to_plain(page))
        if page_limit > 0 and index >= page_limit:
            break
    return pages


def emit_json(payload: Any, out_path: str | None = None) -> None:
    """Print JSON payload to stdout and optionally write it to a file."""
    rendered = json.dumps(to_plain(payload), indent=2, sort_keys=True)
    print(rendered)
    if out_path:
        Path(out_path).write_text(rendered + "\n", encoding="utf-8")


def fail(message: str, *, details: Any = None, code: int = 2) -> None:
    """Exit process with a structured JSON error payload."""
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = to_plain(details)

    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    raise SystemExit(code)


def parse_optional_list(
    raw_values: list[str] | None, default: list[str] | None = None
) -> list[str] | None:
    """Parse repeated CSV args and return either parsed values or default list."""
    parsed = parse_csv_options(raw_values)
    if parsed is not None:
        return parsed
    return list(default) if default else None


def ensure_positive(value: int, *, field_name: str) -> int:
    """Validate that numeric arguments are positive integers."""
    if value <= 0:
        fail(f"{field_name} must be > 0", code=2)
    return value
