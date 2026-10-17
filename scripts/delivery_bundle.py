"""Build and copy the delivery policy bundle using local files only."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'dist/delivery-policy.zip'
SOURCES = (
    'AGENTS.md',
    'skills/commit-helper/SKILL.md',
    'skills/conventional-commit-helper/SKILL.md',
    'skills/pr-helper/SKILL.md',
)


def destination() -> Path:
    """Require an explicit filesystem destination before any build or copy."""
    value = os.environ.get('PUBLISH_DIR', '')
    if not value.strip() or '://' in value:
        raise ValueError('Set PUBLISH_DIR to an explicit local directory')
    target = Path(value).expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise ValueError('PUBLISH_DIR must name a directory')
    if target == BUNDLE.parent.resolve():
        raise ValueError('PUBLISH_DIR must differ from the build directory')
    return target


def build() -> None:
    """Write a reproducible policy-only archive, excluding local config."""
    BUNDLE.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(BUNDLE, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCES:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (ROOT / name).read_bytes())
    print(BUNDLE)


def publish() -> None:
    """Copy an already built archive to the explicitly selected local path."""
    target = destination()
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BUNDLE, target / BUNDLE.name)
    print(target / BUNDLE.name)


def clean() -> None:
    """Remove only known generated directories; preserve all local config."""
    for name in ('.venv', 'dist'):
        path = ROOT / name
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def main() -> None:
    """Dispatch the explicit local build operation."""
    commands = {
        'build': build,
        'publish': publish,
        'clean': clean,
        'validate-destination': destination,
    }
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit('Use build, publish, clean, or validate-destination')
    try:
        commands[sys.argv[1]]()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error


if __name__ == '__main__':
    main()
