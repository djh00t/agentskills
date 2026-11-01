"""Command line behaviour tests."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import decide
from decide_common import DecideError
from tests.helpers import run


class CliTests(unittest.TestCase):
    def test_version_prints_the_tool_and_schema_version(self):
        """version prints the tool and schema version"""
        code, stdout, stderr = run(["version"])
        self.assertEqual((0, "decide 0.1.0 (schema 1)\n", ""), (code, stdout, stderr))
        code, stdout, stderr = run(["--json", "version"])
        self.assertEqual(0, code)
        self.assertEqual({"tool": "decide", "version": "0.1.0", "schema": 1}, json.loads(stdout))
        self.assertEqual("", stderr)

    def test_an_unknown_command_is_a_usage_error(self):
        """an unknown command is a usage error"""
        code, _, _ = run(["nope"])
        self.assertEqual(2, code)

    def test_no_command_is_a_usage_error(self):
        """no command is a usage error"""
        code, stdout, stderr = run([])
        self.assertEqual(2, code)
        self.assertEqual("", stdout)
        self.assertIn("usage:", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_registered_command_reports_errors(self):
        """registered commands report errors in text and JSON modes"""
        def fail(_args):
            raise DecideError(5, "boom", {"k": 1})

        def register(subparsers):
            subparsers.add_parser("probe").set_defaults(func=fail)

        with patch.object(decide, "COMMANDS", (SimpleNamespace(register=register),)):
            for argv, expected in ((["probe"], ""), (["--json", "probe"], '{"k": 1}\n')):
                with self.subTest(argv=argv):
                    code, stdout, stderr = run(argv)
                    self.assertEqual(5, code)
                    self.assertEqual(expected, stdout)
                    self.assertEqual("decide: error: boom\n", stderr)
