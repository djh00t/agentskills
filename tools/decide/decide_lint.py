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
            r"(?!users\.noreply\.github\.com(?![A-Za-z0-9.-]))"
            r"(?:[A-Za-z0-9-]++\.)++[A-Za-z]{2,}", re.IGNORECASE
        ),
    ),
    ("home_path", re.compile(r"(?:/U[s]ers/[^/\s]+|/h[o]me/[^/\s]+|~/)")),
    ("pushover_key", re.compile(r"(?is)pushover.{0,40}?\b[a-z0-9]{30}\b")),
    ("webhook_url", re.compile(r"https?://[^\s]*+", re.IGNORECASE)),
    ("long_number", re.compile(r"(?<![0-9A-Fa-f])\d{9,}(?![0-9A-Fa-f])")),
]


def scan_text(text):
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    variants = (text, re.sub(r"\r?\n[ \t]*", "", text))
    return [
        name for name, pattern in GENERIC_PATTERNS
        if any(
            any("hook" in match.group().lower() for match in pattern.finditer(value))
            if name == "webhook_url" else pattern.search(value)
            for value in variants
        )
    ]


def iter_text_fields(req, path=""):
    if isinstance(req, str):
        yield path, req
    elif isinstance(req, dict):
        for index, (key, value) in enumerate(req.items()):
            # Keys are untrusted too; never place a matched value in a report path.
            label = str(key)
            key_hits = scan_text(label)
            child = (path + "." if path else "") + ("[key{}]".format(index) if key_hits else label)
            if key_hits:
                yield child, label
            yield from iter_text_fields(value, child)
    elif isinstance(req, list):
        for index, value in enumerate(req):
            yield from iter_text_fields(value, "{}[{}]".format(path, index))


def lint_request(req):
    return [
        (path, pattern_name)
        for path, text in iter_text_fields(req)
        for pattern_name in scan_text(text)
    ]


def format_hits(hits):
    return "; ".join("{}: matches {}".format(path, pattern) for path, pattern in hits)
