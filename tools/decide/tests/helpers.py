"""Helpers shared by decide tests."""

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path

import decide


FIXTURES = Path(__file__).parent / "fixtures"


def run(argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = decide.main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, stdout.getvalue(), stderr.getvalue()
