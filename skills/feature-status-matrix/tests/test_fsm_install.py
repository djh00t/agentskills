from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL))

from fsm_ledger.install import install_codex, uninstall_codex


class CodexInstallTest(unittest.TestCase):
    def test_creates_catalog_preserves_plugins_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            catalog = home / ".agents" / "plugins" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"name": "local", "plugins": [{"name": "other"}]}), encoding="utf-8")
            with mock.patch("fsm_ledger.install.Path.home", return_value=home):
                first = install_codex()
                first_text = catalog.read_text(encoding="utf-8")
                second = install_codex()
            data = json.loads(first_text)
            self.assertTrue(first["ok"] and second["ok"])
            self.assertEqual([p["name"] for p in data["plugins"]], ["other", "fsm-ledger"])
            self.assertTrue((home / "plugins/fsm-ledger/.codex-plugin/plugin.json").exists())
            self.assertEqual(catalog.read_text(encoding="utf-8"), first_text)
            self.assertIsNone(second["catalog_backup"])

    def test_removes_only_owned_stale_copy(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            stale = home / ".agents/plugins/plugins/fsm-ledger/.codex-plugin"
            stale.mkdir(parents=True)
            (stale / "plugin.json").write_text(json.dumps({"name": "fsm-ledger"}), encoding="utf-8")
            unrelated = home / ".agents/plugins/plugins/other"
            unrelated.mkdir(parents=True)
            with mock.patch("fsm_ledger.install.Path.home", return_value=home):
                result = install_codex()
            self.assertTrue(result["ok"])
            self.assertFalse(stale.parent.exists())
            self.assertTrue(unrelated.exists())

    def test_preserves_unrelated_plugin_path(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            plugin = home / "plugins/fsm-ledger"
            plugin.mkdir(parents=True)
            (plugin / "user-file").write_text("keep", encoding="utf-8")
            with mock.patch("fsm_ledger.install.Path.home", return_value=home):
                result = install_codex()
            self.assertFalse(result["ok"])
            self.assertEqual((plugin / "user-file").read_text(), "keep")

    def test_preserves_unrelated_plugin_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            target = home / "my-plugin"
            target.mkdir()
            plugin = home / "plugins/fsm-ledger"
            plugin.parent.mkdir()
            plugin.symlink_to(target, target_is_directory=True)
            with mock.patch("fsm_ledger.install.Path.home", return_value=home):
                result = install_codex()
            self.assertFalse(result["ok"])
            self.assertTrue(plugin.is_symlink())

    def test_migrates_only_legacy_config_block_with_backup(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[plugins."other"]\nenabled = true\n\n'
                '# fsm-ledger BEGIN — old\n'
                '[marketplaces.fsm-ledger-local]\nsource = "old"\n'
                '# fsm-ledger END\n\n[profiles.default]\n',
                encoding="utf-8",
            )
            with mock.patch("fsm_ledger.install.Path.home", return_value=home):
                result = install_codex()
            text = config.read_text(encoding="utf-8")
            self.assertTrue(result["migrated_legacy_config"])
            self.assertIn('[plugins."other"]', text)
            self.assertIn("[profiles.default]", text)
            self.assertNotIn("fsm-ledger BEGIN", text)
            self.assertTrue(Path(result["legacy_config_backup"]).exists())

    def test_uninstall_removes_only_owned_catalog_entry(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            catalog = home / ".agents" / "plugins" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"plugins": [{"name": "other"}, {"name": "fsm-ledger"}]}), encoding="utf-8")
            with mock.patch("fsm_ledger.install.Path.home", return_value=home), mock.patch(
                "fsm_ledger.install.shutil.which", return_value=None
            ):
                result = uninstall_codex()
            self.assertFalse(result["ok"])
            self.assertEqual(json.loads(catalog.read_text())["plugins"], [{"name": "other"}, {"name": "fsm-ledger"}])
            self.assertEqual(result["codex_remove"]["skipped"], "codex CLI unavailable")

    def test_uninstall_failure_preserves_all_state(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            catalog = home / ".agents" / "plugins" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"plugins": [{"name": "fsm-ledger"}]}), encoding="utf-8")
            config = home / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text("# fsm-ledger BEGIN\nold = true\n# fsm-ledger END\n", encoding="utf-8")
            plugin = home / "plugins/fsm-ledger/.codex-plugin"
            plugin.mkdir(parents=True)
            (plugin / "plugin.json").write_text(json.dumps({"name": "fsm-ledger"}), encoding="utf-8")
            failed = mock.Mock(returncode=1, stdout="", stderr="remove failed")
            with mock.patch("fsm_ledger.install.Path.home", return_value=home), mock.patch(
                "fsm_ledger.install.shutil.which", return_value="/usr/local/bin/codex"
            ), mock.patch("fsm_ledger.install.subprocess.run", return_value=failed):
                result = uninstall_codex()
            self.assertFalse(result["ok"])
            self.assertEqual(catalog.read_text(), '{"plugins": [{"name": "fsm-ledger"}]}')
            self.assertIn("fsm-ledger BEGIN", config.read_text())
            self.assertTrue(plugin.parent.exists())
            self.assertEqual(result["codex_remove"]["stderr"], "remove failed")

    def test_uninstall_removes_owned_plugin_after_codex_remove(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            plugin = home / "plugins/fsm-ledger/.codex-plugin"
            plugin.mkdir(parents=True)
            (plugin / "plugin.json").write_text(json.dumps({"name": "fsm-ledger"}), encoding="utf-8")
            completed = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch("fsm_ledger.install.Path.home", return_value=home), mock.patch(
                "fsm_ledger.install.shutil.which", return_value="/usr/local/bin/codex"
            ), mock.patch("fsm_ledger.install.subprocess.run", return_value=completed) as run:
                result = uninstall_codex()
            run.assert_called_once_with(
                ["/usr/local/bin/codex", "plugin", "remove", "fsm-ledger@local"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertTrue(result["removed_plugin"])
            self.assertFalse((home / "plugins/fsm-ledger").exists())

    def test_uninstall_preserves_plugin_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            target = home / "owned-plugin"
            manifest = target / ".codex-plugin"
            manifest.mkdir(parents=True)
            (manifest / "plugin.json").write_text(json.dumps({"name": "fsm-ledger"}), encoding="utf-8")
            plugin = home / "plugins/fsm-ledger"
            plugin.parent.mkdir()
            plugin.symlink_to(target, target_is_directory=True)
            completed = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch("fsm_ledger.install.Path.home", return_value=home), mock.patch(
                "fsm_ledger.install.shutil.which", return_value="/usr/local/bin/codex"
            ), mock.patch("fsm_ledger.install.subprocess.run", return_value=completed):
                result = uninstall_codex()
            self.assertTrue(result["ok"])
            self.assertTrue(plugin.is_symlink())


if __name__ == "__main__":
    unittest.main()
