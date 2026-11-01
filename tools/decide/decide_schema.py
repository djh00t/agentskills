"""Validation for decide request objects."""

from datetime import datetime
import re
import unicodedata
from urllib.parse import urlsplit


KINDS = ("simple", "complex", "pr_merge")
PRIORITIES = ("P0", "P1", "P2")
LABELS = ("A", "B", "C", "D")
REVERSIBLE = ("yes", "no", "partly")
UUID_RE = re.compile(r"\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
STATES = ("open", "ready", "shown", "on_hold", "approved", "answered", "rejected", "merged", "merge_failed", "expired", "withdrawn", "superseded")
EVENT_TYPES = ("ask", "transition", "chase", "verify", "answer", "closed_by", "outbox", "outbox_sent", "amend", "import", "page_ack", "counter_floor")

_INVISIBLE = {"\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u2800", "\u3164", "\uffa0", "\U00016fe4", "\U0001d159", "\ufffc"} | set(map(chr, range(0x180b, 0x1810))) | set(map(chr, range(0xfe00, 0xfe10))) | set(map(chr, range(0xe0100, 0xe01f0)))

_FIELDS = {
    "key", "requester", "kind", "title", "question", "why_owner", "options",
    "rec_reason", "bounds", "links", "pr", "priority", "depends_on",
    "chase_at", "expires_at", "supersedes", "cc", "chat_link", "quote",
}
_OPTION_FIELDS = {"label", "text", "changes", "reversible", "rec", "approves_merge"}
_PR_FIELDS = {"repo", "number", "head_sha", "base", "merger", "merge_method", "merge_order", "trailers"}


def safe_text(value):
    """Check raw text for invisible, non-printable, or excessive marks."""
    marks = 0
    hebrew_marks = 0
    hebrew_base = False
    visible = False
    previous = ""
    for index, char in enumerate(value):
        category = unicodedata.category(char)
        mark = category in ("Mn", "Me")
        hebrew_point = "\u0591" <= char <= "\u05c7"
        if mark and (not previous or previous.isspace()):
            return False
        if hebrew_point:
            hebrew_marks += 1
            if not hebrew_base or hebrew_marks > 4:
                return False
        elif mark:
            marks += 1
            if marks > 2:
                return False
        else:
            marks = 0
            hebrew_marks = 0
            hebrew_base = category.startswith("L") and ("\u05d0" <= char <= "\u05ea" or "\ufb1d" <= char <= "\ufb4f")
        emoji_variation = char == "\ufe0f" and previous and unicodedata.category(previous) == "So"
        emoji_joiner = (char == "\u200d" and previous and index + 1 < len(value)
                        and (unicodedata.category(previous) == "So" or previous == "\ufe0f")
                        and unicodedata.category(value[index + 1]) == "So")
        if (char in _INVISIBLE and not emoji_variation) or (not char.isprintable() and not char.isspace() and not emoji_joiner):
            return False
        if category in ("Cc", "Zl", "Zp"):
            return False
        visible |= category[0] in "LNPS"
        previous = char
    return not value.strip() or visible



def validate_request(obj):
    """Return every schema error found in a request object."""
    errors = []

    def error(path, message):
        errors.append("{}: {}".format(path, message))

    if not isinstance(obj, dict):
        return ["$: must be an object"]

    for key in obj:
        if key not in _FIELDS:
            error("<unknown field>", "unknown field")

    def string(value, path, minimum=1, maximum=None, strip=False):
        if not isinstance(value, str):
            error(path, "must be a string")
            return False
        checked = unicodedata.normalize("NFKC", value)
        if not safe_text(value):
            error(path, "contains non-printable or invisible characters")
        if strip:
            checked = checked.strip()
        if len(checked) < minimum:
            error(path, "must be at least {} character(s)".format(minimum))
        if maximum is not None and (len(value) > maximum or len(checked) > maximum):
            error(path, "longer than {} characters".format(maximum))
        return True

    def enum(value, path, choices):
        if not isinstance(value, str) or value not in choices:
            error(path, "must be one of {}".format(", ".join(choices)))

    for name, maximum in (("key", 80), ("title", 80), ("question", 300), ("why_owner", 200), ("rec_reason", 150)):
        if name not in obj:
            error(name, "is required")
            continue
        value = obj[name]
        if string(value, name, maximum=maximum, strip=name != "key") and name == "key" and not re.fullmatch(r"[A-Za-z0-9._:-]+", value):
            error(name, "contains invalid characters")

    if "requester" not in obj:
        error("requester", "is required")
    elif not isinstance(obj["requester"], str) or not UUID_RE.fullmatch(obj["requester"]):
        error("requester", "must be a UUID")

    kind = obj.get("kind")
    if "kind" not in obj:
        error("kind", "is required")
    else:
        enum(kind, "kind", KINDS)
    if "priority" not in obj:
        error("priority", "is required")
    else:
        enum(obj["priority"], "priority", PRIORITIES)

    options = obj.get("options")
    if "options" not in obj:
        error("options", "is required")
    elif not isinstance(options, list):
        error("options", "must be a list")
    else:
        if not 2 <= len(options) <= 4:
            error("options", "must contain 2 to 4 items")
        rec_count = 0
        approve_count = 0
        for index, option in enumerate(options):
            path = "options[{}]".format(index)
            if not isinstance(option, dict):
                error(path, "must be an object")
                continue
            for key in option:
                if key not in _OPTION_FIELDS:
                    error(path + ".<unknown field>", "unknown field")
            for key in ("label", "text", "changes", "reversible", "rec"):
                if key not in option:
                    error(path + "." + key, "is required")
            if "label" in option:
                expected = LABELS[index] if index < len(LABELS) else None
                if option["label"] != expected:
                    error(path + ".label", "must be {}".format(expected or "a valid label"))
            for key, maximum in (("text", 60), ("changes", 200)):
                if key in option:
                    string(option[key], path + "." + key, maximum=maximum, strip=True)
            if "reversible" in option:
                enum(option["reversible"], path + ".reversible", REVERSIBLE)
            if "rec" in option:
                if type(option["rec"]) is not bool:
                    error(path + ".rec", "must be a boolean")
                elif option["rec"]:
                    rec_count += 1
            if "approves_merge" in option:
                if type(option["approves_merge"]) is not bool:
                    error(path + ".approves_merge", "must be a boolean")
                elif option["approves_merge"]:
                    approve_count += 1
                if kind != "pr_merge":
                    error(path + ".approves_merge", "only allowed for pr_merge")
        if rec_count != 1:
            error("options", "must have exactly one recommended option")
        if kind == "pr_merge" and approve_count != 1:
            error("options", "must have exactly one approves_merge option")

    chase = expires = None

    def link(value, path):
        if not isinstance(value, str):
            error(path, "must be a string")
            return
        try:
            parts = urlsplit(value)
            host = parts.hostname or ""
            valid = (value.isascii() and parts.scheme == "https"
                     and bool(re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", host))
                     and "@" not in parts.netloc
                     and not any(c in value for c in "\\\"'`"))
            parts.port
        except ValueError:
            valid = False
        if not valid or not value.isprintable() or any(c.isspace() or c in "<>[]" for c in value):
            error(path, "must be a valid https URL")
        if len(value) > 300:
            error(path, "longer than 300 characters")

    for name in ("bounds", "links", "depends_on", "supersedes", "cc", "chase_at", "expires_at"):
        if name not in obj:
            continue
        value = obj[name]
        if name == "bounds":
            if not isinstance(value, dict):
                error(name, "must be an object")
            else:
                for key, item in value.items():
                    path = name + "." + key if key in {"time", "milestone", "spend"} else name + ".<unknown field>"
                    if key not in {"time", "milestone", "spend"}:
                        error(path, "unknown field")
                    else:
                        string(item, path, minimum=0, maximum=100)
        elif name == "links":
            if not isinstance(value, list):
                error(name, "must be a list")
            else:
                if len(value) > 5:
                    error(name, "must contain at most 5 items")
                for i, item in enumerate(value):
                    path = "links[{}]".format(i)
                    link(item, path)
        elif name in ("depends_on", "supersedes"):
            values = value if name == "depends_on" and isinstance(value, list) else [value]
            if name == "depends_on" and not isinstance(value, list):
                error(name, "must be a list")
            if name == "depends_on" and isinstance(value, list) and len(value) > 20:
                error(name, "must contain at most 20 items")
            seen = set()
            for i, item in enumerate(values):
                path = "{}[{}]".format(name, i) if name == "depends_on" else name
                if type(item) is not int or item < 1:
                    error(path, "must be an integer greater than or equal to 1")
                elif item in seen:
                    error(path, "must be distinct")
                if type(item) is int:
                    seen.add(item)
        elif name == "cc":
            if not isinstance(value, list):
                error(name, "must be a list")
            else:
                if len(value) > 20:
                    error(name, "must contain at most 20 items")
                seen = set()
                for i, item in enumerate(value):
                    path = "cc[{}]".format(i)
                    if not isinstance(item, str) or not UUID_RE.fullmatch(item):
                        error(path, "must be a UUID")
                    elif item == obj.get("requester"):
                        error(path, "must not equal requester")
                    elif item in seen:
                        error(path, "must be distinct")
                    if isinstance(item, str):
                        seen.add(item)
        else:
            path = name
            if not isinstance(value, str):
                error(path, "must be an ISO 8601 string with an offset")
                continue
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    raise ValueError
                obj_value = parsed
                if name == "chase_at":
                    chase = obj_value
                else:
                    expires = obj_value
            except (ValueError, OverflowError):
                error(path, "must be an ISO 8601 string with an offset")
    if chase is not None and expires is not None and chase >= expires:
        error("chase_at", "must be before expires_at")

    for name, required_kind in (("chat_link", "complex"), ("quote", "complex")):
        required = kind == required_kind
        if required and name not in obj:
            error(name, "is required for complex")
        elif not required and name in obj:
            error(name, "only allowed for complex")
        elif name in obj:
            value = obj[name]
            if name == "chat_link":
                link(value, name)
            else:
                string(value, name, maximum=300, strip=True)

    pr = obj.get("pr")
    if kind == "pr_merge" and "pr" not in obj:
        error("pr", "is required for pr_merge")
    elif kind != "pr_merge" and "pr" in obj:
        error("pr", "only allowed for pr_merge")
    elif "pr" in obj:
        if not isinstance(pr, dict):
            error("pr", "must be an object")
        else:
            for key in pr:
                if key not in _PR_FIELDS:
                    error("pr.<unknown field>", "unknown field")
            for key in ("repo", "number", "head_sha", "base", "merger", "merge_method"):
                if key not in pr:
                    error("pr." + key, "is required")
            for key, pattern, message in (("repo", r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/(?!\.{1,2}\Z)[A-Za-z0-9._-]+", "must be an owner/repository"), ("head_sha", r"[0-9a-f]{40}", "must be a 40-character lowercase hex sha")):
                if key in pr and (not isinstance(pr[key], str) or not re.fullmatch(pattern, pr[key])):
                    error("pr." + key, message)
            for key in ("number", "merge_order"):
                if key in pr and (type(pr[key]) is not int or pr[key] < 1):
                    error("pr." + key, "must be an integer greater than or equal to 1")
            if "base" in pr:
                base = pr["base"]
                if (not isinstance(base, str) or not 1 <= len(base) <= 100
                        or base.startswith("-") or ".." in base
                        or base.endswith(".")
                        or not re.fullmatch(r"[A-Za-z0-9._/-]+", base)
                        or base == "HEAD" or base.endswith("_HEAD") or base.startswith("refs/")
                        or any(not part or part.startswith(".") or part.endswith(".lock") for part in base.split("/"))
                        ):
                    error("pr.base", "must be a valid git ref")
            if "merger" in pr and pr["merger"] not in ("owner", "agent"):
                error("pr.merger", "must be owner or agent")
            if "merge_method" in pr and pr["merge_method"] not in ("merge", "squash", "rebase"):
                error("pr.merge_method", "must be merge, squash or rebase")
            if "trailers" in pr:
                if not isinstance(pr["trailers"], list):
                    error("pr.trailers", "must be a list")
                else:
                    if len(pr["trailers"]) > 20:
                        error("pr.trailers", "must contain at most 20 items")
                    for i, item in enumerate(pr["trailers"]):
                        if not isinstance(item, str):
                            error("pr.trailers[{}]".format(i), "must be a string")
                        else:
                            if len(item) > 100 or len(unicodedata.normalize("NFKC", item)) > 100:
                                error("pr.trailers[{}]".format(i), "longer than 100 characters")
                            if (not safe_text(item.partition(": ")[2])
                                    or not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*: \S[^\r\n]*", item)):
                                error("pr.trailers[{}]".format(i), "must be a single trailer line")
    return errors


def _safe_text(value, maximum=None):
    if not isinstance(value, str):
        return False
    if maximum is not None and len(value) > maximum:
        return False
    normalized = unicodedata.normalize("NFKC", value)
    return bool(normalized.strip()) and (maximum is None or len(normalized) <= maximum) and safe_text(value) and safe_text(normalized)


def validate_event(ev):
    """Return every schema error found in an event envelope."""
    errors = []
    fields = {"seq", "ts", "type", "id", "data", "prev_sha256"}
    if not isinstance(ev, dict):
        return ["$: must be an object"]
    for key in ev:
        if key not in fields:
            errors.append("$: unknown field")
    for key in fields - set(ev):
        errors.append("{}: is required".format(key))
    if "seq" in ev and (type(ev["seq"]) is not int or ev["seq"] < 1):
        errors.append("seq: must be an integer greater than or equal to 1")
    if "ts" in ev:
        try:
            if not isinstance(ev["ts"], str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", ev["ts"]):
                raise ValueError
            datetime.strptime(ev["ts"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            errors.append("ts: must be a UTC timestamp ending in Z")
    if "type" in ev and (not isinstance(ev["type"], str) or ev["type"] not in EVENT_TYPES):
        errors.append("type: must be a known event type")
    if "id" in ev and not (ev["id"] is None and ev.get("type") in ("page_ack", "counter_floor")) and (type(ev["id"]) is not int or ev["id"] < 1):
        errors.append("id: must be a positive integer or null for page_ack/counter_floor")
    if "data" in ev and not isinstance(ev["data"], dict):
        errors.append("data: must be an object")
    if "prev_sha256" in ev and (not isinstance(ev["prev_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", ev["prev_sha256"])):
        errors.append("prev_sha256: must be 64 lowercase hex characters")
    return errors


def validate_answer(data):
    """Return every schema error found in an answer payload."""
    errors = []
    fields = {"choice", "label", "words", "via", "msg_ref", "mapped_by", "closes", "recorded_by"}
    if not isinstance(data, dict):
        return ["$: must be an object"]
    for key in data:
        if key not in fields:
            errors.append("$: unknown field")
    for key in fields - set(data):
        errors.append("{}: is required".format(key))
    choice = data.get("choice")
    if "choice" in data and (not isinstance(choice, str) or choice not in LABELS + ("custom",)):
        errors.append("choice: must be a label or custom")
    if "label" in data and ((choice == "custom" and data["label"] is not None) or (choice != "custom" and (not isinstance(data["label"], str) or data["label"] not in LABELS))):
        errors.append("label: must be a label or null for custom")
    if isinstance(choice, str) and choice in LABELS and data.get("label") != choice:
        errors.append("label: must match choice")
    if "words" in data and (not _safe_text(data["words"], 4000)):
        errors.append("words: must contain 1 to 4000 non-blank characters")
    if "via" in data and data["via"] not in ("card", "chat"):
        errors.append("via: must be card or chat")
    if "msg_ref" in data and (not _safe_text(data["msg_ref"], 200)):
        errors.append("msg_ref: must contain 1 to 200 characters")
    if "mapped_by" in data and data["mapped_by"] not in ("token", "judgement"):
        errors.append("mapped_by: must be token or judgement")
    if data.get("mapped_by") == "judgement" and choice == "custom":
        errors.append("mapped_by: judgement cannot map custom")
    closes = data.get("closes")
    if "closes" in data:
        if not isinstance(closes, list):
            errors.append("closes: must be a list")
        else:
            seen = set()
            for i, item in enumerate(closes):
                path = "closes[{}]".format(i)
                if not isinstance(item, dict):
                    errors.append("{}: must be an object".format(path))
                    continue
                if set(item) != {"id", "choice"}:
                    errors.append("{}: must contain only id and choice".format(path))
                if type(item.get("id")) is not int or item["id"] < 1:
                    errors.append("{}.id: must be a positive integer".format(path))
                elif item["id"] in seen:
                    errors.append("{}.id: must be distinct".format(path))
                else:
                    seen.add(item["id"])
                if item.get("choice") not in LABELS:
                    errors.append("{}.choice: must be a label".format(path))
    if "recorded_by" in data and data["recorded_by"] != "record":
        errors.append("recorded_by: must be record")
    return errors


def validate_legacy(rec):
    """Return every schema error found in an imported legacy record."""
    errors = []
    if not isinstance(rec, dict):
        return ["$: must be an object"]
    if "id" not in rec:
        errors.append("id: is required")
    elif type(rec["id"]) is not int or rec["id"] < 1:
        errors.append("id: must be an integer greater than or equal to 1")
    if "kind" not in rec:
        errors.append("kind: is required")
    elif rec["kind"] not in KINDS:
        errors.append("kind: must be a known kind")
    if "title" not in rec:
        errors.append("title: is required")
    elif not _safe_text(rec["title"], 80):
        errors.append("title: must be a non-empty string")
    if "state" not in rec:
        errors.append("state: is required")
    elif rec["state"] not in STATES:
        errors.append("state: must be a known state")
    if rec.get("requester") is not None and (not isinstance(rec["requester"], str) or not UUID_RE.fullmatch(rec["requester"])):
        errors.append("requester: must be a UUID")
    pr = rec.get("pr")
    if pr is not None and not isinstance(pr, dict):
        errors.append("pr: must be an object")
    elif isinstance(pr, dict) and "head_sha" in pr and (not isinstance(pr["head_sha"], str) or not re.fullmatch(r"[0-9a-f]{7,40}", pr["head_sha"])):
        errors.append("pr.head_sha: must be 7 to 40 lowercase hex characters")
    return errors
