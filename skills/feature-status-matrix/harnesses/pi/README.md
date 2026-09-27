# fsm-ledger Pi harness

Pi package with a TypeScript extension on `message_end` that shells out to:

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger append --harness pi --render
```

Install:

```bash
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger install --harnesses pi
# or: pi install ~/.agents/skills/feature-status-matrix/harnesses/pi
```

Adds the package path to `~/.pi/agent/settings.json` `packages` array.
