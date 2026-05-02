# Spec-Kit Runbook

## Prerequisites

- Python 3.11+
- `gh` CLI authenticated (`gh auth status`)
- `specify` CLI installed

## Install Upstream Spec-Kit Requirements

1. `bash skills/spec-kit/scripts/install_spec_kit_deps.sh`
2. `specify --help`

The installer script automatically installs `uv` if it is missing.

## High-Level Flow

1. Receive human specification.
2. Validate upstream Spec-Kit CLI entrypoint.
3. Validate and ask clarification questions.
4. Build deterministic dependency-aware plan.
5. Request human approval.
6. Generate issue drafts and publish with `gh` when approved.

## Dry Run

Use dry-run mode first to verify issue payloads without writing to GitHub.

## Publish Safety Controls

- Use repo allowlists when publishing issues.
- Keep audit logging enabled for publish and dry-run emissions.
