---
name: polymarket-repo-map
description: Maintain `polymarket/docs/INDEX.md`, `polymarket/docs/CODEMAP.md`, and `polymarket/docs/repo_map.json` so humans and Codex can quickly orient, find ownership, and understand the current vs target layout.
metadata:
  short-description: Regenerate/update the Polymarket repo map docs
---

# Polymarket Repo Map Skill

Use this skill when:

- Adding/removing/moving files under `polymarket/src/polymarket/` or `polymarket/tests/`
- Updating Polymarket docs that affect navigation/ownership
- An agent needs a fast, accurate inventory of modules/entrypoints

## Sources of Truth

- Requirements/constraints: `polymarket/docs/spec.md`
- Target end-state layout: `polymarket/docs/plan.md` (“Target Repository Structure”)
- DuckDB contract: `polymarket/docs/schemas.md`
- Execution workflow: `polymarket/docs/workflows.md`

## Workflow (Keep It Deterministic)

1) Refresh the auto-generated inventory:
   - From repo root (no venv required):
     - `python polymarket/src/polymarket/tools/repo_map.py --write --project-root polymarket`
2) Confirm `polymarket/docs/CODEMAP.md` still describes the correct module responsibilities and boundaries.
   - Only the inventory block should change automatically.
3) If navigation changed, update the curated index:
   - `polymarket/docs/INDEX.md`
4) Sanity-check:
   - `python polymarket/src/polymarket/tools/repo_map.py --check --project-root polymarket`

## Notes on AST / Indexing

- The generator uses Python’s `ast` module to build a lightweight symbol index (`polymarket/docs/repo_map.json`).
- Avoid committing full AST dumps: they are large, noisy, and rarely help more than a symbol/index view.
- If deeper structure is needed, extend the generator to emit (a) imports/dependency edges, or (b) per-function signatures,
  rather than whole ASTs.
