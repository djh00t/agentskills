#!/usr/bin/env python3
"""Command line entry point for decide."""

import argparse
import json
import sys

from decide_common import DecideError, emit
import decide_store
import decide_state

COMMANDS = (decide_state, decide_store)


def _version(args):
    emit(args, {"tool": "decide", "version": "0.1.0", "schema": 1}, "decide 0.1.0 (schema 1)")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="decide")
    parser.add_argument("--home", metavar="DIR", default=None)
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    version = subparsers.add_parser("version")
    version.set_defaults(func=_version)
    for module in COMMANDS:
        module.register(subparsers)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except DecideError as exc:
        print("decide: error: " + exc.message, file=sys.stderr)
        if exc.payload is not None and args.json:
            print(json.dumps(exc.payload, sort_keys=True, ensure_ascii=False))
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
