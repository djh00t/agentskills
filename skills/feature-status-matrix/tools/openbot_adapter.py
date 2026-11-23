"""Offline OpenBot request adapter for the feature-status matrix."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import quote, urlsplit


_DEFAULT_BLOCKER_STATUSES = frozenset({"blocked"})
_TABLE_HEADER = "| Feature | Status | Issue |\n| --- | --- | --- |"


def _parse_blocker_statuses(value: str | None) -> frozenset[str]:
    """Parse comma-separated additions while keeping BLOCKED as a default."""
    if value is None:
        return _DEFAULT_BLOCKER_STATUSES
    if not isinstance(value, str):
        raise ValueError("blocker_statuses must be a comma-separated string")

    configured = value.split(",")
    names = [name.strip().casefold() for name in configured]
    if not names or any(not name for name in names):
        raise ValueError("blocker_statuses must contain non-empty comma-separated names")
    return _DEFAULT_BLOCKER_STATUSES | frozenset(names)


def _required_text(record: Mapping[str, Any], field: str, context: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must contain a non-empty string {field!r}")
    return value


def _records(value: Any, context: str) -> list[Mapping[str, Any]]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
        raise ValueError(f"{context} must be an iterable of mappings")
    records = list(value)
    if any(not isinstance(record, Mapping) for record in records):
        raise ValueError(f"{context} must contain only mappings")
    return records


def _markdown_cell(value: str) -> str:
    """Escape table pipes and flatten line breaks without changing cell text."""
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "<br>")
        .replace("\r", "<br>")
        .replace("\n", "<br>")
        .replace("|", "\\|")
    )


def _heading_text(value: str) -> str:
    return (
        _markdown_cell(value)
        .replace("<br>", " ")
        .replace("#", "\\#")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _issue_link(issue_url: str, context: str) -> str:
    parts = urlsplit(issue_url)
    path_parts = parts.path.lstrip("/").split("/")
    is_github_issue = (
        issue_url == issue_url.strip()
        and not any(char.isspace() for char in issue_url)
        and parts.scheme == "https"
        and parts.netloc.casefold() == "github.com"
        and parts.path.startswith("/")
        and len(path_parts) >= 4
        and bool(path_parts[0])
        and bool(path_parts[1])
        and path_parts[2] == "issues"
        and path_parts[3].isdigit()
        and not parts.username
        and not parts.password
    )
    if not is_github_issue:
        raise ValueError(f"{context} must contain a canonical https://github.com issue URL")
    destination = quote(issue_url, safe=":/?#[]@!$&'()*+,;=%-._~")
    return f"[Issue](<{destination}>)"


def _render_release(
    release_id: str,
    release_title: str,
    items: Any,
    blocker_statuses: frozenset[str],
) -> list[str]:
    lines = [f"## {_heading_text(release_id)} — {_heading_text(release_title)}", "", _TABLE_HEADER]
    for index, item in enumerate(_records(items, f"items for release {release_id!r}"), start=1):
        context = f"item {index} for release {release_id!r}"
        title = _required_text(item, "title", context)
        status = _required_text(item, "status", context)
        issue_url = _required_text(item, "issue_url", context)
        is_blocker = status.strip().casefold() in blocker_statuses
        visible_status = f"⚠️ {status}" if is_blocker else status
        lines.append(
            f"| {_markdown_cell(title)} | {_markdown_cell(visible_status)} | {_issue_link(issue_url, context)} |"
        )
    return lines


def handle_request(
    request: Mapping[str, Any],
    source: Any,
    sink: Any,
    *,
    blocker_statuses: str | None = None,
) -> str:
    """Render one ``full`` or selected ``release`` request and reply once.

    ``source`` supplies ``list_releases()`` and ``list_items(release_id)``;
    ``sink`` supplies ``reply(markdown)``. No live service or harness is used.
    """
    statuses = _parse_blocker_statuses(blocker_statuses)
    if not isinstance(request, Mapping):
        raise ValueError("request must be a mapping")
    mode = request.get("mode")
    if not isinstance(mode, str) or mode not in {"full", "release"}:
        raise ValueError("mode must be 'full' or 'release'")
    selected_release = None
    if mode == "release":
        selected_release = request.get("release")
        if not isinstance(selected_release, str) or not selected_release.strip():
            raise ValueError("release mode requires a non-empty 'release' identifier")
    if not callable(getattr(source, "list_releases", None)):
        raise ValueError("source must provide list_releases()")
    if not callable(getattr(source, "list_items", None)):
        raise ValueError("source must provide list_items(release_id)")
    if not callable(getattr(sink, "reply", None)):
        raise ValueError("sink must provide reply(markdown)")

    releases = _records(source.list_releases(), "releases")
    normalized_releases: list[tuple[str, str, Mapping[str, Any]]] = []
    seen_ids: set[str] = set()
    for index, release in enumerate(releases, start=1):
        context = f"release {index}"
        release_id = _required_text(release, "id", context)
        title = _required_text(release, "title", context)
        if release_id in seen_ids:
            raise ValueError(f"duplicate release identifier {release_id!r}")
        seen_ids.add(release_id)
        normalized_releases.append((release_id, title, release))

    if mode == "release":
        selected = next(
            (entry for entry in normalized_releases if entry[0] == selected_release),
            None,
        )
        if selected is None:
            raise ValueError(f"unknown release identifier {selected_release!r}")
        included_releases = [selected]
    else:
        included_releases = normalized_releases

    sections = ["# Feature Status Matrix"]
    for release_id, title, _release in included_releases:
        section = _render_release(
            release_id,
            title,
            source.list_items(release_id),
            statuses,
        )
        sections.extend(["", *section])
    markdown = "\n".join(sections)
    sink.reply(markdown)
    return markdown
