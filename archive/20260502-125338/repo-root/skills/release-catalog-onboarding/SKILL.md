---
name: release-catalog-onboarding
description: Add or repair an `openai_finance` service in the release catalog when commit scopes, service metadata, or release automation validation are failing.
argument-hint: "[service-path-or-name]"
disable-model-invocation: false
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Bash
  - Edit
---

# When to use

Use this when `openai_finance` work touches a new or changed service and any of these cues appear:

- commit scope validation mentions `deploy/services.yaml`
- `service_release_plan.py validate-commits` fails
- `tests/unit/test_service_release_catalog.py` fails
- a PR review says the service is not fully onboarded for release

Do not use this for generic CI failures unrelated to service catalog metadata.

This skill exists because PR #559 showed the same onboarding work succeeded on feature code but failed release checks until catalog metadata, companion artifacts, and catalog tests were reconciled. The objective is first-pass service onboarding: one PR should include metadata + artifacts + tests and pass scope validation without follow-up rework.

# Inputs / context to gather

1. The service path and intended Conventional Commit scope.
2. The current `deploy/services.yaml` entry, if any.
3. Companion files already present under the service directory.
4. Whether workflow job names or required checks changed as part of the same work.

# Procedure

1. Inspect `deploy/services.yaml` for the existing service entry and approved scopes.
2. Check whether the service has the usual companion artifacts the repo expects:
  - `Dockerfile`
  - `CHANGELOG.md`
  - `flux/app.yaml`
  - any release metadata fields referenced by nearby catalog entries
3. Update the catalog entry and the companion files together; do not add a scope in isolation.
4. Search `tests/unit/test_service_release_catalog.py` and any nearby catalog tests for hardcoded service lists or expected scopes, then update them to match the catalog change.
5. Validate commit scopes with:

```bash
python3 .github/scripts/service_release_plan.py validate-commits \
  --catalog deploy/services.yaml \
  --base-sha "$(git merge-base origin/main HEAD)" \
  --head-sha HEAD
```

6. Run the repo gate:

```bash
make check
```

7. If workflow jobs or required checks changed, hand off to `skills/workflow-contract-sync/SKILL.md` before finishing.

# Hard Gates

- No new or changed service may be merged until commit scope validation and catalog test checks are green.
- Never add a new scope until companion artifacts are present in service directory (`Dockerfile`, `CHANGELOG.md`, `flux/app.yaml`).
- Update catalog-driven tests when any service is added/renamed/retired.
- Do not close the task if `make check` reveals catalog/commit-scope drift.

# Evidence-Driven Evidence

- PR #559 `deploy/services.yaml` mismatch and missing metadata caused convention-scope failures.
- PR #559 follow-up catalog failure came from `tests/unit/test_service_release_catalog.py` hardcoded service lists.
- Service onboarding in this repo commonly also requires `flux_reference_paths` and activation metadata parity.

# Required Tests

- `python3 .github/scripts/service_release_plan.py validate-commits --catalog deploy/services.yaml --base-sha ... --head-sha ...` passes for the PR head and merge-base.
- `make check` passes after onboarding changes.
- Catalog expectation test suite reflects the same service set as `deploy/services.yaml`.
- Any changed/added commit scope appears in `deploy/services.yaml` and no unapproved scope IDs are introduced.

# Scorecard

- `catalog_first_pass_success`: services onboarded without follow-up commit due to catalog or scope failure / total catalog-facing service changes.
- `missing_artifact_rate`: required artifact files missing from cataloged services / services touched in PR.
- `catalog_test_drift_count`: hardcoded service expectations not updated before final merge.
- `scope_validation_failures`: number of `validate-commits` failures for a PR.

Score formula:

```text
score = 100
  - 30 * (1 - catalog_first_pass_success)
  - 20 * catalog_test_drift_count
  - 20 * scope_validation_failures
  - 10 * missing_artifact_rate
```

# Self-Assessment

- What is the intended catalog scope and which existing neighboring service should be mirrored?
- Which required artifact is most likely still missing before merge?
- What tests could pass locally but fail once the PR crosses into release tooling?
- Confidence 1-5 on: `onboarding completeness`, `test completeness`, `scope correctness`.

After merge, compare predicted misses to follow-up review comments. Any repeated miss becomes a new required step in this skill.

# User Feedback

- Ask one question after merge: `Did this service onboarding pass `make check` without a second pass for catalog/scope? (1-5)`.
- If the answer is below 4, capture the exact gap and add it as a new gate.

# Efficiency plan

- Read one existing nearby service entry first and mirror its shape instead of inferring the schema from scratch.
- Search for the candidate scope string in `deploy/services.yaml` and `tests/unit/test_service_release_catalog.py` before editing.
- Stop expanding the fix once `validate-commits` and `make check` are both green; avoid unrelated cleanup.

# Pitfalls and fixes

- Symptom: commit validation rejects the scope.
  Likely cause: the scope is not present or not correctly modeled in `deploy/services.yaml`.
  Fix: add or repair the catalog entry first, then rerun `validate-commits`.

- Symptom: catalog/unit tests fail after adding the service.
  Likely cause: hardcoded service lists or expected sets were not updated.
  Fix: update the tests alongside the catalog change.

- Symptom: the service looks onboarded locally but release automation still breaks in review.
  Likely cause: companion artifacts like `Dockerfile`, `CHANGELOG.md`, or `flux/app.yaml` are missing.
  Fix: compare against an existing released service and add the missing artifacts.

# Verification checklist

- `deploy/services.yaml` contains the intended service/scope metadata.
- Required companion artifacts exist in the service directory.
- `python3 .github/scripts/service_release_plan.py validate-commits ...` passes.
- `make check` passes.
- Any touched catalog tests now reflect the final service list and scope behavior.
