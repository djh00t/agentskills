"""Shared helpers for the decide command line tool."""

import argparse
import json
import os
import re
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


def parse_item_id(value):
    if not re.fullmatch(r"[0-9]+", value):
        raise argparse.ArgumentTypeError("item id must contain ASCII digits")
    return int(value)
