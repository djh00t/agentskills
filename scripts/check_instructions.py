"""Validate the instruction collection without third-party dependencies."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPERS = (
    'conventional-commit-helper',
    'commit-helper',
    'pr-helper',
)


class InstructionContracts(unittest.TestCase):
    """Check parseability and cross-file references used during delivery."""

    def test_tracked_config_parses(self) -> None:
        """The shared configuration remains valid TOML."""
        with (ROOT / 'config.toml').open('rb') as source:
            tomllib.load(source)

    def test_helper_metadata(self) -> None:
        """Each delivery entry point has discoverable frontmatter."""
        for name in HELPERS:
            with self.subTest(helper=name):
                text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
                self.assertTrue(text.startswith('---\n'))
                self.assertIn(f'\nname: {name}\n', text)
                self.assertRegex(text, r'\ndescription: .+\n')
                self.assertGreaterEqual(text.count('---'), 2)

    def test_commit_entry_point_resolves(self) -> None:
        """The short helper name resolves to the canonical commit contract."""
        folder = ROOT / 'skills' / 'commit-helper'
        text = (folder / 'SKILL.md').read_text()
        links = re.findall(r'\]\(([^)]+)\)', text)
        self.assertTrue(links)
        for link in links:
            self.assertTrue((folder / link).is_file(), link)


if __name__ == '__main__':
    unittest.main(verbosity=2)
