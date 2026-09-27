# fsm-ledger OpenCode harness (phase-2 stub)

`plugin.mjs` is a minimal placeholder. `install --harnesses opencode` writes
`~/.config/opencode/fsm-ledger.ENABLE.txt` with the path to add to the `plugin`
array — it does **not** rewrite `opencode.jsonc` (JSONC comments).

When OpenCode's `message.updated` hook surface is confirmed, extend `plugin.mjs`
to append usage the same way as the Pi extension.
