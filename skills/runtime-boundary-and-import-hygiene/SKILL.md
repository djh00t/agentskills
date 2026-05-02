---
name: runtime-boundary-and-import-hygiene
description: Prevent runtime and import-time regressions in stateful or optional-dependency code paths before runtime, startup, and CI hit them.
argument-hint: "[module-or-service]"
disable-model-invocation: false
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Bash
  - Edit
---

# When to use

Use this when service code changes touch startup, repository initialization, global mutable state, thread-sensitive runtime behavior, or optional dependency test assumptions.

This is tied to PR #559 where import-time DB calls, mutable module state, and dependency-gated tests caused CI and runtime risks.

# Inputs / context to gather

1. All changed module imports and top-level side effects in the PR.
2. Existing dependency assumptions (`sqlalchemy`, `fastapi`, etc.).
3. State mutations in route handlers or module globals.
4. Existing tests that exercise startup/import boundaries.

# Procedure

1. Audit module-level code for side effects and move DB schema/session setup from import to explicit initialization paths.
2. For import-once or module-global state, replace with explicit request-scoped or service-scoped state unless intentionally single-thread-scope with guardrails.
3. Require deterministic timestamps to be passed through from source data, not recomputed unless explicitly intended.
4. Move optional dependency `importorskip` calls inside test functions after import guard statements are set.
5. Add tests for:
  - import without full optional dependency stack
  - concurrent mutation paths (or explicit lock around mutable state)
  - startup without external DB availability

# Hard Gates

- No repository or schema initialization in module import for runtime services.
- Any mutable module state used across requests must either be read-only or guarded for concurrency.
- Timestamp fields representing source events must not be overwritten by runtime `now()` defaults.
- Optional dependency tests must be import-safe and avoid failing lint/static checks.

# Scorecard

- `import_side_effect_findings`: import-time side effects fixed or introduced.
- `thread_safety_gaps`: mutable state paths without guard/serialization.
- `optional_dependency_failure_count`: optional dependency tests that need import-time ordering.
- `timestamp_overwrite_occurrences`: runtime timestamp fields replacing source timestamps.

Score formula:

```text
score = 100
  - 30 * import_side_effect_findings
  - 25 * thread_safety_gaps
  - 20 * optional_dependency_failure_count
  - 20 * timestamp_overwrite_occurrences
```

# Self-Assessment

- Which side effects still live at import time?
- Which state must remain stable under parallel requests?
- Which timestamps are authoritative from feed/input vs derived metadata?
- Confidence 1-5 for concurrency safety, startup safety, and dependency safety.

After every PR review, add any missed runtime boundary regression comment as a new preflight checklist item.

# User Feedback

- Ask after merge: `Did startup and import behavior feel predictable under CI and local dev dependency drift? (1-5)`.
- If score is below 4, promote the miss into a pre-merge import/runtime checklist item.
