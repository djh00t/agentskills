---
name: feature-status-matrix
description: Use when generating or refreshing a feature/project/roadmap status matrix — a summary-by-Area table plus a detailed per-item matrix with emoji status, percent progress, and (for AI-delivery pipelines) per-item budget vs. actual token/cost spend. Includes a CLI tool, shared fsm-ledger usage capture across Codex/Claude/Pi, and a project-specific state file for tracking what changed between snapshots.
---

# Feature Status Matrix

Produces the standard two-part status report mandated by the global reporting
preferences: a **summary grouped by Area** (emoji status + % progress), followed by a
**detailed matrix grouped under the same Areas**, with emoji status, % progress, and a
next-action/note for every row. For AI-driven delivery pipelines it also shows
**Budget vs. Actual** spend per item, sourced from real per-work-item token/cost
telemetry in `~/.agents/status-matrices/<project>/usage.jsonl` — not invented estimates.

## When to use this skill

- Any time you're asked for a "feature status matrix", "status matrix", "roadmap
  matrix", or similar for a project, pipeline, or set of tracked work items.
- Specifically when the work items come from a `coordination.py`-style claim protocol
  (work-packages.json + `claims/`/`heartbeats/`/`deliveries/` directories) — the bundled
  tool reads that layout directly via `--pack-root`.
- For agent-brain-style matrices with state already on each package, use
  `--packages-json ~/.agents/status-matrices/agent-brain/work-packages.json`.
- When you want spend visibility per item, backed by the shared **fsm-ledger**.

## Reporting modes

| Mode | When | What you get |
|------|------|----------------|
| **manual** | Ad-hoc asks | Agent narrates from matrix file / live render |
| **compact** | Mid-session / “what moved?” | Summary by Area + TOTAL → only the moved area’s detail → `### Delta` |
| **full** | Milestone / snapshot | Summary + every area’s detail tables |

Compact auto-detects the moved area from `status-matrix-state.json` deltas when
`--area` is omitted. Prefer `--area Enrich-S3` when you know the theme.

## Format specification (do not deviate)

