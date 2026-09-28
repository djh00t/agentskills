# fsm-ledger Codex harness

Codex only loads hooks via plugins. This directory is a Codex plugin:

- `.codex-plugin/hooks.json` — Stop + SessionEnd
- `.codex-plugin/fsm-ledger-hook` — queue stdin JSON; async Stop drains the queue and renders

## Enable

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger install --harnesses codex
codex plugin add fsm-ledger@local
```

The installer merges an entry into `~/.agents/plugins/marketplace.json` and
copies the plugin to `~/plugins/fsm-ledger`. The Codex command installs it from
the personal `local` marketplace. Restart Codex Desktop after installation.

**Trust reminder:** Enabling a plugin does not trust its hooks. Review and accept
the Stop and SessionEnd hooks in Codex's trust prompt. Existing brute / ponytail /
context-mode hooks are not modified.

## Verification

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m unittest discover \
  -s ~/.agents/skills/feature-status-matrix/tests
codex plugin list
```

Stop runs in Codex's background hook mode. SessionEnd drains synchronously.
Both read per-response `token_usage_record` rows from the session rollout.
Pending events are stored under `~/.agents/status-matrices/_hook_pending/` and
survive a cancelled background hook or unreadable rollout. After a real Stop event, inspect
`~/.agents/status-matrices/agent-brain/usage.jsonl`.
Do not append fixture events to the live ledger.
