import json
from pathlib import Path
import tempfile
import unittest

from decide_common import EXIT_ENV
from decide_config import Config, load_config
from decide_lint import mask_obj, mask_text
from tests.helpers import FIXTURES, run


CONFIG = FIXTURES / "config.json"


class ConfigFeatureTests(unittest.TestCase):
    def write_config(self, change=None, roster=None):
        directory = Path(tempfile.mkdtemp())
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        if change:
            change(data)
        (directory / "config.json").write_text(json.dumps(data), encoding="utf-8")
        (directory / "roster.yaml").write_text(
            (FIXTURES / "roster.yaml").read_text(encoding="utf-8") if roster is None else roster,
            encoding="utf-8",
        )
        self.addCleanup(lambda: __import__("shutil").rmtree(directory, ignore_errors=True))
        return directory / "config.json"

    def test_sample_config_loads(self):
        """the sample config loads"""
        cfg = load_config(CONFIG)
        self.assertEqual(cfg.reviewer_login, "example-reviewer")
        self.assertEqual(len(cfg.roster_ids), 3)

    def test_roster_names(self):
        """roster names come from the name line"""
        cfg = load_config(CONFIG)
        self.assertEqual(cfg.roster_names["11111111-1111-4111-8111-111111111111"], "Example Bot A")

    def test_page_summary_requires_waiting(self):
        """a page_summary without {waiting} exits 5"""
        path = self.write_config(lambda data: data.update(page_summary="Status {as_of}"))
        with self.assertRaisesRegex(Exception, "config: page_summary") as caught:
            load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)

    def test_missing_config(self):
        """a missing config exits 5"""
        code, _, _ = run(["--config", str(CONFIG.parent / "absent.json"), "lint-files", "x"])
        self.assertEqual(code, EXIT_ENV)

    def test_unknown_key(self):
        """an unknown config key exits 5"""
        path = self.write_config(lambda data: data.update(extra=True))
        code, _, err = run(["--config", str(path), "lint-files", "x"])
        self.assertEqual(code, EXIT_ENV)
        self.assertIn("extra", err)

    def test_roster_without_ids(self):
        """a roster with no ids exits 5"""
        path = self.write_config(roster="name: nobody\n")
        with self.assertRaises(Exception) as caught:
            load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)

    def test_bad_private_regex(self):
        """a bad private regex exits 5 without echoing it"""
        secret_regex = "(["
        path = self.write_config(lambda data: data["private_patterns"].__setitem__(0, {"name": "bad", "regex": secret_regex}))
        code, _, err = run(["--config", str(path), "lint-files", "x"])
        self.assertEqual(code, EXIT_ENV)
        self.assertNotIn(secret_regex, err)

    def test_account_number_mask(self):
        """an account number is masked to its last three digits"""
        masked, hits = mask_text("account U1234567", load_config(CONFIG))
        self.assertEqual(masked, "account U…567")
        self.assertEqual(hits, ["account"])

    def test_private_surname_mask(self):
        """a private surname is masked"""
        self.assertEqual(mask_text("Quuxley", load_config(CONFIG))[0], "[masked:surname]")

    def test_generic_mask(self):
        """a generic hit is masked by pattern name"""
        token = "gh" + "p_" + "A" * 36
        self.assertEqual(mask_text(token, load_config(CONFIG))[0], "[masked:github_token]")

    def test_nested_object_mask(self):
        """mask_obj masks nested strings but not keys"""
        result, _ = mask_obj({"Quuxley": ["U1234567"]}, load_config(CONFIG))
        self.assertEqual(result, {"Quuxley": ["U…567"]})

    def test_lint_files_report(self):
        """lint-files reports file line and pattern but not the value"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input.txt"
            target.write_text("Quuxley\n", encoding="utf-8")
            code, out, _ = run(["--config", str(CONFIG), "lint-files", str(target)])
            self.assertEqual(code, 2)
            self.assertIn("{}:1: surname".format(target), out)
            self.assertNotIn("Quuxley", out)

    def test_lint_files_exit_codes(self):
        """lint-files exits 2 on a hit and 0 when clean"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input.txt"
            target.write_text("clean\n", encoding="utf-8")
            self.assertEqual(run(["--config", str(CONFIG), "lint-files", str(target)])[0], 0)
            target.write_text("Quuxley\n", encoding="utf-8")
            self.assertEqual(run(["--config", str(CONFIG), "lint-files", str(target)])[0], 2)

    def test_lint_files_requires_config(self):
        """lint-files needs a config"""
        code, _, _ = run(["lint-files", "input.txt"], env={"DECIDE_CONFIG": ""})
        self.assertEqual(code, EXIT_ENV)


if __name__ == "__main__":
    unittest.main()
