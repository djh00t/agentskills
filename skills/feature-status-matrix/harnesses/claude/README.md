# fsm-ledger Claude harness

Stop hook merges into `~/.claude/settings.json` under `hooks.Stop` without removing
existing `PreToolUse` entries. Marker key: `"fsm-ledger": true`.

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger install --harnesses claude
```

Scans `transcript_path` JSONL at Stop and keeps the final usage snapshot for
each assistant API message ID. It records cache reads and writes separately;
total input includes both. A live Claude run is needed to verify the installed
transcript format.
