"""Helpers shared by decide tests."""

import atexit
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import tempfile

import decide


FIXTURES = Path(__file__).parent / "fixtures"


def run(argv, env=None):
    stdout = io.StringIO()
    stderr = io.StringIO()
    previous = os.environ.copy()
    try:
        if env is not None:
            os.environ.update(env)
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = decide.main(argv)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.environ.clear()
        os.environ.update(previous)
    return code, stdout.getvalue(), stderr.getvalue()


def temp_home():
    path = Path(tempfile.mkdtemp())
    os.chmod(path, 0o700)
    atexit.register(lambda: __import__("shutil").rmtree(path, ignore_errors=True))
    return path
