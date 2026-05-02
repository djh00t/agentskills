# Spec-Kit Workflow Map

This flow is derived from upstream `spec-kit` scripts/templates and describes the
command progression from project initiation through delivery.

```mermaid
flowchart TD
  A[specify init] --> B[Template extracted into project]
  B --> C[Constitution seeded if missing]
  C --> D["/speckit.constitution"]
  D --> E["/speckit.specify"]
  E --> E1[create-new-feature.sh\ncreates numbered branch + specs/<branch>/spec.md]
  E1 --> E2{Spec quality pass?}
  E2 -- No --> E3[Revise spec / resolve up to 3 clarifications]
  E3 --> E2
  E2 -- Yes --> F{Run structured clarify?}
  F -- Yes --> G["/speckit.clarify\ninteractive Q&A writes back to spec"]
  F -- No --> H["/speckit.plan"]
  G --> H
  H --> H1[setup-plan.sh creates plan.md]
  H1 --> H1a[update-agent-context.sh updates agent context]
  H1a --> H2[Generate research/data-model/contracts/quickstart]
  H2 --> I["/speckit.tasks"]
  I --> I1[tasks.md by setup/foundational/user story/polish]
  I1 --> J{"Optional /speckit.analyze?"}
  J -- Yes --> J1[Consistency report + deterministic auto-fix pass]
  J -- No --> K{Issue handoff needed?}
  J1 --> K
  K -- Yes --> K1["/speckit.taskstoissues"]
  K -- No --> L["/speckit.implement"]
  K1 --> L
  L --> L1{Checklist files complete?}
  L1 -- No --> L2[Prompt user to proceed or stop]
  L2 --> L3{User proceeds?}
  L3 -- No --> Z[Stop]
  L3 -- Yes --> M[Execute tasks, mark done in tasks.md]
  L1 -- Yes --> M
  M --> N[Final delivery increment]

  E1 --> X{New feature vs behavior change}
  X -- New feature --> X1[Create new numbered feature branch/spec]
  X -- Behavior change --> X2[Reuse existing feature prefix context]
```

## Notes

- Upstream explicitly enforces a numbered feature branch/spec creation path.
- Behavior changes are supported operationally by reusing existing prefix
  context, but this is policy-driven and not a separate hard-coded command path.
- This repository's skill runs an "upstream-plus" flow: it follows the same
  script progression and adds deterministic analyze-and-fix behavior to reduce
  manual cleanup before issue handoff.
