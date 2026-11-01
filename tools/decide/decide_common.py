"""Shared helpers for the decide command line tool."""

import json
import os
import re
from pathlib import Path


EXIT_OK = 0
EXIT_VALIDATION = 2
EXIT_NOT_FOUND = 4
EXIT_ENV = 5
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


class DecideError(Exception):
    def __init__(self, code, message, payload=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload


def emit(args, obj, text):
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False) if args.json else text)


def config_path(args):
    value = getattr(args, "config", None) or os.environ.get("DECIDE_CONFIG")
    if not value:
        raise DecideError(EXIT_ENV, "config file is required")
    return Path(value)
