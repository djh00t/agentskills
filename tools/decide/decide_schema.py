"""Validation for decide request objects."""

from datetime import datetime
import re


KINDS = ("simple", "complex", "pr_merge")
PRIORITIES = ("P0", "P1", "P2")
LABELS = ("A", "B", "C", "D")
REVERSIBLE = ("yes", "no", "partly")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_FIELDS = {
    "key", "requester", "kind", "title", "question", "why_owner", "options",
    "rec_reason", "bounds", "links", "pr", "priority", "depends_on",
    "chase_at", "expires_at", "supersedes", "cc", "chat_link", "quote",
}
_OPTION_FIELDS = {"label", "text", "changes", "reversible", "rec", "approves_merge"}
_PR_FIELDS = {"repo", "number", "head_sha", "base", "merger", "merge_method", "merge_order", "trailers"}


def validate_request(obj):
    """Return every schema error found in a request object."""
    errors = []

    def error(path, message):
        errors.append("{}: {}".format(path, message))

    if not isinstance(obj, dict):
        return ["$: must be an object"]

    for key in obj:
        if key not in _FIELDS:
            error(key, "unknown field")

    def string(value, path, minimum=1, maximum=None, strip=False):
        if not isinstance(value, str):
            error(path, "must be a string")
            return False
        checked = value.strip() if strip else value
        if len(checked) < minimum:
            error(path, "must be at least {} character(s)".format(minimum))
        if maximum is not None and len(checked) > maximum:
            error(path, "longer than {} characters".format(maximum))
        return True

    def enum(value, path, choices):
        if value not in choices or not isinstance(value, str):
            error(path, "must be one of {}".format(", ".join(choices)))

    for name, maximum in (("key", 80), ("title", 80), ("question", 300), ("why_owner", 200), ("rec_reason", 150)):
        if name not in obj:
            error(name, "is required")
            continue
        value = obj[name]
        if string(value, name, maximum=maximum, strip=name == "title") and name == "key" and not re.fullmatch(r"[A-Za-z0-9._:-]+", value):
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
                    error(path + "." + key, "unknown field")
            for key in ("label", "text", "changes", "reversible", "rec"):
                if key not in option:
                    error(path + "." + key, "is required")
            if "label" in option:
                expected = LABELS[index] if index < len(LABELS) else None
                if option["label"] != expected:
                    error(path + ".label", "must be {}".format(expected or "a valid label"))
            for key, maximum in (("text", 60), ("changes", 200)):
                if key in option:
                    string(option[key], path + "." + key, maximum=maximum)
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

    for name in ("bounds", "links", "depends_on", "supersedes", "cc", "chase_at", "expires_at"):
        if name not in obj:
            continue
        value = obj[name]
        if name == "bounds":
            if not isinstance(value, dict):
                error(name, "must be an object")
            else:
                for key, item in value.items():
                    path = name + "." + key
                    if key not in {"time", "milestone", "spend"}:
                        error(path, "unknown field")
                    elif not isinstance(item, str):
                        error(path, "must be a string")
                    elif len(item) > 100:
                        error(path, "longer than 100 characters")
        elif name == "links":
            if not isinstance(value, list):
                error(name, "must be a list")
            else:
                if len(value) > 5:
                    error(name, "must contain at most 5 items")
                for i, item in enumerate(value):
                    path = "links[{}]".format(i)
                    if not isinstance(item, str):
                        error(path, "must be a string")
                    else:
                        if not item.startswith("https://"):
                            error(path, "must start with https://")
                        if len(item) > 300:
                            error(path, "longer than 300 characters")
        elif name in ("depends_on", "supersedes"):
            values = value if name == "depends_on" and isinstance(value, list) else [value]
            if name == "depends_on" and not isinstance(value, list):
                error(name, "must be a list")
            seen = set()
            for i, item in enumerate(values):
                path = "{}[{}]".format(name, i) if name == "depends_on" else name
                if type(item) is not int or item < 1:
                    error(path, "must be an integer greater than or equal to 1")
                elif item in seen:
                    error(path, "must be distinct")
                seen.add(item)
        elif name == "cc":
            if not isinstance(value, list):
                error(name, "must be a list")
            else:
                seen = set()
                for i, item in enumerate(value):
                    path = "cc[{}]".format(i)
                    if not isinstance(item, str) or not UUID_RE.fullmatch(item):
                        error(path, "must be a UUID")
                    elif item == obj.get("requester"):
                        error(path, "must not equal requester")
                    elif item in seen:
                        error(path, "must be distinct")
                    seen.add(item)
        else:
            path = name
            if not isinstance(value, str):
                error(path, "must be an ISO 8601 string with an offset")
                continue
            try:
                parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
                if parsed.tzinfo is None:
                    raise ValueError
                obj_value = parsed
                if name == "chase_at":
                    chase = obj_value
                else:
                    expires = obj_value
            except (ValueError, OverflowError):
                error(path, "must be an ISO 8601 string with an offset")
    if "chase" in locals() and "expires" in locals() and chase >= expires:
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
                if not isinstance(value, str):
                    error(name, "must be a string")
                else:
                    if not value.startswith("https://"):
                        error(name, "must start with https://")
                    if len(value) > 300:
                        error(name, "longer than 300 characters")
            else:
                string(value, name, maximum=300)

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
                    error("pr." + key, "unknown field")
            for key in ("repo", "number", "head_sha", "base", "merger", "merge_method"):
                if key not in pr:
                    error("pr." + key, "is required")
            for key, pattern, message in (("repo", r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", "must be an owner/repository"), ("head_sha", r"[0-9a-f]{40}", "must be a 40-character lowercase hex sha")):
                if key in pr and (not isinstance(pr[key], str) or not re.fullmatch(pattern, pr[key])):
                    error("pr." + key, message)
            for key in ("number", "merge_order"):
                if key in pr and (type(pr[key]) is not int or pr[key] < 1):
                    error("pr." + key, "must be an integer greater than or equal to 1")
            if "base" in pr and (not isinstance(pr["base"], str) or not 1 <= len(pr["base"]) <= 100):
                error("pr.base", "must be a string of 1 to 100 characters")
            if "merger" in pr and pr["merger"] not in ("david", "agent"):
                error("pr.merger", "must be david or agent")
            if "merge_method" in pr and pr["merge_method"] not in ("merge", "squash", "rebase"):
                error("pr.merge_method", "must be merge, squash or rebase")
            if "trailers" in pr:
                if not isinstance(pr["trailers"], list):
                    error("pr.trailers", "must be a list")
                else:
                    for i, item in enumerate(pr["trailers"]):
                        if not isinstance(item, str):
                            error("pr.trailers[{}]".format(i), "must be a string")
                        elif len(item) > 100:
                            error("pr.trailers[{}]".format(i), "longer than 100 characters")
    return errors
