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

## Spec-Kit Structure

- Canonical runtime behavior lives in `src/agentskills/skills/spec_kit`.
- `skills/spec-kit` is the authoritative skill asset directory
	(metadata/schema/examples/scripts docs).
- `skills/spec-kit/scripts/*.py` are thin wrappers that parse CLI arguments
	and delegate logic to `src` modules.
- `src/agentskills/skills/spec_kit/script_entrypoints.py` is the canonical
	script CLI entrypoint and delegates to shared runtime modules.
- Deterministic planning and issue emission logic are shared library modules,
	preventing duplicate implementations across scripts and runtime.

## Deterministic Execution

- Validate input payloads before processing.
- Build directed acyclic graphs from declared dependencies.
- Produce stable topological order and parallel groups.
- Require human approval before issue publication.
