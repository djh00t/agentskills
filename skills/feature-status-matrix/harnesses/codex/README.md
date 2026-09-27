# fsm-ledger Codex harness

Codex only loads hooks via plugins. This directory is a Codex plugin:

- `.codex-plugin/hooks.json` — Stop + SessionEnd
- `.codex-plugin/fsm-ledger-hook` — queues stdin JSON; async Stop drains and renders

## Enable

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger install --harnesses codex
```

That copies this plugin into `harnesses/codex-marketplace/plugins/fsm-ledger/` and appends a
marked `[marketplaces.fsm-ledger-local]` + `[plugins."fsm-ledger@fsm-ledger-local"]` block to
`~/.codex/config.toml` (backup: `config.toml.bak-fsm-YYYYMMDD`).

**Trust reminder:** Codex will prompt to trust the new hooks. Accept them. Existing
brute / ponytail / context-mode hooks are not modified.

Stop runs asynchronously in Codex. SessionEnd always runs synchronously, so
it only queues its payload. The next Stop drains pending events from
`~/.agents/status-matrices/_hook_pending/`. The hook exits 0 without output
after accepting the event.

## Manual test

```bash
echo '{"usage":{"input_tokens":10,"output_tokens":5},"model":"gpt-6-luna","cwd":"/Users/djh/work/src/github.com_local/djh00t/agent-brain"}' \
  | ~/.agents/skills/feature-status-matrix/harnesses/codex/.codex-plugin/fsm-ledger-hook stop
```
