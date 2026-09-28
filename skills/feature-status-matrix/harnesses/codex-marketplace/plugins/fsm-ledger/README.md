# fsm-ledger Codex harness

Codex only loads hooks via plugins. This directory is a Codex plugin:

- `.codex-plugin/hooks.json` — Stop + SessionEnd
- `.codex-plugin/fsm-ledger-hook` — queue stdin JSON; async Stop drains the queue and renders

Stop and SessionEnd read per-response `token_usage_record` entries from the
session rollout. SessionEnd drains synchronously. Unreadable rollouts remain
queued in `~/.agents/status-matrices/_hook_pending/` for retry.

## Enable

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger install --harnesses codex
```

The installer registers `fsm-ledger@local` in the personal marketplace and
copies the plugin to `~/plugins/fsm-ledger`. Run `codex plugin add fsm-ledger@local`
and restart Codex.

**Trust reminder:** Codex will prompt to trust the new hooks. Accept them. Existing
brute / ponytail / context-mode hooks are not modified.

## Manual test

```bash
tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m unittest discover \
  -s ~/.agents/skills/feature-status-matrix/tests
```
