"""Item state transitions, event folding and read commands."""

from decide_schema import validate_event, validate_request, validate_answer, validate_legacy

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
    current = fold(store.read_events())[item["id"]]
    if current["state"] != item["state"]:
        raise DecideError(3, "stale item state")
    check_transition(current, to_state)
    data = {"from": item["state"], "to": to_state}
    if reason is not None:
        data["reason"] = reason
    if by is not None:
        data["by"] = by
    return store.append("transition", item["id"], data)


def fold(events):
    result = {}
    for event in events:
        errors = validate_event(event)
        if errors:
            raise DecideError(3, "invalid event: " + "; ".join(errors))
        event_type = event["type"]
        item_id = event["id"]
        data = event["data"]
        if event_type in ("ask", "import"):
            if item_id in result:
                raise DecideError(3, "duplicate item #{}".format(item_id))
            if event_type == "ask":
                request = data.get("request")
                errors = validate_request(request)
                if errors:
                    raise DecideError(3, "invalid request: " + "; ".join(errors))
                item = {"id": item_id, "kind": request["kind"],
                        "state": "open" if request["kind"] == "pr_merge" else "ready",
                        "request": request, "created_at": event["ts"], "updated_at": event["ts"],
                        "closed_at": None, "last_shown_at": None, "verify": None,
                        "answer": None, "legacy": False, "rank": None}
            else:
                record = data.get("record")
                errors = validate_legacy(record)
                if errors:
                    raise DecideError(3, "invalid legacy record: " + "; ".join(errors))
                if record["id"] != item_id:
                    raise DecideError(3, "legacy id mismatch")
                request = {key: value for key, value in record.items() if key not in ("id", "state", "rank", "created_at")}
                errors = validate_request(request)
                if errors:
                    raise DecideError(3, "invalid legacy request: " + "; ".join(errors))
                transitions = TRANSITIONS[record["kind"]]
                reachable = set(transitions).union(*transitions.values())
                if record["state"] not in reachable:
                    raise DecideError(3, "invalid legacy state for kind")
                created_at = record.get("created_at", event["ts"])
                item = {"id": item_id, "kind": record["kind"], "state": record["state"],
                        "request": request,
                        "created_at": created_at, "updated_at": created_at,
                        "closed_at": created_at if record["state"] in CLOSED else None, "last_shown_at": None, "verify": None,
                        "answer": None, "legacy": True, "rank": record.get("rank")}
            result[item_id] = item
            continue
        if event_type in ("page_ack", "counter_floor") and item_id is None:
            continue
        if item_id not in result:
            raise DecideError(3, "event {} refers to unknown item {}".format(event["seq"], item_id))
        item = result[item_id]
        if event_type == "transition":
            if data.get("from") != item["state"] or not isinstance(data.get("to"), str):
                raise DecideError(3, "invalid transition")
            check_transition(item, data["to"])
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
            errors = validate_answer(data)
            if errors:
                raise DecideError(3, "invalid answer: " + "; ".join(errors))
            item["answer"] = data
        elif event_type == "amend":
            request = data.get("request")
            errors = validate_request(request)
            if errors or request["kind"] != item["kind"]:
                raise DecideError(3, "invalid amended request")
            item["request"] = request
    return result


def items(store):
    return fold(store.read_events())


def get_item(store, item_id):
    item = items(store).get(item_id)
    if item is None:
        display_id = str(item_id)
        if len(display_id) > 32:
            display_id = display_id[:32] + "..."
        raise DecideError(4, "no item #{}".format(display_id))
    return item


def _status(args):
    if (args.requester is None) != (args.key is None):
        raise DecideError(2, "status requires both requester and key")
    if args.id is None and args.requester is None or args.id is not None and args.requester is not None:
        raise DecideError(2, "status requires an id or requester and key")
    store = Store(home_dir(args))
    if args.requester is not None:
        current = items(store)
        found = next((item for item in current.values()
                      if item["request"].get("requester") == args.requester
                      and item["request"].get("key") == args.key), None)
        if found is None:
            raise DecideError(4, "no item for requester and key")
        item = found
    else:
        item = get_item(store, args.id)
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
