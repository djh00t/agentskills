# Agent Contract

## Required Inputs

- `spec_title`: short human-provided title.
- `spec_body`: source specification text.
- `tasks`: optional task seeds with dependencies.

## Required Checkpoints

1. Clarification checkpoint for missing or ambiguous required data.
2. Approval checkpoint before issue creation or update.

## Required Outputs

- Deterministic execution plan.
- Dependency-aware ordering with parallelizable groups.
- Issue drafts, and optionally published GitHub issue references.
