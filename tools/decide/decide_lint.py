import re


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
