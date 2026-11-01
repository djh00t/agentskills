"""Print connector calls for verifying a pull request."""

import json

from decide_common import DecideError, home_dir
from decide_state import CLOSED, get_item
from decide_store import Store


PLAN_FILES = ("pr.json", "reviews.json", "checks.json", "status.json")


def _verify_pr(args):
    item = get_item(Store(home_dir(args)), args.id)
    if item["kind"] != "pr_merge":
        raise DecideError(2, "item must be pr_merge")
    if item["state"] in CLOSED:
        raise DecideError(3, "item is closed")

    pr = item["request"]["pr"]
    owner, repo = pr["repo"].split("/")
    number = pr["number"]
    head = pr["head_sha"]
    plan = [
        {"tool": "get_pull_request", "arguments": {
            "owner": owner, "repo": repo, "pull_number": number}, "save_as": PLAN_FILES[0]},
        {"tool": "list_pull_request_reviews", "arguments": {
            "owner": owner, "repo": repo, "pull_number": number, "per_page": 100}, "save_as": PLAN_FILES[1]},
        {"tool": "list_check_runs_for_ref", "arguments": {
            "owner": owner, "repo": repo, "ref": head, "per_page": 100}, "save_as": PLAN_FILES[2]},
        {"tool": "get_commit_combined_status", "arguments": {
            "owner": owner, "repo": repo, "ref": head}, "save_as": PLAN_FILES[3]},
    ]
    print(json.dumps(plan))
    return 0


def register(subparsers):
    command = subparsers.add_parser("verify-pr")
    command.add_argument("id", type=int)
    command.set_defaults(func=_verify_pr)
