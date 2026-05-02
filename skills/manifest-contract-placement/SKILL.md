---
name: manifest-contract-placement
description: Verify Kubernetes manifest intent and docs are structurally aligned when service ops, observability, or deployment surface behavior changes.
argument-hint: "[resource-kind-or-service]"
disable-model-invocation: false
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Bash
  - Edit
---

# When to use

Use this when `openai_finance` changes touch deployment manifests, service metadata, or observability wiring and PR review risk includes wording or placement mismatches.

This skill is required for PR themes like #555, where ServiceMonitor-like behavior and scrape annotations were implemented in the wrong Kubernetes object even though string checks passed.

# Inputs / context to gather

1. The modified manifest files and their rendered Kustomize intent.
2. Any docs claiming behavior (Flux README, service README, runbooks) touching manifests.
3. Any tests currently validating the affected manifests.
4. Whether Service vs Deployment/POD annotations, ports, and selectors are contractually coupled.

# Procedure

1. Load each changed manifest and locate the exact target object (`Service`, `Deployment`, `Job`, `CronJob`, etc.) for every operational claim.
2. Replace string-presence checks with YAML-structure assertions for target objects.
3. Assert both sides explicitly when behavior spans multiple objects, e.g.:
  - Service annotations on `Service.metadata.annotations`
  - Runtime pod settings on `Deployment.spec.template.metadata.annotations`
4. Run an object-level diff against a stable peer manifest for the same service family before merging.
5. Update docs statements to match implemented object placement and discovery mechanism.
6. Add one regression test per critical contract (`kind`, annotation location, port value, selector, route/path).

# Hard Gates

- Do not merge if a doc claims Service scraping and only Deployment scraping exists.
- Do not pass manifest review on text-only assertions where placement is semantically important.
- Any new annotation or port setting used for runtime discovery must be asserted at the correct object kind.
- If tests are present for manifest assertions, they must parse YAML into objects and inspect fields, not raw string slices.

# Required Tests

- YAML parser-based assertions for every object-level contract claim changed by the PR.
- Paired doc + manifest diff test where a claim is modified (or added) and verified.
- A guard test confirming fallback object behavior (e.g., one object missing expected fields fails hard).

# Scorecard

- `manifest_object_misplacement_count`: cases where expected behavior asserted on wrong Kubernetes object.
- `string_only_manifest_tests_ratio`: string-based manifest tests / total manifest contract tests.
- `doc_manifest_mismatch_count`: doc claims that do not match manifest objects.

Score formula:

```text
score = 100
  - 40 * manifest_object_misplacement_count
  - 20 * doc_manifest_mismatch_count
  - 10 * string_only_manifest_tests_ratio
```

# Self-Assessment

- Which object owns this behavior before and after the change (`Service`, `Deployment`, `Pod`)?
- Which claim is currently validated structurally vs only by text?
- What is the most likely review miss for a one-pass failure?
- Confidence 1-5 for: object placement correctness, doc parity, test clarity.

After review, convert any unexpected placement miss into a mandatory assertion pattern.

# User Feedback

- Ask after merge: `Did this change make placement and manifest behavior easier to verify on first review? (1-5)`.
- If score is below 4, add a one-line YAML-path assertion for that miss.
