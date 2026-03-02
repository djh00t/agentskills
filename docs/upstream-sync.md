# Upstream Sync

This project consumes `github/spec-kit` via the upstream `specify` CLI to avoid
workflow drift.

## Install CLI

```bash
uv tool install --force specify-cli --from git+https://github.com/github/spec-kit.git
specify --help
```

## Update CLI

```bash
uv tool install --force specify-cli --from git+https://github.com/github/spec-kit.git
specify --help
```

## Validation After Update

1. Run `make check`.
2. Verify deterministic orchestration tests still pass.
3. Verify no local wrappers invent process stages or templates.
