# fsm-ledger Claude harness

Stop hook merges into `~/.claude/settings.json` under `hooks.Stop` without removing
existing `PreToolUse` entries. Marker key: `"fsm-ledger": true`.

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger install --harnesses claude
```

Parses stdin Stop payload and optional `transcript_path` JSONL; dedupes by message UUID.
Transcript formats vary across Claude Code versions — best-effort / phase-1 fragile.
