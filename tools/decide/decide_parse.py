"""Parse replies in rule order: normalize, question, decision-pair ambiguity, option, approve, custom, ambiguity."""

import re
import unicodedata


_OPTION_WITH_REASON = re.compile(
    r"#?(\d+)\s*:\s*([A-Da-d])(?:\s*[,.:;-]\s*(.*))?", re.S
)
_OPTION_TOKEN = re.compile(r"#?(\d+)\s+([A-Da-d])")
_APPROVE = re.compile(r"approve\s+#?(\d+)", re.I)
_START_ID = re.compile(r"^#?(\d+)\b")
_HASH_ID = re.compile(r"#(\d+)")
_DECISION_PAIR = re.compile(r"#?\d+\s*[:\s]\s*[A-Da-d]\b")


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
    t = "".join(
        char for char in unicodedata.normalize("NFKC", text)
        if unicodedata.category(char) != "Cf"
    ).strip()
    if t == "":
        return _result("ambiguous", text)
    if any(
        "QUESTION" in unicodedata.name(char, "") or char == "\u203d"
        for char in text
    ):
        return _result("question", text, _find_id(t))
    if len(_DECISION_PAIR.findall(t)) > 1:
        return _result("ambiguous", text)

    match = _OPTION_WITH_REASON.fullmatch(t) or _OPTION_TOKEN.fullmatch(t)
    if match:
        option_id = int(match.group(1))
        mentioned_ids = {option_id}
        mentioned_ids.update(int(item.group(1)) for item in _HASH_ID.finditer(t))
        if len(mentioned_ids) > 1:
            return _result("ambiguous", text)
        return _result("option", text, int(match.group(1)), match.group(2).upper())

    match = _APPROVE.fullmatch(t)
    if match:
        return _result("option", text, int(match.group(1)), "rec")

    item_id = _find_id(t)
    if item_id is not None:
        return _result("custom", text, item_id)
    return _result("ambiguous", text)
