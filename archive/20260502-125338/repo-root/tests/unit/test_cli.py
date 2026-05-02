"""Unit tests for agentskills CLI dispatch."""

from __future__ import annotations

import argparse

import pytest

from agentskills import cli


def test_cli_main_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures CLI returns zero when command function succeeds."""

    class DummyParser:
        def parse_args(self) -> argparse.Namespace:
            return argparse.Namespace(func=lambda _args: 0)

    monkeypatch.setattr(cli, "build_parser", lambda: DummyParser())
    assert cli.main() == 0


def test_cli_main_handles_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures CLI converts expected exceptions into non-zero exit."""

    class DummyParser:
        def parse_args(self) -> argparse.Namespace:
            def _raise(_: argparse.Namespace) -> int:
                raise ValueError("bad")

            return argparse.Namespace(func=_raise)

    monkeypatch.setattr(cli, "build_parser", lambda: DummyParser())
    assert cli.main() == 1
