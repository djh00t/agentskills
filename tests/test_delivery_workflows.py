"""Execute the local delivery feature against isolated real repositories."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'AGENTS.md', 'README.md', 'Makefile', 'config.toml',
    'scripts/check_instructions.py', 'scripts/delivery_bundle.py',
    'skills/conventional-commit-helper/SKILL.md',
    'skills/commit-helper/SKILL.md', 'skills/pr-helper/SKILL.md',
)


class DeliveryScenarios(unittest.TestCase):
    """Run scenario steps against a fresh fixture for each workflow."""

    def setUp(self) -> None:
        """Copy only the delivery surface; never mutate the working checkout."""
        self.temp = tempfile.TemporaryDirectory(prefix='delivery-bdd-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        for name in FILES:
            source = ROOT / name
            if source.exists():
                target = self.repo / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        self.run_command('git', 'init', '-q')
        self.run_command('git', 'add', '.')

    def run_command(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Capture actual command output for actionable assertions."""
        return subprocess.run(args, cwd=self.repo, text=True, capture_output=True)

    def successful_make(self, target: str, *args: str) -> None:
        """Require the real target to succeed."""
        result = self.run_command('make', target, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def staged_whitespace(self) -> None:
        """Given staged bad whitespace, check must reject it."""
        (self.repo / 'README.md').write_text('bad whitespace   \n')
        self.run_command('git', 'add', 'README.md')
        result = self.run_command('make', 'check')
        self.assertNotEqual(result.returncode, 0, 'staged whitespace escaped check')
        self.assertIn('trailing whitespace', result.stdout + result.stderr)

    def unstaged_whitespace(self) -> None:
        """Given unstaged bad whitespace, check must reject it."""
        (self.repo / 'README.md').write_text('bad whitespace   \n')
        result = self.run_command('make', 'check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('trailing whitespace', result.stdout + result.stderr)

    def install_environment(self) -> None:
        """Install must produce an executable local validation environment."""
        self.successful_make('install')
        result = self.run_command('.venv/bin/python', 'scripts/check_instructions.py')
        self.assertEqual(result.returncode, 0, result.stderr)

    def build_bundle(self) -> None:
        """Build must be reproducible, portable, and exclude local settings."""
        (self.repo / '.env').write_text('fixture-only\n')
        self.successful_make('build')
        bundle = self.repo / 'dist/delivery-policy.zip'
        first = bundle.read_bytes()
        self.successful_make('build')
        self.assertEqual(first, bundle.read_bytes())
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            for name in FILES:
                if name.startswith('skills/'):
                    self.assertIn(name, names)
            self.assertNotIn('config.toml', names)
            self.assertNotIn('.env', names)
            for name in names:
                self.assertEqual(archive.read(name), (self.repo / name).read_bytes())

    def missing_destination(self) -> None:
        """Publish must refuse a missing destination without even building."""
        result = self.run_command('make', 'publish', 'PUBLISH_DIR=')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PUBLISH_DIR', result.stdout + result.stderr)
        self.assertFalse((self.repo / 'dist').exists())

    def local_publication(self) -> None:
        """Explicit local publication must copy the checked bundle exactly."""
        destination = Path(self.temp.name) / 'published'
        self.successful_make('publish', f'PUBLISH_DIR={destination}')
        self.assertEqual(
            (destination / 'delivery-policy.zip').read_bytes(),
            (self.repo / 'dist/delivery-policy.zip').read_bytes(),
        )

    def safe_clean(self) -> None:
        """Clean must remove only known outputs and preserve local config."""
        for name in ('.venv', 'dist'):
            (self.repo / name).mkdir()
            (self.repo / name / 'generated').write_text('generated\n')
        (self.repo / '.env').write_text('fixture-only\n')
        before = (self.repo / 'config.toml').read_bytes()
        self.successful_make('clean')
        self.assertFalse((self.repo / '.venv').exists())
        self.assertFalse((self.repo / 'dist').exists())
        self.assertEqual((self.repo / '.env').read_text(), 'fixture-only\n')
        self.assertEqual((self.repo / 'config.toml').read_bytes(), before)

    def missing_codex_gate(self) -> None:
        """Deleting a mandatory gate must fail the real instruction check."""
        path = self.repo / 'skills/pr-helper/SKILL.md'
        path.write_text(path.read_text().replace('Codex GitHub review', 'review'))
        result = self.run_command('make', 'check')
        self.assertNotEqual(result.returncode, 0, 'missing Codex gate accepted')

    def missing_human_rule(self) -> None:
        """Deleting human-only main protection must fail instruction checks."""
        path = self.repo / 'skills/pr-helper/SKILL.md'
        path.write_text(path.read_text().replace('human-only', 'automatic'))
        result = self.run_command('make', 'check')
        self.assertNotEqual(result.returncode, 0, 'missing human-only rule accepted')

    def mismatched_types(self) -> None:
        """Branch types must continue matching the canonical commit whitelist."""
        path = self.repo / 'skills/pr-helper/SKILL.md'
        path.write_text(path.read_text().replace(', `revert`', ''))
        result = self.run_command('make', 'check')
        self.assertNotEqual(result.returncode, 0, 'mismatched branch types accepted')


SCENARIOS = {
    'Reject a missing Codex merge gate': 'missing_codex_gate',
    'Reject a missing human-only main rule': 'missing_human_rule',
    'Reject a mismatched branch type contract': 'mismatched_types',
    'Reject staged whitespace': 'staged_whitespace',
    'Reject unstaged whitespace': 'unstaged_whitespace',
    'Install the local validation environment': 'install_environment',
    'Build a portable delivery bundle': 'build_bundle',
    'Require an explicit publication destination': 'missing_destination',
    'Publish to a local destination': 'local_publication',
    'Clean generated files without deleting local configuration': 'safe_clean',
}


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite,
               pattern: str | None) -> unittest.TestSuite:
    """Bind every declared Gherkin scenario to executable acceptance steps."""
    feature = (ROOT / 'tests/features/delivery.feature').read_text()
    names = [line.strip().removeprefix('Scenario: ') for line in feature.splitlines()
             if line.strip().startswith('Scenario: ')]
    if set(names) != set(SCENARIOS) or len(names) != len(SCENARIOS):
        raise ValueError('Feature scenarios must match executable step bindings')
    return unittest.TestSuite(DeliveryScenarios(SCENARIOS[name]) for name in names)
