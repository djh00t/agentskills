import json
from pathlib import Path
import tempfile
import shutil
import unittest

from decide_common import EXIT_ENV
from decide_config import Config, load_config
from decide_lint import mask_obj, mask_text
from tests.helpers import FIXTURES, run


CONFIG = FIXTURES / "config.json"


class ConfigFeatureTests(unittest.TestCase):
    def setUp(self):
        self.config = self.write_config()

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
        (directory / "config.json").chmod(0o600)
        (directory / "roster.yaml").chmod(0o600)
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        return directory / "config.json"

    def test_sample_config_loads(self):
        """the sample config loads"""
        cfg = load_config(self.config)
        self.assertEqual(cfg.reviewer_login, "example-reviewer")
        self.assertEqual(len(cfg.roster_ids), 3)

    def test_roster_names(self):
        """roster names come from the name line"""
        cfg = load_config(self.config)
        self.assertEqual(cfg.roster_names["11111111-1111-4111-8111-111111111111"], "Example Bot A")

    def test_page_summary_requires_waiting(self):
        """a page_summary without {waiting} exits 5"""
        path = self.write_config(lambda data: data.update(page_summary="Status {as_of}"))
        with self.assertRaisesRegex(Exception, "config: page_summary") as caught:
            load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)

    def test_missing_config(self):
        """a missing config exits 5"""
        code, _, _ = run(["--config", str(self.config.parent / "absent.json"), "lint-files", "x"])
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
        masked, hits = mask_text("account U1234567", load_config(self.config))
        self.assertEqual(masked, "account U…567")
        self.assertEqual(hits, ["account"])

    def test_private_surname_mask(self):
        """a private surname is masked"""
        self.assertEqual(mask_text("Quuxley", load_config(self.config))[0], "[masked:surname]")

    def test_generic_mask(self):
        """a generic hit is masked by pattern name"""
        token = "gh" + "p_" + "A" * 36
        self.assertEqual(mask_text(token, load_config(self.config))[0], "[masked:github_token]")

    def test_nested_object_mask(self):
        """mask_obj masks nested strings and keys"""
        result, _ = mask_obj({"Quuxley": ["U1234567"]}, load_config(self.config))
        self.assertEqual(result, {"[masked:surname]": ["U…567"]})

    def test_lint_files_report(self):
        """lint-files reports file line and pattern but not the value"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input.txt"
            target.write_text("Quuxley\n", encoding="utf-8")
            code, out, _ = run(["--config", str(self.config), "lint-files", str(target)])
            self.assertEqual(code, 2)
            self.assertIn("{}:1: surname".format(target), out)
            self.assertNotIn("Quuxley", out)

    def test_lint_files_exit_codes(self):
        """lint-files exits 2 on a hit and 0 when clean"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input.txt"
            target.write_text("clean\n", encoding="utf-8")
            self.assertEqual(run(["--config", str(self.config), "lint-files", str(target)])[0], 0)
            target.write_text("Quuxley\n", encoding="utf-8")
            self.assertEqual(run(["--config", str(self.config), "lint-files", str(target)])[0], 2)

    def test_lint_files_requires_config(self):
        """lint-files needs a config"""
        code, _, _ = run(["lint-files", "input.txt"], env={"DECIDE_CONFIG": ""})
        self.assertEqual(code, EXIT_ENV)

    def test_invalid_config_rules(self):
        """invalid configuration rules fail without exposing values"""
        cases = [
            lambda d: d.pop("version"), lambda d: d.update(version=2),
            lambda d: d.update(roster_path="/outside"), lambda d: d.update(roster_path="../outside"),
            lambda d: d.update(roster_path="missing"), lambda d: d.update(reviewer_login="!"),
            lambda d: d.update(verdict_regex="["), lambda d: d.update(verdict_regex="abc"),
            lambda d: d.update(timezone="Invalid/Zone"), lambda d: d.update(check_times=[]),
            lambda d: d.update(check_times=["12:00", "09:00"]),
            lambda d: d.update(private_patterns=[{"name": "x"}]),
            lambda d: d.update(private_patterns=[{"name": "x", "regex": "x"}] * 2),
            lambda d: d.update(private_patterns=[{"name": "!", "regex": "x"}]),
            lambda d: d.update(private_patterns=[{"name": "x", "regex": ""}]),
            lambda d: d.update(mask_rules=[{"name": "x", "regex": "x", "replace": "\\g<0>"}]),
            lambda d: d.update(mask_rules=[{"name": "x", "regex": "x", "replace": 9}]),
            lambda d: d.update(page_title=""), lambda d: d.update(page_summary="x"),
            lambda d: d.update(page_summary="{as_of} {waiting}" + "x" * 400),
            lambda d: d.update(page_summary="{waiting} {waiting}"),
        ]
        for change in cases:
            with self.subTest(change=change):
                path = self.write_config(change)
                code, out, err = run(["--config", str(path), "lint-files", "x"])
                self.assertEqual(code, EXIT_ENV)
                self.assertNotIn("Invalid/Zone", out + err)

    def test_private_file_permissions_and_roster_ids(self):
        """private files and roster ids are validated"""
        for filename in ("config.json", "roster.yaml"):
            path = self.write_config()
            (path.parent / filename).chmod(0o666)
            self.assertEqual(run(["--config", str(path), "lint-files", "x"])[0], EXIT_ENV)
        identifier = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
        path = self.write_config(roster="- id: " + identifier + " # comment\n")
        self.assertIn(identifier.lower(), load_config(path).roster_ids)
        for roster in ("- id: invalid\n", "- id: " + identifier + "\n- id: " + identifier.lower() + "\n"):
            path = self.write_config(roster=roster)
            self.assertEqual(run(["--config", str(path), "lint-files", "x"])[0], EXIT_ENV)

    def test_roster_name_scope_and_default(self):
        """roster names stay within their entry and default to the id"""
        identifier = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        path = self.write_config(roster="  - id: " + identifier + "\n  name: outside\n")
        self.assertEqual(load_config(path).roster_names[identifier], identifier)

    def test_roster_symlink_and_traversal(self):
        """roster paths cannot escape or use symlinks"""
        path = self.write_config()
        (path.parent / "link.yaml").symlink_to(path.parent / "roster.yaml")
        data = json.loads(path.read_text())
        data["roster_path"] = "link.yaml"
        path.write_text(json.dumps(data))
        self.assertEqual(run(["--config", str(path), "lint-files", "x"])[0], EXIT_ENV)
        data["roster_path"] = "../" + path.parent.name + "/roster.yaml"
        path.write_text(json.dumps(data))
        self.assertEqual(run(["--config", str(path), "lint-files", "x"])[0], EXIT_ENV)

    def test_scan_length_limit(self):
        """oversized fields and lines fail closed"""
        with self.assertRaises(Exception) as caught:
            mask_text("a" * 65537, load_config(self.config))
        self.assertEqual(caught.exception.code, 2)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input"
            target.write_text("a" * 65537, encoding="utf-8")
            self.assertEqual(run(["--config", str(self.config), "lint-files", str(target)])[0], 2)

    def test_normalized_masking_and_json_report(self):
        """normalized values are masked and JSON reports never echo matches"""
        cfg = load_config(self.config)
        for value in ("Ｑｕｕｘｌｅｙ", "Quu\u200bxley"):
            self.assertEqual(mask_text(value, cfg)[0], "[masked:surname]")
        for value in ("Ｕ１２３４５６７", "U123\u200b4567"):
            self.assertEqual(mask_text(value, cfg)[0], "U…567")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input"
            token = "gh" + "p_" + "A" * 36
            target.write_text(token + "\nU1234567\nQuuxley\n", encoding="utf-8")
            code, out, err = run(["--json", "--config", str(self.config), "lint-files", str(target)])
            self.assertEqual(code, 2)
            self.assertIn("github_token", out)
            self.assertIn("mask:account", out)
            for value in (token[:8], token[8:], "U1234567", "Quuxley"):
                self.assertNotIn(value, out + err)


if __name__ == "__main__":
    unittest.main()
