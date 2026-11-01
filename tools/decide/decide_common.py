"""Shared helpers for the decide command line tool."""

import json


class DecideError(Exception):
    def __init__(self, code, message, payload=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload


def emit(args, obj, text):
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False) if args.json else text)
