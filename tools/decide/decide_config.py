"""Load and validate the private decide configuration."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from decide_common import DecideError, EXIT_ENV, config_path


# TODO(D01b): Keep this identical to UUID_RE in decide_schema.
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
NAME_RE = re.compile(r"^[a-z0-9_]{1,40}$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
KEYS = {
    "version", "roster_path", "reviewer_login", "verdict_regex", "timezone",
    "check_times", "private_patterns", "mask_rules", "page_title", "page_summary",
}


@dataclass(frozen=True)
class Config:
    reviewer_login: str
    verdict_re: object
    tz: ZoneInfo
    check_times: tuple
    private: list
    masks: list
    roster_ids: frozenset
    roster_names: dict
    page_title: str
    page_summary: str


def _fail(key, detail="is invalid"):
    raise DecideError(EXIT_ENV, "config: {} {}".format(key, detail))


def _string(data, key, low=None, high=None):
    value = data[key]
    if not isinstance(value, str) or (low is not None and not low <= len(value) <= high):
        _fail(key)
    return value


def _roster(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        _fail("roster_path", "cannot be read")
    matches = list(re.finditer(r"^\s*-?\s*id:\s*['\"]?([0-9a-f-]{36})['\"]?\s*$", text, re.M))
    ids = set()
    names = {}
    for match in matches:
        identifier = match.group(1)
        if not UUID_RE.fullmatch(identifier):
            _fail("roster_path", "contains an invalid id")
        ids.add(identifier)
        indent = len(match.group(0)) - len(match.group(0).lstrip())
        for line in text[match.end():].splitlines():
            if not line.strip():
                continue
            next_indent = len(line) - len(line.lstrip())
            if next_indent <= indent:
                break
            name_match = re.match(r"^\s+name:\s*(.*?)\s*$", line)
            if name_match:
                name = name_match.group(1).strip("'\"")
                if name:
                    names[identifier] = name
                break
        names.setdefault(identifier, identifier)
    if not ids:
        _fail("roster_path", "contains no ids")
    return frozenset(ids), names


def load_config(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("file", "cannot be read as JSON")
    if not isinstance(data, dict):
        _fail("object")
    missing = KEYS - data.keys()
    unknown = data.keys() - KEYS
    if missing:
        _fail(sorted(missing)[0], "is required")
    if unknown:
        _fail(sorted(unknown)[0], "is unknown")
    if type(data["version"]) is not int or data["version"] != 1:
        _fail("version")
    roster_value = _string(data, "roster_path")
    if not roster_value or Path(roster_value).is_absolute():
        _fail("roster_path")
    roster_file = path.parent / roster_value
    if not roster_file.is_file():
        _fail("roster_path", "does not exist")
    reviewer = _string(data, "reviewer_login")
    if not LOGIN_RE.fullmatch(reviewer):
        _fail("reviewer_login")
    verdict = _string(data, "verdict_regex")
    try:
        verdict_re = re.compile(verdict)
    except re.error:
        _fail("verdict_regex", "does not compile")
    if verdict_re.groups != 1:
        _fail("verdict_regex", "must have one group")
    timezone = _string(data, "timezone")
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        _fail("timezone")
    times = data["check_times"]
    if not isinstance(times, list) or not 1 <= len(times) <= 6 or any(
        not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value)
        for value in times
    ) or times != sorted(set(times)):
        _fail("check_times")
    private = []
    masks = []
    for key, fields, target in (
        ("private_patterns", {"name", "regex"}, private),
        ("mask_rules", {"name", "regex", "replace"}, masks),
    ):
        values = data[key]
        if not isinstance(values, list):
            _fail(key)
        names = set()
        for value in values:
            if not isinstance(value, dict) or value.keys() != fields:
                _fail(key)
            name = value["name"]
            if not isinstance(name, str) or not NAME_RE.fullmatch(name) or name in names:
                _fail(key, "has an invalid or duplicate name")
            names.add(name)
            regex = value["regex"]
            if not isinstance(regex, str):
                _fail(key, "has an invalid regex")
            try:
                compiled = re.compile(regex)
            except re.error:
                _fail(key, "has an invalid regex")
            if key == "private_patterns":
                target.append((name, compiled))
            else:
                replacement = value["replace"]
                if not isinstance(replacement, str):
                    _fail(key, "has an invalid replacement")
                try:
                    compiled.sub(replacement, "")
                except re.error:
                    _fail(key, "has an invalid replacement")
                target.append((name, compiled, replacement))
    title = _string(data, "page_title", 1, 80)
    summary = _string(data, "page_summary", 1, 400)
    placeholders = re.findall(r"\{([^{}]*)\}", summary)
    if placeholders.count("as_of") != 1 or placeholders.count("waiting") != 1 or len(placeholders) != 2:
        _fail("page_summary")
    roster_ids, roster_names = _roster(roster_file)
    return Config(reviewer, verdict_re, tz, tuple(times), private, masks, roster_ids,
                  roster_names, title, summary)


def config_from_args(args):
    return load_config(config_path(args))
