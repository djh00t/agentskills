"""Fixed-template reply outbox commands."""

import json

from decide_common import DecideError, EXIT_CONFLICT, home_dir
from decide_store import Store


TEMPLATES = {
    "answered": 'decide #{id} answered: {label} ({text}). Words: "{words}"',
    "custom": 'decide #{id} answered (custom). Words: "{words}"',
    "approved": ('decide #{id} approved: {label} ({text}). Words: "{words}". '
                 'Merge it, then run decide confirm-merge {id} --sha <merge sha>.'),
    "rejected": "decide #{id} rejected with no reason.",
    "expired": "decide #{id} expired with no answer. It is not a yes and not a no.",
    "verify_failed": "decide #{id} verify-pr failed: {reasons}.",
    "stale": "decide #{id} is stale: the PR head changed. Re-run verify-pr at the new head.",
    "closed_by": 'decide #{id} closed as {label} by the answer on #{by}. Words: "{words}"',
}


def _mask_text(text, cfg):
    if cfg is None:
        return text
    for _, pattern, replacement in cfg.masks:
        text = pattern.sub(replacement, text)
    return text


def _events_locked(store):
    result, lines = store._verify_locked()
    if not result["ok"]:
        raise DecideError(EXIT_CONFLICT, "cannot read a broken log", result)
    return [json.loads(line) for line in lines]


def _queue(store, item, template, fields, to, priority, cfg=None, prefix=""):
    """Append one reply line. The caller must hold the store lock."""
    values = dict(fields)
    values.setdefault("id", item["id"])
    text = prefix + _mask_text(TEMPLATES[template].format(**values), cfg)
    seq = len(_events_locked(store)) + 1
    oid = "{}-{}".format(item["id"], seq)
    return store.append("outbox", item["id"], {
        "oid": oid, "to": to, "priority": bool(priority), "text": text,
    })


def queue(store, item, template, fields, to, priority, cfg=None):
    """Append one reply line. The caller must hold the store lock."""
    return _queue(store, item, template, fields, to, priority, cfg)


def queue_for_item(store, item, template, fields, cfg=None):
    """Queue the requester reply and FYI lines for all copied recipients."""
    events = []
    request = item["request"]
    requester = request.get("requester")
    if requester is not None:
        events.append(queue(store, item, template, fields, requester,
                            template != "expired", cfg))
    text_fields = dict(fields)
    text_fields.setdefault("id", item["id"])
    for recipient in request.get("cc", []):
        events.append(_queue(store, item, template, text_fields, recipient, False,
                             cfg=cfg, prefix="FYI "))
    return events


def pending(store):
    """Return queued lines that have no later sent marker."""
    events = store.read_events()
    sent = {event["data"].get("oid") for event in events if event["type"] == "outbox_sent"}
    return [event["data"] for event in events
            if event["type"] == "outbox" and event["data"].get("oid") not in sent]


def _mark_sent(store, oid):
    with store.lock():
        events = _events_locked(store)
        matching = next((event for event in events
                         if event["type"] == "outbox" and event["data"].get("oid") == oid), None)
        if matching is None:
            raise DecideError(4, "no outbox line {}".format(oid))
        if any(event["type"] == "outbox_sent" and event["data"].get("oid") == oid
               for event in events):
            raise DecideError(EXIT_CONFLICT, "outbox line already sent")
        return store.append("outbox_sent", matching["id"], {"oid": oid})


def _outbox(args):
    store = Store(home_dir(args))
    if args.mark_sent is not None:
        _mark_sent(store, args.mark_sent)
        return 0
    lines = pending(store)
    if args.json:
        for line in lines:
            print(json.dumps(line, sort_keys=True, ensure_ascii=False))
    else:
        for line in lines:
            marker = " [P]" if line["priority"] else ""
            print("{} -> {}{}: {}".format(line["oid"], line["to"], marker, line["text"]))
    return 0


def register(subparsers):
    command = subparsers.add_parser("outbox")
    command.add_argument("--mark-sent", metavar="OID")
    command.set_defaults(func=_outbox)
