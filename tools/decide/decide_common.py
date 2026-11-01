"""Shared helpers for the decide command line tool."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


EXIT_CONFLICT = 3
EXIT_ENV = 5


class DecideError(Exception):
    def __init__(self, code, message, payload=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload


def emit(args, obj, text):
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False) if args.json else text)


def home_dir(args):
    value = getattr(args, "home", None) or os.environ.get("DECIDE_HOME")
    if not value:
        raise DecideError(EXIT_ENV, "home directory is required")
    return Path(value)


def utc_now():
    return datetime.now(timezone.utc)


def iso_z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