1. **Summary first**: one row per Area, with emoji status, % progress (average of its
   items' progress), and Budget/Actual $ rollups, plus a **TOTAL** row.
2. **Detailed matrix second**, grouped under the *same* Area headings used in the
   summary. Every item gets its own row: ID, Name/description, size/wave (or equivalent),
   emoji status, %, Budget, Actual, Delta (`actual - budget`, signed), and a Note.
   Escape Markdown table-breaking pipes and newlines in Name/description values.
3. **Emoji legend** (fixed): `🟢`/`✅` done · `🟡` partial · `🔴` gap · `⚪` not started/blocked
   · `🔵` in progress · `🟣` blocked-for-human · `⚠️` risk.
4. **% progress**: `ACCEPTED=100, DELIVERED=70, IN_PROGRESS=50, CLAIMED=30, REJECTED=40, READY=0, BLOCKED=0`.
5. **Actual cost sums every attempt**, including failed/rejected ones.
6. Budget is a **per-size estimate** (defaults `S=$2, M=$5, L=$15`).
7. **UNALLOCATED** is a valid workPackageId — shown as a synthetic row when present in
   the usage log but not in packages. Subscription/plan usage shows as `plan` in Actual.
8. Missing cost telemetry shows `—`, not measured zero. Pricing-derived cost is
   prefixed `~`; incomplete aggregates are marked partial/unknown. Do not treat
   `~` or `plan` as provider-reported dollars.

## fsm-ledger (shared usage capture)

Package: `~/.agents/skills/feature-status-matrix/fsm_ledger/` (stdlib + PyYAML).

```bash
# Register harnesses (backups: *.bak-fsm-YYYYMMDD)
PYTHONPATH=~/.agents/skills/feature-status-matrix \
  python3 -m fsm_ledger install --harnesses codex,claude,pi

# Codex: install the registered local plugin, restart the app, then review/trust
# its Stop and SessionEnd hooks in Codex's trust prompt.
codex plugin add fsm-ledger@local

# Bind active WP for attribution
python3 -m fsm_ledger bind-wp --project agent-brain --wp AB-033

# Append a usage row (JSON stdin)
echo '{"model":"gpt-6-luna","inputTokens":100,"outputTokens":20,"costTotal":0.01}' \
  | PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger append --harness manual

# Render
PYTHONPATH=~/.agents/skills/feature-status-matrix \
  python3 -m fsm_ledger render --project agent-brain --mode compact --area Enrich-S3

PYTHONPATH=~/.agents/skills/feature-status-matrix \
  python3 -m fsm_ledger render --project agent-brain --mode full

# Smoke (fixture rows labeled fixture-smoke — not real spend)
PYTHONPATH=~/.agents/skills/feature-status-matrix python3 -m fsm_ledger smoke
```

Wrapper: `tools/fsm-ledger` (same CLI).

Attribution order: `FSM_WP`/`FEATURE_WP` → `active-wp.json` → branch/subject heuristic
(`feat(enrich)`, `AB-033`, …) → `UNALLOCATED`.
Project attribution uses configured roots or the Git remote; events from an
unmatched workspace go to `_unattributed/usage.jsonl`, not another project's
matrix. `UNALLOCATED` is a work-package id within a resolved project.

Pricing: prefer provider-reported `costTotal`; else estimate from
`agent-brain/config/inference_pricing.yaml` (never hard-coded). Soft-imports
`pipelines.common.pricing.loader.estimate_cost` when on `PYTHONPATH`.
`billing_mode=subscription` → `costTotal=0` + plan flag.

Harness rows represent individual API responses. `inputTokens` is total input,
including cached reads and cache writes; `cachedInputTokens` and
`cacheWriteInputTokens` retain those components separately. `ts` is the response
timestamp and `model` is the model used. An absent cache-write field means the
source did not report it, not zero. Existing usage rows are not backfilled.

### Pipeline metered() helper

Do **not** commit into agent-brain unless via a separate CloudAgent PR. From any
pipeline with the skill on `PYTHONPATH`:

```python
from fsm_ledger.metered import metered

with metered(model="gpt-6-luna", work_package="AB-033") as m:
    ...
    m.add(input_tokens=100, output_tokens=50)
```

## Render CLI

```bash
# coordination.py pack
python3 tools/render_matrix.py \
  --pack-root ~/work/src/github.com/djh00t/to2 \
  --usage-log /tmp/orch-usage.jsonl \
  --state-file ~/.worktrees/to2-orchestrator/status-matrix-state.json

# agent-brain packages-json (state on each package)
python3 tools/render_matrix.py \
  --packages-json ~/.agents/status-matrices/agent-brain/work-packages.json \
  --usage-log ~/.agents/status-matrices/agent-brain/usage.jsonl \
  --state-file ~/.agents/status-matrices/agent-brain/status-matrix-state.json \
  --out ~/.agents/status-matrices/agent-brain/FEATURE_STATUS_MATRIX.md \
  --mode full

# Compact view to stdout; --out still refreshes the full file on disk
python3 tools/render_matrix.py \
  --packages-json ~/.agents/status-matrices/agent-brain/work-packages.json \
  --usage-log ~/.agents/status-matrices/agent-brain/usage.jsonl \
  --state-file ~/.agents/status-matrices/agent-brain/status-matrix-state.json \
  --out ~/.agents/status-matrices/agent-brain/FEATURE_STATUS_MATRIX.md \
  --mode compact --area Enrich-S3
```

## Tests

```bash
cd ~/.agents/skills/feature-status-matrix
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## Harness notes / phase-2 gaps

- **Codex**: installer registers the plugin in the personal local marketplace;
  `codex plugin add fsm-ledger@local` installs it. Restart Codex and review/trust
  its Stop and SessionEnd hooks. Stop runs asynchronously; SessionEnd drains its
  rollout synchronously. Both read per-response `token_usage_record` entries;
  unreadable rollouts remain queued under `~/.agents/status-matrices/_hook_pending/`.
  Enabling a plugin alone does
  not trust hooks.
  Existing brute/ponytail/context-mode hooks are untouched.
- **Claude**: Stop scans transcript assistant messages and keeps the final usage
  snapshot per API message ID; a live Claude run is still needed to confirm its
  installed transcript format.
- **Pi**: `message_end` extension records the message's usage and timestamp.
- **OpenCode**: phase-2 stub (`harnesses/opencode/`); enable hint file only.

## Extending to other coordination layouts

`compute_coordination_state()` / `load_packages_json()` are the schema-specific
loaders. Anything returning `[{id, theme, wave, size, title, state}, ...]` can be
passed to `render_markdown()`.
