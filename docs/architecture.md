# Architecture

## Overview

This monorepo hosts reusable agent skills with deterministic orchestration,
stable contracts, and explicit human checkpoints.

## Layers

- `skills/`: human-facing skill definitions and agent usage documentation.
- `src/agentskills/contracts`: typed schemas and domain models.
- `src/agentskills/planning`: dependency and parallelization planning.
- `src/agentskills/skills`: skill orchestrators and adapters.
- `src/agentskills/integrations`: external system integrations.

## Deterministic Execution

- Validate input payloads before processing.
- Build directed acyclic graphs from declared dependencies.
- Produce stable topological order and parallel groups.
- Require human approval before issue publication.
