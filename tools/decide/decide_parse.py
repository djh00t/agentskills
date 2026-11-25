"""Parse replies in rule order: normalize, question, pair ambiguity, option, approve, custom, ambiguity.

Unicode names depend on Python's Unicode database and can match non-question
symbols, including question marks in URLs. These are treated as questions.
"""

import re
import unicodedata


_INVISIBLE = {"\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u2800", "\u3164", "\uffa0", "\U00016fe4", "\U0001d159", "\ufffc"} | set(map(chr, range(0x180b, 0x1810))) | set(map(chr, range(0xfe00, 0xfe10))) | set(map(chr, range(0xe0100, 0xe01f0)))

_OPTION_WITH_REASON = re.compile(
    r"#?([0-9]{1,9})\s*:\s*([A-Da-d])(?:\s*[,.:;-]\s*(.*))?"
)
_OPTION_TOKEN = re.compile(r"#?([0-9]{1,9})\s+([A-Da-d])")
_APPROVE = re.compile(r"approve\s+#?([0-9]{1,9})", re.I)
_START_ID = re.compile(r"^#?([0-9]{1,9})\b")
_HASH_ID = re.compile(r"#([0-9]{1,9})(?![0-9])")
_DECISION_PAIR = re.compile(r"(?<![0-9])#?[0-9]{1,9}(?:\s*:\s*|\s+)[A-Da-d]\b")


def _find_id(text):
    ids = set()
    start_match = _START_ID.match(text)
    if start_match:
        ids.add(int(start_match.group(1)))
    ids.update(int(match.group(1)) for match in _HASH_ID.finditer(text))
    return next(iter(ids)) if len(ids) == 1 else None


def _result(result, text, item_id=None, choice=None):
    return {"result": result, "id": item_id, "choice": choice, "words": text}


def parse_text(text: str) -> dict:
    """Classify reply text as an option, custom answer, question or ambiguity."""
    if len(text) > 4000:
        return _result("ambiguous", text)
    normalized = unicodedata.normalize("NFKC", text)
    if len(normalized) > 4000:
        return _result("ambiguous", text)
    words = "".join(char for char in text if char not in _INVISIBLE and unicodedata.category(char) != "Cf")
    t = unicodedata.normalize("NFKC", words).strip()
    if any(c.isdecimal() and c not in "0123456789" for c in words):
        return _result("ambiguous", words)
    if any(
        any(word in unicodedata.name(char, "") for word in ("QUESTION", "INTERROBANG"))
        for char in words
    ):
        return _result("question", words, _find_id(t))
    if not words.isprintable():
        return _result("ambiguous", words)
    text = words
    if len(_DECISION_PAIR.findall(t)) > 1:
        return _result("ambiguous", text)

    match = _OPTION_WITH_REASON.fullmatch(t) or _OPTION_TOKEN.fullmatch(t)
    if match:
        option_id = int(match.group(1))
        mentioned_ids = {option_id}
        mentioned_ids.update(int(item.group(1)) for item in _HASH_ID.finditer(t))
        if len(mentioned_ids) > 1:
            return _result("ambiguous", text)
        return _result("option", text, option_id, match.group(2).upper())

    match = _APPROVE.fullmatch(t)
    if match:
        return _result("option", text, int(match.group(1)), "rec")

    item_id = _find_id(t)
    if item_id is not None:
        return _result("custom", text, item_id)
    return _result("ambiguous", text)
