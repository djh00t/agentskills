"""Keep feature scenarios linked to exactly one test method."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def uncovered_scenarios(feature_texts, test_texts):
    scenarios = [
        line.split("Scenario:", 1)[1].strip()
        for text in feature_texts
        for line in text.splitlines()
        if line.strip().startswith("Scenario:")
    ]
    tests = []
    for text in test_texts:
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                doc = ast.get_docstring(node)
                if doc:
                    tests.append(doc.splitlines()[0])
    return [name for name in scenarios if tests.count(name) != 1]


class FeatureCoverageTests(unittest.TestCase):
    def test_each_scenario_has_one_test(self):
        features = (p.read_text(encoding="utf-8") for p in sorted((ROOT / "features").glob("*.feature")))
        tests = (p.read_text(encoding="utf-8") for p in sorted((ROOT / "tests").glob("test_*.py")))
        invalid = uncovered_scenarios(features, tests)
        self.assertEqual([], invalid, "scenarios with zero or multiple tests: " + ", ".join(invalid))

    def test_coverage_guard(self):
        feature = "  Scenario: covered\n  Scenario: missing\n  Scenario: duplicate\n# Scenario: comment\n  Scenario Outline: outline\n"
        tests = '''def test_one():
    """covered"""
def test_two():
    """duplicate"""
async def test_three():
    """duplicate"""
'''
        self.assertEqual(["missing", "duplicate"], uncovered_scenarios([feature], [tests]))
