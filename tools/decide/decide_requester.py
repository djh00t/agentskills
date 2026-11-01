"""Requester-side item state changes."""

import json
import re

from decide_common import DecideError, emit, home_dir
from decide_schema import safe_text
from decide_state import CLOSED, fold, write_transition
from decide_store import Store


def scan_text(value):
    """Return whether text contains a recognizable credential token."""
    prefixes = ("g" + "hp_", "gho_", "ghu_", "ghs_", "ghr_", "sk-", "AKIA")
    return any(re.search(re.escape(prefix) + r"[A-Za-z0-9_-]{8,}", value) for prefix in prefixes)


def _reason(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 200 or not safe_text(value):
        raise DecideError(2, "reason must be 1 to 200 safe characters")
    if scan_text(value):
        raise DecideError(2, "reason contains a sensitive token")
    return value


def _locked_items(store):
    result, lines = store._verify_locked()
    if not result["ok"]:
        raise DecideError(3, "cannot read a broken log", result)
    return fold([json.loads(line) for line in lines])


def _change(args, target, reason=None, sha=None):
    store = Store(home_dir(args))
    with store.lock():
        item = _locked_items(store).get(args.id)
        if item is None:
            raise DecideError(4, "no item #{}".format(args.id))
        if item["state"] in CLOSED:
            raise DecideError(3, "#{} is already {}".format(args.id, item["state"]))
        if target == "release":
            target = "open" if item["kind"] == "pr_merge" else "ready"
        if sha is not None:
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise DecideError(2, "sha must be 40 lowercase hex characters")
            reason = "merge sha " + sha
            target = "merged"
        write_transition(store, item, target, reason=reason)
    emit(args, {"id": item["id"], "state": target}, "#{} {}".format(item["id"], target))
    return 0


def _withdraw(args):
    return _change(args, "withdrawn", reason=_reason(args.reason))


def _hold(args):
    return _change(args, "on_hold", reason=_reason(args.reason))


def _release(args):
    return _change(args, "release")


def _confirm_merge(args):
    return _change(args, "merged", sha=args.sha)


def _merge_failed(args):
    return _change(args, "merge_failed", reason=_reason(args.reason))


def register(subparsers):
    for name, handler, reason in (("withdraw", _withdraw, True), ("hold", _hold, True),
                                  ("release", _release, False),
                                  ("confirm-merge", _confirm_merge, False),
                                  ("merge-failed", _merge_failed, True)):
        command = subparsers.add_parser(name)
        command.add_argument("id", type=int)
        if reason:
            command.add_argument("--reason", required=True)
        if name == "confirm-merge":
            command.add_argument("--sha", required=True)
        command.set_defaults(func=handler)
