"""Shared helpers for the decide command line tool."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


EXIT_OK = 0
EXIT_VALIDATION = 2
EXIT_CONFLICT = 3
EXIT_NOT_FOUND = 4
EXIT_ENV = 5


class DecideError(Exception):
    def __init__(self, code, message, payload=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload


def emit(args, obj, text):
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False) if args.json else text)


def utc_now():
    value = os.environ.get("DECIDE_NOW")
    return parse_iso(value) if value is not None else datetime.now(timezone.utc)


def iso_z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    if parsed.tzinfo is None:
        raise ValueError("time must include a UTC offset")
    return parsed


def home_dir(args):
    value = getattr(args, "home", None) or os.environ.get("DECIDE_HOME")
    if not value:
        raise DecideError(EXIT_ENV, "home directory is required")
    return Path(value)


def config_path(args):
    value = getattr(args, "config", None) or os.environ.get("DECIDE_CONFIG")
    if not value:
        raise DecideError(EXIT_ENV, "config file is required")
    return Path(value)
