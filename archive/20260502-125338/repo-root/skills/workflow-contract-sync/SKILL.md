---
name: workflow-contract-sync
description: Update `openai_finance` workflow contract files and validation when GitHub Actions triggers, job names, required checks, or summary behavior change.
argument-hint: "[workflow-or-check-name]"
disable-model-invocation: false
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Bash
  - Edit
---

# When to use

Use this when `openai_finance` workflow edits change any of the following:

- workflow triggers or path filters
- job names
- required checks
- GitHub step-summary behavior
- planner vs matrix routing for CI/service-image workflows

Do not use it for runtime service bugs or release-catalog onboarding unless workflow surfaces changed too.

# Inputs / context to gather

1. The workflow files being edited under `.github/workflows/`.
2. The expected stable required check name.
3. The current `deploy/ci_contract.json` and `docs/runbooks/ci-workflow-inventory.md`.
4. Any tests that lock the workflow contract.

# Procedure

1. Inspect the touched workflow YAML and identify whether the stable required check should remain `quality-gate`.
2. Update the workflow files first, keeping app-specific routing or path filters explicit.
3. Regenerate and verify the workflow contract:

```bash
uv run python scripts/audit_ci_contract.py --write
uv run python scripts/audit_ci_contract.py --check
```

4. Update `deploy/ci_contract.json` and `docs/runbooks/ci-workflow-inventory.md` if the audit step or workflow diff shows drift.
5. If CI or service-image summaries are part of the change, make sure they append to `GITHUB_STEP_SUMMARY` instead of truncating it.
6. Run focused workflow validation:

```bash
actionlint .github/workflows/*.yml
make check
```

7. If the workflow change also touched a service release scope or onboarding metadata, run `skills/release-catalog-onboarding/SKILL.md`.

# Efficiency plan

- Start from the current required-check contract instead of re-deriving naming from branch protection.
- Search for the affected job name in `deploy/ci_contract.json`, `docs/runbooks/ci-workflow-inventory.md`, and tests before editing.
- Use diagnostics for summary-only helpers; do not let a `git diff` lookup become the reason the planner job fails.

# Pitfalls and fixes

- Symptom: workflow YAML is updated but contract files still fail validation.
  Likely cause: `deploy/ci_contract.json` or workflow inventory docs were not regenerated.
  Fix: run `audit_ci_contract.py --write` and `--check`, then commit the synchronized artifacts.

- Symptom: later step-summary content disappears.
  Likely cause: a helper used overwrite semantics on `GITHUB_STEP_SUMMARY`.
  Fix: append instead of truncating.

- Symptom: CI now runs too broadly after an app-specific change.
  Likely cause: path filters or planner dependency fan-out were not updated together.
  Fix: keep routing in the planner/path-filter layer and preserve `quality-gate` as the stable required aggregate check.

# Verification checklist

- Workflow YAML matches the intended trigger/job/check behavior.
- `uv run python scripts/audit_ci_contract.py --check` passes.
- `deploy/ci_contract.json` and `docs/runbooks/ci-workflow-inventory.md` match the workflow surface.
- Step-summary helpers append to `GITHUB_STEP_SUMMARY`.
- `actionlint` and `make check` pass.
