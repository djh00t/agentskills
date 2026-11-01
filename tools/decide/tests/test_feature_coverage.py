"""Keep feature scenarios linked to exactly one test method."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FeatureCoverageTests(unittest.TestCase):
    def test_each_scenario_has_one_test(self):
        scenarios = []
        for feature in sorted((ROOT / "features").glob("*.feature")):
            scenarios.extend(
                line.split("Scenario:", 1)[1].strip()
                for line in feature.read_text(encoding="utf-8").splitlines()
                if "Scenario:" in line
            )
        tests = []
        for test_file in sorted((ROOT / "tests").glob("test_*.py")):
            tree = ast.parse(test_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    doc = ast.get_docstring(node)
                    if doc:
                        tests.append(doc.splitlines()[0])
        invalid = [name for name in scenarios if tests.count(name) != 1]
        self.assertEqual([], invalid, "scenarios with zero or multiple tests: " + ", ".join(invalid))
