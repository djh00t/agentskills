# AGENTS for spec-kit

This file narrows the root agent policy for the `spec-kit` skill.

## Required Behavior

1. Run only documented Spec-Kit stages.
2. Ask clarification questions when spec intent is not explicit.
3. Stop and request explicit approval before issue publication.
4. Preserve deterministic output ordering.

## Required Inputs

- spec title
- spec body
- optional initial tasks and dependencies

## Required Outputs

- deterministic execution plan
- parallelizable batches
- issue drafts or created issue references
