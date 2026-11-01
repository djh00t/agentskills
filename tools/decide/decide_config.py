"""Load and validate the private decide configuration."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from decide_common import DecideError, EXIT_ENV, UUID_RE, config_path


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
    private: tuple
    masks: tuple
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


def _roster(text):
    ids = set()
    names = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^(\s*)-?\s*id\s*:\s*(.*?)\s*(?:\s+#.*)?$", line, re.IGNORECASE)
        if match:
            raw = match.group(2).strip().strip("'\"")
            if not UUID_RE.fullmatch(raw):
                _fail("roster_path", "contains an invalid id")
            current = raw.lower()
            if current in ids:
                _fail("roster_path", "contains duplicate ids")
            ids.add(current)
            names[current] = current
            indent = len(match.group(1))
        elif re.search(r"\bid[\'\"]?\s*:", line, re.IGNORECASE):
            _fail("roster_path", "contains an unsupported id entry")
        elif current is not None:
            name_match = re.match(r"^(\s+)name:\s*(.*?)\s*$", line)
            if name_match and len(name_match.group(1)) > indent:
                name = name_match.group(2).strip("'\"")
                if name:
                    names[current] = name
            elif line.strip() and len(line) - len(line.lstrip()) <= indent:
                current = None
    if not ids:
        _fail("roster_path", "contains no ids")
    return frozenset(ids), names


def _secure_file(path, key):
    try:
        if path.is_symlink():
            _fail(key, "has unsafe ownership or permissions")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                _fail(key, "has unsafe ownership or permissions")
            return stream.read()
    except (OSError, UnicodeError):
        _fail(key, "cannot be read")


def load_config(path):
    path = Path(path)
    text = _secure_file(path, "file")
    try:
        data = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("file", "cannot be read as JSON")
    if not isinstance(data, dict):
        _fail("object")
    missing = KEYS - data.keys()
    unknown = data.keys() - KEYS
    if missing or unknown:
        _fail("keys", "; ".join(filter(None, (
            "required: " + ", ".join(sorted(missing)) if missing else "",
            "unknown: " + ", ".join(sorted(unknown)) if unknown else "",
        ))))
    if type(data["version"]) is not int or data["version"] != 1:
        _fail("version")
    roster_value = _string(data, "roster_path")
    if not roster_value or Path(roster_value).is_absolute() or ".." in Path(roster_value).parts:
        _fail("roster_path")
    roster_file = path.parent / roster_value
    if not roster_file.resolve().is_relative_to(path.parent.resolve()) or any(
        (path.parent / Path(*Path(roster_value).parts[:i])).is_symlink()
        for i in range(1, len(Path(roster_value).parts) + 1)
    ):
        _fail("roster_path")
    roster_text = _secure_file(roster_file, "roster_path")
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
            if compiled.search(""):
                _fail(key, "has an empty matching regex")
            if key == "private_patterns":
                target.append((name, compiled))
            else:
                replacement = value["replace"]
                if not isinstance(replacement, str):
                    _fail(key, "has an invalid replacement")
                if re.search(r"\\g<0>", replacement):
                    _fail(key, "has an invalid replacement")
                try:
                    compiled.sub(replacement, "")
                except re.error:
                    _fail(key, "has an invalid replacement")
                target.append((name, compiled, replacement))
    title = _string(data, "page_title", 1, 80)
    summary = _string(data, "page_summary", 0, 400)
    placeholders = re.findall(r"\{([^{}]*)\}", summary)
    if placeholders.count("as_of") != 1 or placeholders.count("waiting") != 1 or len(placeholders) != 2:
        _fail("page_summary")
    roster_ids, roster_names = _roster(roster_text)
    return Config(reviewer, verdict_re, tz, tuple(times), tuple(private), tuple(masks), roster_ids,
                  roster_names, title, summary)


def config_from_args(args):
    return load_config(config_path(args))
