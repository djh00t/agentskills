"""Find common leaks in request text; encoded secrets may not be detected."""

import re
import unicodedata


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


def scan_text(text):
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text
                   if unicodedata.category(char) not in {"Cf", "Cn", "Mn", "Me"}
                   and char not in "\u115f\u1160\u3164\uffa0\u2800")
    text = unicodedata.normalize("NFKC", text)
    variants = (text, re.sub(r"[ \t]*\\?(?:\r\n|[\r\n\x85\u2028\u2029])[ \t]*", "", text))
    return [
        name for name, pattern in GENERIC_PATTERNS
        if any(
            any("hook" in match.group().lower() for match in pattern.finditer(value))
            if name == "webhook_url" else pattern.search(value)
            for value in variants
        )
    ]


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
