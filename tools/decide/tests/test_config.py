import json
import re
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

from decide_common import DecideError, EXIT_ENV
from decide_config import Config, _secure_file, load_config
from decide_lint import mask_obj, mask_text, scan_private
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

    def test_config_is_immutable(self):
        cfg = load_config(self.config)
        with self.assertRaises(FrozenInstanceError) as caught:
            cfg.page_title = "changed"
        self.assertEqual(str(caught.exception), "cannot assign to field 'page_title'")

    def test_string_length_boundaries(self):
        for length in (0, 1, 79, 80, 81):
            with self.subTest(field="page_title", length=length):
                path = self.write_config(lambda d: d.update(page_title="x" * length))
                if 1 <= length <= 80:
                    self.assertEqual(load_config(path).page_title, "x" * length)
                else:
                    with self.assertRaises(DecideError) as caught:
                        load_config(path)
                    self.assertEqual(str(caught.exception), "config: page_title is invalid")
        prefix = "{as_of} {waiting}"
        for length in (399, 400, 401):
            with self.subTest(field="page_summary", length=length):
                summary = prefix + "x" * (length - len(prefix))
                path = self.write_config(lambda d: d.update(page_summary=summary))
                if length <= 400:
                    self.assertEqual(load_config(path).page_summary, summary)
                else:
                    with self.assertRaises(DecideError) as caught:
                        load_config(path)
                    self.assertEqual(str(caught.exception), "config: page_summary is invalid")

    def test_check_times_count_boundaries(self):
        for count in (0, 1, 5, 6, 7):
            with self.subTest(count=count):
                times = [f"{hour:02}:00" for hour in range(count)]
                path = self.write_config(lambda d: d.update(check_times=times))
                if 1 <= count <= 6:
                    self.assertEqual(load_config(path).check_times, tuple(times))
                else:
                    with self.assertRaises(DecideError) as caught:
                        load_config(path)
                    self.assertEqual(str(caught.exception), "config: check_times is invalid")

    def test_roster_parent_symlink_boundaries(self):
        path = self.write_config()
        alias = path.parent.parent / (path.parent.name + "-alias")
        alias.symlink_to(path.parent, target_is_directory=True)
        self.addCleanup(alias.unlink)
        self.assertEqual(load_config(alias / path.name).roster_ids, load_config(path).roster_ids)

        final_link = path.parent / "roster-link.yaml"
        final_link.symlink_to(path.parent / "roster.yaml")
        data = json.loads(path.read_text())
        data["roster_path"] = final_link.name
        path.write_text(json.dumps(data))
        with self.assertRaises(DecideError) as caught:
            load_config(path)
        self.assertEqual(str(caught.exception), "config: roster_path is invalid")

        (path.parent / "actual").mkdir()
        shutil.copy(path.parent / "roster.yaml", path.parent / "actual" / "roster.yaml")
        (path.parent / "link").symlink_to(path.parent / "actual", target_is_directory=True)
        data = json.loads(path.read_text())
        data["roster_path"] = "link/roster.yaml"
        path.write_text(json.dumps(data))
        with self.assertRaises(DecideError) as caught:
            load_config(path)
        self.assertEqual(str(caught.exception), "config: roster_path is invalid")

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
        with patch.dict("os.environ", {"DECIDE_CONFIG": ""}):
            code, _, _ = run(["lint-files", "input.txt"])
        self.assertEqual(code, EXIT_ENV)

    def test_invalid_config_rules(self):
        """invalid configuration rules fail without exposing values"""
        cases = [
            lambda d: d.pop("version"), lambda d: d.update(version=2),
            lambda d: d.update(roster_path="/outside"), lambda d: d.update(roster_path="../outside"),
            lambda d: d.update(roster_path="missing"), lambda d: d.update(reviewer_login="!"),
            lambda d: d.update(reviewer_login=9),
            lambda d: d.update(private_patterns={}),
            lambda d: d.update(private_patterns=[{"name": "x", "regex": 9}]),
            lambda d: d.update(mask_rules=[{"name": "x", "regex": "x", "replace": "\\g<8>"}]),
            lambda d: d.update(verdict_regex="["), lambda d: d.update(verdict_regex="abc"),
            lambda d: d.update(timezone="Invalid/Zone"), lambda d: d.update(timezone="/invalid"), lambda d: d.update(check_times=[]),
            lambda d: d.update(check_times=["12:00", "09:00"]),
            lambda d: d.update(check_times=["25:00"]),
            lambda d: d.update(private_patterns=[{"name": "x", "regex": "x", "extra": True}]),
            lambda d: d.update(page_summary="{as_of} {waiting} {extra}"),
            lambda d: d.update(private_patterns=[{"name": "x"}]),
            lambda d: d.update(private_patterns=[{"name": "x", "regex": "x"}] * 2),
            lambda d: d.update(private_patterns=[{"name": "!", "regex": "x"}]),
            lambda d: d.update(private_patterns=[{"name": "x", "regex": ""}]),
            lambda d: d.update(mask_rules=[{"name": "x", "regex": "x", "replace": "\\g<0>"}]),
            lambda d: d.update(mask_rules=[{"name": "x", "regex": "x", "replace": 9}]),
            lambda d: d.update(page_title=""), lambda d: d.update(page_summary="x"),
            lambda d: d.update(page_summary="{as_of} {waiting}" + "x" * 400),
            lambda d: d.update(page_summary="{waiting} {waiting}"),
            lambda d: d.update(page_summary="{waiting} {extra}"),
            lambda d: d.update(page_summary="{as_of} {extra}"),
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
            for mode in (0o601, 0o640, 0o666):
                path = self.write_config()
                (path.parent / filename).chmod(mode)
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

    def test_config_file_validation_boundaries(self):
        """config files and roster paths enforce their separate guards"""
        path = self.write_config()
        path.write_text("[]", encoding="utf-8")
        with self.assertRaises(Exception) as caught:
            load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)

        path = self.write_config()
        data = json.loads(path.read_text())
        data["roster_path"] = str(path.parent / "roster.yaml")
        path.write_text(json.dumps(data))
        with patch.object(Path, "is_symlink", return_value=False):
            with self.assertRaises(Exception) as caught:
                load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)

        path = self.write_config()
        (path.parent / "actual").mkdir(mode=0o700)
        shutil.copy(path.parent / "roster.yaml", path.parent / "actual" / "roster.yaml")
        (path.parent / "alias").symlink_to(path.parent / "actual", target_is_directory=True)
        data = json.loads(path.read_text())
        data["roster_path"] = "alias/roster.yaml"
        path.write_text(json.dumps(data))
        with self.assertRaises(Exception) as caught:
            load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)

        path = self.write_config()
        with patch("decide_config.os.getuid", return_value=-1):
            with self.assertRaises(Exception) as caught:
                load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)

        alias = path.parent / "alias.json"
        alias.symlink_to(path)
        with self.assertRaises(Exception) as caught:
            _secure_file(alias, "file")
        self.assertEqual(caught.exception.code, EXIT_ENV)

        directory = path.parent / "directory"
        directory.mkdir(mode=0o700)
        with self.assertRaises(Exception) as caught:
            _secure_file(directory, "file")
        self.assertEqual(caught.exception.code, EXIT_ENV)

    def test_resolved_roster_path_containment(self):
        """a resolved roster outside the config directory exits 5"""
        original = Path.resolve

        def resolve(path, *args, **kwargs):
            if path.name == "roster.yaml":
                return path.parent.parent / "outside" / path.name
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve):
            with self.assertRaises(Exception) as caught:
                load_config(self.config)
        self.assertEqual(caught.exception.code, EXIT_ENV)

    def test_scan_length_before_and_after_normalization(self):
        """scan limits apply before and after normalization"""
        cfg = load_config(self.config)
        for value in ("A\u030a" * 32769, "\ufb03" * 21846):
            with self.subTest(length=len(value)):
                with self.assertRaises(Exception) as caught:
                    mask_text(value, cfg)
                self.assertEqual(caught.exception.code, 2)

    def test_read_failures_and_type_guards(self):
        """unreadable private files and invalid types fail closed"""
        invalid = self.write_config()
        invalid.write_text("{", encoding="utf-8")
        with self.assertRaises(Exception) as caught:
            load_config(invalid)
        self.assertEqual(caught.exception.code, EXIT_ENV)
        path = self.write_config(lambda d: d.update(roster_path=""))
        code, _, err = run(["--config", str(path), "lint-files", "x"])
        self.assertEqual(code, EXIT_ENV)
        self.assertIn("config: roster_path is invalid", err)
        for change in (lambda d: d.update(version=True),
                       lambda d: d.update(check_times="09:00"),
                       lambda d: d.update(check_times=9),
                       lambda d: d.update(check_times=[9]),
                       lambda d: d.update(private_patterns=[9]),
                       lambda d: d.update(private_patterns=[{"name": 9, "regex": "x"}])):
            with self.subTest(change=change):
                with self.assertRaises(Exception) as caught:
                    load_config(self.write_config(change))
                self.assertEqual(caught.exception.code, EXIT_ENV)

    def test_mask_collisions_deduplication_and_directory(self):
        """mask collisions and duplicate hits are handled safely"""
        cfg = load_config(self.config)
        with self.assertRaisesRegex(Exception, "masked keys collide"):
            mask_obj({"Quuxley": 1, "QUUXLEY": 2}, cfg)
        self.assertEqual(mask_obj(["Quuxley", "Quuxley"], cfg)[1], ["surname"])
        cfg = replace(cfg, private=(("github_token", re.compile("uniquevalue")),))
        token = "gh" + "p_" + "A" * 36
        self.assertEqual(mask_text(token + " uniquevalue", cfg)[1], ["github_token"])
        with tempfile.TemporaryDirectory() as directory:
            code, _, err = run(["--config", str(self.config), "lint-files", directory])
            self.assertEqual(code, 4)
            self.assertIn("not a regular file", err)
            code, _, err = run(["--config", str(self.config), "lint-files", str(Path(directory) / "missing")])
            self.assertEqual(code, 4)
            self.assertIn("file not found", err)

    def test_roster_name_does_not_cross_entries(self):
        """roster names do not cross sibling entries"""
        identifier = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        path = self.write_config(roster="- id: " + identifier + "\nother: value\n  name: misplaced\n")
        self.assertEqual(load_config(path).roster_names[identifier], identifier)
        path = self.write_config(roster="- id: " + identifier + "\n\n  other: value\n  name: Correct\n")
        self.assertEqual(load_config(path).roster_names[identifier], "Correct")

    def test_mask_preserves_unmatched_line_breaks(self):
        """mask preserves unmatched line breaks"""
        cfg = load_config(self.config)
        self.assertEqual(mask_text("Hello\nWorld", cfg), ("Hello\nWorld", []))
        self.assertEqual(mask_text("before\nQuu\nxley\nafter", cfg)[0], "before\n[masked:surname]\nafter")
        self.assertEqual(mask_text("U123\n4567", cfg)[0], "U…567")
        self.assertEqual(mask_text("Quu\nxley\nafter", cfg)[0], "[masked:surname]\nafter")
        self.assertEqual(mask_text("before\nQuu\nxley", cfg)[0], "before\n[masked:surname]")
        self.assertEqual(mask_text("xley\nsafe\nQuu", cfg)[0], "xley\nsafe\nQuu")

    def test_wrapped_private_scan(self):
        """wrapped private values are detected"""
        cfg = load_config(self.config)
        self.assertEqual(scan_private("Quu\nxley", cfg), ["surname"])
        self.assertEqual(scan_private("Ｑｕｕｘｌｅｙ", cfg), ["surname"])

    def test_unsupported_roster_id_entries(self):
        """unsupported roster id entries are rejected"""
        identifier = "11111111-1111-4111-8111-111111111111"
        for entry in (f'- {{id: {identifier}}}', f'- {{ID: {identifier}}}',
                      f'- {{"id": {identifier}}}', f'- "id": {identifier}',
                      f"- 'id': {identifier}", f'- name: x, id: {identifier}'):
            with self.subTest(entry=entry):
                with self.assertRaises(DecideError) as caught:
                    load_config(self.write_config(roster=entry + "\n- id: " + identifier + "\n"))
                self.assertEqual(caught.exception.code, EXIT_ENV)
                self.assertEqual(str(caught.exception), "config: roster_path contains an unsupported id entry")

    def test_uppercase_roster_id_key(self):
        path = self.write_config(roster="- ID: 11111111-1111-4111-8111-111111111111\n")
        self.assertEqual(len(load_config(path).roster_ids), 1)

    def test_reviewer_login_length(self):
        self.assertEqual(load_config(self.write_config(lambda d: d.update(reviewer_login="a" * 39))).reviewer_login, "a" * 39)
        with self.assertRaises(DecideError) as caught:
            load_config(self.write_config(lambda d: d.update(reviewer_login="a" * 40)))
        self.assertEqual(caught.exception.code, EXIT_ENV)
        self.assertEqual(str(caught.exception), "config: reviewer_login is invalid")

    def test_replacement_containing_full_match_is_masked(self):
        path = self.write_config(lambda d: d.update(mask_rules=[{"name": "acct", "regex": "(U[0-9]+)", "replace": r"[\1]"}]))
        self.assertEqual(mask_text("U123", load_config(path))[0], "[masked:acct]")

    def test_all_missing_keys_are_reported(self):
        path = self.write_config(lambda d: (d.pop("version"), d.pop("timezone"), d.update(extra=True)))
        with self.assertRaises(DecideError) as caught:
            load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)
        self.assertEqual(str(caught.exception), "config: keys required: timezone, version; unknown: extra")

    def test_invalid_utf8_is_rejected(self):
        path = self.write_config()
        path.write_bytes(b"\xff")
        with self.assertRaises(DecideError) as caught:
            load_config(path)
        self.assertEqual(caught.exception.code, EXIT_ENV)
        self.assertEqual(str(caught.exception), "config: file cannot be read")

    def test_lint_pair_results_include_path_and_line(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            first.write_text("Quuxley\nx", encoding="utf-8")
            second.write_text("x\nQuuxley", encoding="utf-8")
            code, out, _ = run(["--json", "--config", str(self.config), "lint-files", str(first), str(second)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out), [{"path": str(first), "line": 1, "pattern": "surname"},
                                               {"path": str(second), "line": 2, "pattern": "surname"}])

    def test_lint_pair_deduplicates_each_file_and_line(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            first.write_text("Quuxley\n ", encoding="utf-8")
            second.write_text(" \nQuuxley", encoding="utf-8")
            for args, expected in (([str(first), str(second)],
                                    [{"path": str(first), "line": 1, "pattern": "surname"},
                                     {"path": str(second), "line": 2, "pattern": "surname"}]),):
                code, out, _ = run(["--json", "--config", str(self.config), "lint-files"] + args)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(out), expected)
            code, out, _ = run(["--config", str(self.config), "lint-files", str(second)])
            self.assertEqual(code, 2)
            self.assertEqual(out.strip(), f"{second}:2: surname")

    def test_lint_wrapped_values(self):
        """wrapped file values report their first line"""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input"
            target.write_text("Quu\nxley\nU123\n4567", encoding="utf-8")
            code, out, _ = run(["--json", "--config", str(self.config), "lint-files", str(target)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out), [{"path": str(target), "line": 1, "pattern": "surname"},
                                               {"path": str(target), "line": 3, "pattern": "mask:account"}])
            code, out, _ = run(["--config", str(self.config), "lint-files", str(target)])
            self.assertEqual(code, 2)
            self.assertEqual(out.strip(), f"{target}:1: surname\n{target}:3: mask:account")

    def test_lint_long_space_line_is_fast(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "input"
            target.write_text("x\n" + " " * 16000, encoding="utf-8")
            start = time.monotonic()
            self.assertEqual(run(["--config", str(self.config), "lint-files", str(target)])[0], 0)
            self.assertLess(time.monotonic() - start, 0.5)

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
        for value in ("Ｑｕｕｘｌｅｙ", "Quu\u200bxley", "Quu\ufe0fxley", "Quu\u0301xley"):
            self.assertEqual(mask_text(value, cfg)[0], "[masked:surname]")
        for value in ("Ｕ１２３４５６７", "U123\u200b4567", "U123\ufe0f4567"):
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
