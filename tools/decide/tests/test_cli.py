"""Command line behaviour tests."""

import json
import unittest

from tests.helpers import run


class CliTests(unittest.TestCase):
    def test_version_prints_the_tool_and_schema_version(self):
        """version prints the tool and schema version"""
        code, stdout, _ = run(["--json", "version"])
        self.assertEqual(0, code)
        self.assertEqual({"tool": "decide", "version": "0.1.0", "schema": 1}, json.loads(stdout))

    def test_an_unknown_command_is_a_usage_error(self):
        """an unknown command is a usage error"""
        code, _, _ = run(["nope"])
        self.assertEqual(2, code)
