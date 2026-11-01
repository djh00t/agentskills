"""Item state transitions, event folding and read commands."""

import argparse

from decide_common import DecideError, emit, home_dir, parse_item_id
from decide_store import Store


TRANSITIONS = {
    "simple": {
        "ready": {"shown", "on_hold", "withdrawn", "superseded", "expired", "answered", "rejected"},
        "shown": {"answered", "rejected", "on_hold", "withdrawn", "superseded", "expired"},
        "on_hold": {"ready", "withdrawn", "superseded", "expired"},
    },
    "complex": {
        "ready": {"shown", "on_hold", "withdrawn", "superseded", "expired", "answered", "rejected"},
        "shown": {"answered", "rejected", "on_hold", "withdrawn", "superseded", "expired"},
        "on_hold": {"ready", "withdrawn", "superseded", "expired"},
    },
    "pr_merge": {
        "open": {"ready", "on_hold", "withdrawn", "superseded", "expired"},
        "ready": {"open", "shown", "on_hold", "withdrawn", "superseded", "expired", "approved", "answered", "rejected"},
        "shown": {"open", "approved", "answered", "rejected", "on_hold", "withdrawn", "superseded", "expired"},
        "on_hold": {"open", "withdrawn", "superseded", "expired"},
        "approved": {"merged", "merge_failed"},
    },
}
CLOSED = {"answered", "rejected", "merged", "merge_failed", "expired", "withdrawn", "superseded"}


def check_transition(item, to_state):
    if to_state not in TRANSITIONS.get(item["kind"], {}).get(item["state"], set()):
        raise DecideError(3, "cannot move #{} from {} to {}".format(item["id"], item["state"], to_state))


def write_transition(store, item, to_state, reason=None, by=None):
    check_transition(item, to_state)
    data = {"from": item["state"], "to": to_state}
    if reason is not None:
        data["reason"] = reason
    if by is not None:
        data["by"] = by
    return store.append("transition", item["id"], data)


def fold(events):
    result = {}
    for event in events:
        event_type = event["type"]
        item_id = event["id"]
        data = event["data"]
        if event_type in ("ask", "import"):
            if event_type == "ask":
                request = data["request"]
                item = {"id": item_id, "kind": request["kind"],
                        "state": "open" if request["kind"] == "pr_merge" else "ready",
                        "request": request, "created_at": event["ts"], "updated_at": event["ts"],
                        "closed_at": None, "last_shown_at": None, "verify": None,
                        "answer": None, "legacy": False, "rank": None}
            else:
                record = data["record"]
                item = {"id": item_id, "kind": record["kind"], "state": record["state"],
                        "request": {key: value for key, value in record.items()
                                    if key not in ("id", "state", "rank")},
                        "created_at": record["created_at"], "updated_at": record["created_at"],
                        "closed_at": None, "last_shown_at": None, "verify": None,
                        "answer": None, "legacy": True, "rank": record["rank"]}
            result[item_id] = item
            continue
        if item_id not in result:
            raise DecideError(5, "event {} refers to unknown item {}".format(event["seq"], item_id))
        item = result[item_id]
        if event_type == "transition":
            item["state"] = data["to"]
            item["updated_at"] = event["ts"]
            if data["to"] in CLOSED:
                item["closed_at"] = event["ts"]
            if data["to"] == "shown":
                item["last_shown_at"] = event["ts"]
        elif event_type == "chase":
            item["last_shown_at"] = event["ts"]
        elif event_type == "verify":
            item["verify"] = data
        elif event_type == "answer":
            item["answer"] = data
        elif event_type == "amend":
            item["request"] = data["request"]
    return result


def items(store):
    return fold(store.read_events())


def get_item(store, item_id):
    item = items(store).get(item_id)
    if item is None:
        raise DecideError(4, "no item #{}".format(item_id))
    return item


def _status(args):
    current = items(Store(home_dir(args)))
    if (args.requester is None) != (args.key is None):
        raise DecideError(2, "status requires both requester and key")
    if args.requester is not None:
        found = next((item for item in current.values()
                      if item["request"].get("requester") == args.requester
                      and item["request"].get("key") == args.key), None)
        if found is None:
            raise DecideError(4, "no item for requester and key")
        item = found
    else:
        item = current.get(args.id)
        if item is None:
            raise DecideError(4, "no item #{}".format(args.id))
    answer = item["answer"]
    summary = {"id": item["id"], "state": item["state"], "kind": item["kind"],
               "title": item["request"].get("title"),
               "answer": ({key: answer.get(key) for key in ("choice", "label", "words")}
                          if answer is not None else None)}
    emit(args, summary, "#{} {} {}: {}".format(item["id"], item["state"], item["kind"], summary["title"]))
    return 0


def _list(args):
    all_items = items(Store(home_dir(args)))
    selected = [item for item in all_items.values()
                if (not args.open or item["state"] not in CLOSED)
                and (args.requester is None or item["request"].get("requester") == args.requester)]
    selected.sort(key=lambda item: item["id"])
    output = [{"id": item["id"], "state": item["state"],
               "priority": item["request"].get("priority"), "title": item["request"].get("title"),
               "requester": item["request"].get("requester")} for item in selected]
    emit(args, output, "\n".join("#{} {} {} {}".format(row["id"], row["state"], row["priority"], row["title"])
                                  for row in output))
    return 0


def register(subparsers):
    status = subparsers.add_parser("status")
    status.add_argument("id", type=parse_item_id, nargs="?")
    status.add_argument("--requester")
    status.add_argument("--key")
    status.set_defaults(func=_status)
    listing = subparsers.add_parser("list")
    listing.add_argument("--open", action="store_true")
    listing.add_argument("--requester")
    listing.set_defaults(func=_list)
