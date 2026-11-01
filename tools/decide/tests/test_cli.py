"""Command line behaviour tests."""

import json
import os
from pathlib import Path
import sys
import unittest

import decide_common
from tests.helpers import run


TOOL_DIR = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.probe = TOOL_DIR / "decide_zz_probe.py"

    def tearDown(self):
        self.probe.unlink(missing_ok=True)
        sys.modules.pop("decide_zz_probe", None)

    def _write_probe(self, body):
        self.probe.write_text(body, encoding="utf-8")
        sys.modules.pop("decide_zz_probe", None)

    def test_version_prints_the_tool_and_schema_version(self):
        """version prints the tool and schema version"""
        code, stdout, _ = run(["--json", "version"])
        self.assertEqual(0, code)
        self.assertEqual({"tool": "decide", "version": "0.1.0", "schema": 1}, json.loads(stdout))

    def test_an_unknown_command_is_a_usage_error(self):
        """an unknown command is a usage error"""
        code, _, _ = run(["nope"])
        self.assertEqual(2, code)

    def test_a_module_that_defines_register_adds_a_command(self):
        """a module that defines register adds a command"""
        self._write_probe(
            "def register(subparsers):\n"
            "    command = subparsers.add_parser('zz-probe')\n"
            "    command.set_defaults(func=lambda args: 0)\n"
        )
        self.assertEqual(0, run(["zz-probe"])[0])

    def test_a_decideerror_becomes_its_exit_code_and_a_stderr_message(self):
        """a DecideError becomes its exit code and a stderr message"""
        self._write_probe(
            "from decide_common import DecideError\n"
            "def register(subparsers):\n"
            "    command = subparsers.add_parser('zz-probe')\n"
            "    command.set_defaults(func=lambda args: (_ for _ in ()).throw(DecideError(4, 'no such item')))\n"
        )
        code, _, stderr = run(["zz-probe"])
        self.assertEqual(4, code)
        self.assertEqual("decide: error: no such item\n", stderr)

    def test_home_dir_fails_closed_when_no_home_is_given(self):
        """home_dir fails closed when no home is given"""
        with self.assertRaises(decide_common.DecideError) as caught:
            decide_common.home_dir(type("Args", (), {"home": None})())
        self.assertEqual(5, caught.exception.code)

    def test_parse_iso_rejects_a_time_without_an_offset(self):
        """parse_iso rejects a time without an offset"""
        with self.assertRaises(ValueError):
            decide_common.parse_iso("2026-01-05T10:00:00")
        value = decide_common.parse_iso("2026-01-05T10:00:00Z")
        self.assertEqual("UTC", value.tzname())

    def test_decide_now_overrides_the_clock(self):
        """DECIDE_NOW overrides the clock"""
        self.assertEqual("2026-01-05T10:00:00Z", decide_common.iso_z(
            _utc_now_with_env("2026-01-05T10:00:00Z")
        ))


def _utc_now_with_env(value):
    previous = os.environ.get("DECIDE_NOW")
    os.environ["DECIDE_NOW"] = value
    try:
        return decide_common.utc_now()
    finally:
        if previous is None:
            os.environ.pop("DECIDE_NOW", None)
        else:
            os.environ["DECIDE_NOW"] = previous
