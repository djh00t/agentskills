import re
import argparse
from pathlib import Path

from decide_common import DecideError, EXIT_NOT_FOUND, EXIT_OK, EXIT_VALIDATION, emit


GENERIC_PATTERNS = [
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "email",
        re.compile(
            r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        ),
    ),
    ("home_path", re.compile(r"(?:/U[s]ers/[^/\s]+|/h[o]me/[^/\s]+|~/)")),
    ("pushover_key", re.compile(r"(?is)pushover.{0,40}?\b[a-z0-9]{30}\b")),
    ("webhook_url", re.compile(r"https?://[^\s]*(?:hooks?|webhook)[^\s]*", re.IGNORECASE)),
    ("long_number", re.compile(r"(?<![0-9A-Fa-f])\d{9,}(?![0-9A-Fa-f])")),
]

TEXT_FIELDS = (
    "key",
    "title",
    "question",
    "why_owner",
    "rec_reason",
    "chat_link",
    "quote",
    "bounds.time",
    "bounds.milestone",
    "bounds.spend",
    "links[]",
    "options[].text",
    "options[].changes",
    "pr.trailers[]",
)


def scan_text(text):
    if not text:
        return []
    return [name for name, pattern in GENERIC_PATTERNS if pattern.search(text)]


def scan_private(text, cfg):
    return [name for name, pattern in cfg.private if pattern.search(text)]


def mask_text(text, cfg):
    hits = []
    for name, pattern, replacement in cfg.masks:
        if pattern.search(text):
            text = pattern.sub(replacement, text)
            if name not in hits:
                hits.append(name)
    for name, pattern in GENERIC_PATTERNS + cfg.private:
        if pattern.search(text):
            text = pattern.sub("[masked:{}]".format(name), text)
            if name not in hits:
                hits.append(name)
    return text, hits


def mask_obj(obj, cfg):
    hits = []
    def apply(value):
        if isinstance(value, str):
            masked, found = mask_text(value, cfg)
            for name in found:
                if name not in hits:
                    hits.append(name)
            return masked
        if isinstance(value, list):
            return [apply(item) for item in value]
        if isinstance(value, dict):
            return {key: apply(item) for key, item in value.items()}
        return value
    return apply(obj), hits


def _lint_files(args):
    from decide_config import config_from_args

    cfg = config_from_args(args)
    results = []
    output = []
    for filename in args.paths:
        path = Path(filename)
        try:
            lines = path.read_bytes().decode("utf-8", errors="replace").splitlines()
        except OSError:
            raise DecideError(EXIT_NOT_FOUND, "file not found: {}".format(filename))
        for number, line in enumerate(lines, 1):
            for name in scan_text(line) + scan_private(line, cfg):
                results.append({"path": filename, "line": number, "pattern": name})
                output.append("{}:{}: {}".format(filename, number, name))
            for name, pattern, _replacement in cfg.masks:
                if pattern.search(line):
                    results.append({"path": filename, "line": number, "pattern": "mask:" + name})
                    output.append("{}:{}: mask:{}".format(filename, number, name))
    emit(args, results, "\n".join(output))
    return EXIT_VALIDATION if results else EXIT_OK


def register(subparsers):
    parser = subparsers.add_parser("lint-files")
    parser.add_argument("paths", nargs="+", metavar="PATH")
    parser.set_defaults(func=_lint_files)


def iter_text_fields(req):
    if not isinstance(req, dict):
        return

    for field in TEXT_FIELDS[:7]:
        value = req.get(field)
        if isinstance(value, str):
            yield field, value

    bounds = req.get("bounds")
    if isinstance(bounds, dict):
        for field in ("time", "milestone", "spend"):
            value = bounds.get(field)
            if isinstance(value, str):
                yield "bounds." + field, value

    links = req.get("links")
    if isinstance(links, list):
        for index, value in enumerate(links):
            if isinstance(value, str):
                yield "links[{}]".format(index), value

    options = req.get("options")
    if isinstance(options, list):
        for index, option in enumerate(options):
            if isinstance(option, dict):
                for field in ("text", "changes"):
                    value = option.get(field)
                    if isinstance(value, str):
                        yield "options[{}].{}".format(index, field), value

    pr = req.get("pr")
    if isinstance(pr, dict) and isinstance(pr.get("trailers"), list):
        for index, value in enumerate(pr["trailers"]):
            if isinstance(value, str):
                yield "pr.trailers[{}]".format(index), value


def lint_request(req):
    return [
        (path, pattern_name)
        for path, text in iter_text_fields(req)
        for pattern_name in scan_text(text)
    ]


def format_hits(hits):
    return "; ".join("{}: matches {}".format(path, pattern) for path, pattern in hits)
