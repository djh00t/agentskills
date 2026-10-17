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

    def test_branch_types_match_commit_types(self) -> None:
        """Keep work branch types aligned with the actual commit contract."""
        canonical = (ROOT / 'skills/conventional-commit-helper/SKILL.md').read_text()
        header_rules = canonical.split('### 2) Scope selection', 1)[0]
        commit_types = set(re.findall(r'^  - `([a-z]+)`$', header_rules, re.M))
        self.assertEqual(len(commit_types), 11)
        for name in ('AGENTS.md', 'skills/pr-helper/SKILL.md',
                     'skills/conventional-commit-helper/SKILL.md'):
            with self.subTest(file=name):
                text = (ROOT / name).read_text()
                match = re.search(r'Allowed work types.*?(?=\n- Role)', text, re.S)
                self.assertIsNotNone(match, 'missing work branch type contract')
                self.assertEqual(set(re.findall(r'`([a-z]+)`', match[0])), commit_types)

    def test_required_merge_contract(self) -> None:
        """Fail if an instruction surface loses a required merge safeguard."""
        for name in ('AGENTS.md', 'skills/pr-helper/SKILL.md',
                     'skills/conventional-commit-helper/SKILL.md'):
            with self.subTest(file=name):
                text = (ROOT / name).read_text()
                self.assertNotIn(
                    'hand the PR(s) off to the user for merge/approval', text
                )
                # These clauses are a cross-file instruction contract, not an
                # implementation of an agent's runtime authorization logic.
                for clause in (
                    'Wait for every requested reviewer to finish',
                    'all applicable current-head checks',
                    'Immediately before merge, recheck',
                    'Ask humans only for necessary clean release-level merges',
                    'Pending, failed, stale, or unresolved evidence',
                    'Codex GitHub review', 'independent',
                    'adversarial acceptance/integration review pass',
                    'prospective merged result', 'current target',
                    'affected evidence', 'human-only',
                    'source branch name conveys no authority',
                    'Feature PRs must remain free of GitHub Actions',
                    'grants no blanket approval or merge permission',
                ):
                    self.assertIn(clause, text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
