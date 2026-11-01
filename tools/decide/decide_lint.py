"""Find common leaks in request text; encoded secrets may not be detected."""

import re
import unicodedata
from pathlib import Path

from decide_common import DecideError, EXIT_NOT_FOUND, EXIT_OK, EXIT_VALIDATION, emit
from decide_config import config_from_args


GENERIC_PATTERNS = [
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b", re.IGNORECASE)),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b", re.IGNORECASE)),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", re.IGNORECASE)),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----", re.IGNORECASE)),
    (
        "email",
        re.compile(
            r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]++@"
            r"(?!users\.noreply\.github\.com(?![A-Za-z0-9-]|\.[A-Za-z0-9]))"
            r"(?:[A-Za-z0-9-]++\.)+[A-Za-z]{2,}", re.IGNORECASE
        ),
    ),
    ("home_path", re.compile(r"(?:/U[s]ers/[^/\s]+|/h[o]me/[^/\s]+|~/)")),
    ("pushover_key", re.compile(r"(?is)pushover.{0,40}?\b[a-z0-9]{30}\b")),
    ("webhook_url", re.compile(r"https?://[^\s]*+", re.IGNORECASE)),
    ("long_number", re.compile(r"(?<![0-9A-Fa-f])\d{9,}(?![0-9A-Fa-f])")),
]


MAX_TEXT = 65536


def normalize(text):
    if len(text) > MAX_TEXT:
        raise DecideError(EXIT_VALIDATION, "text exceeds the scan limit")
    text = "".join(char for char in text
                   if unicodedata.category(char) not in {"Cf", "Cn", "Mn", "Me"}
                   and char not in "\u115f\u1160\u3164\uffa0\u2800")
    text = unicodedata.normalize("NFKC", text)
    if len(text) > MAX_TEXT:
        raise DecideError(EXIT_VALIDATION, "text exceeds the scan limit")
    return text


def scan_text(text):
    text = normalize(text)
    variants = (text, re.sub(r"[ \t]*\\?(?:\r\n|[\r\n\x85\u2028\u2029])[ \t]*", "", text))
    return [
        name for name, pattern in GENERIC_PATTERNS
        if any(
            any("hook" in match.group().lower() for match in pattern.finditer(value))
            if name == "webhook_url" else pattern.search(value)
            for value in variants
        )
    ]


def scan_private(text, cfg):
    text = normalize(text)
    return [name for name, pattern in cfg.private if pattern.search(text)]


def mask_text(text, cfg):
    text = normalize(text)
    hits = []
    for name, pattern, replacement in cfg.masks:
        if pattern.search(text):
            text = pattern.sub(replacement, text)
            if name not in hits:
                hits.append(name)
    for name, pattern in GENERIC_PATTERNS + list(cfg.private):
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
            result = {}
            for key, item in value.items():
                masked_key = apply(key)
                if masked_key in result:
                    raise DecideError(EXIT_VALIDATION, "masked keys collide")
                result[masked_key] = apply(item)
            return result
        return value
    return apply(obj), hits


def _lint_files(args):
    cfg = config_from_args(args)
    results = []
    output = []
    for filename in args.paths:
        path = Path(filename)
        if path.exists() and not path.is_file():
            raise DecideError(EXIT_NOT_FOUND, "not a regular file: {}".format(filename))
        try:
            lines = path.read_bytes().decode("utf-8", errors="replace").splitlines()
        except OSError:
            raise DecideError(EXIT_NOT_FOUND, "file not found: {}".format(filename))
        for number, line in enumerate(lines, 1):
            line = normalize(line)
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


def iter_text_fields(req, path=""):
    stack = [(req, path, 0)]
    while stack:
        value, current, depth = stack.pop()
        if depth > 256:
            raise ValueError("request nesting exceeds limit")
        if isinstance(value, str):
            yield current, value
        elif isinstance(value, dict):
            children = []
            for index, (key, item) in enumerate(value.items()):
                if not isinstance(key, str):
                    raise TypeError("request keys must be strings")
                key_hits = scan_text(key)
                label = key if not key_hits and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", key) else "[key{}]".format(index)
                child = (current + "." if current else "") + label
                if key_hits:
                    children.append((key, child, depth + 1))
                children.append((item, child, depth + 1))
            stack.extend(reversed(children))
        elif isinstance(value, list):
            stack.extend((item, "{}[{}]".format(current, index), depth + 1)
                         for index, item in reversed(list(enumerate(value))))
        elif value is not None and not isinstance(value, (int, float, bool)):
            raise TypeError("unsupported request value type")



def lint_request(req):
    return [
        (path, pattern_name)
        for path, text in iter_text_fields(req)
        for pattern_name in scan_text(text)
    ]


def format_hits(hits):
    return "; ".join("{}: matches {}".format(path, pattern) for path, pattern in hits)
