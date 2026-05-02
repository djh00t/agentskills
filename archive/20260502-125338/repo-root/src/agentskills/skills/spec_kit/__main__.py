"""Module entrypoint for spec-kit plan and emit CLI commands."""

from __future__ import annotations

from agentskills.skills.spec_kit.script_entrypoints import run_spec_kit_cli

if __name__ == "__main__":
    raise SystemExit(run_spec_kit_cli())
