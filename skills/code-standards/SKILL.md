---
name: code-standards
description: Enforce Python code style, ASCII-safe text, docstrings, and comment rules.
compatibility: agents
metadata:
  language: python
  scope: style
---
## What I do
- Enforce Python style and structure for this repo.
- Require docstrings for public modules, classes, and functions.
- Require comments for non-obvious logic and complex branches.
- Enforce ASCII-safe punctuation (no smart quotes, no ellipsis, no em dash substitutions).
- Allow emoji only in comments or string literals when explicitly appropriate.

## When to use me
- Use on every coding task in this repo.
- Use before writing or modifying Python code.

## Inputs I need
- Target file paths and function/class names you will touch.

## Steps
1) Preserve the existing project layout under `src/mission_control` and `tests`.
2) Keep imports grouped and ordered: standard library, third-party, local.
3) Prefer `from __future__ import annotations` for new Python modules.
4) Add type hints to public APIs and non-trivial locals.
5) Keep formatting consistent with black-compatible style: 4 spaces, line length about 88.
6) Use ASCII punctuation in code and comments; avoid smart quotes and similar substitutions.
7) Ensure docstrings exist for public modules, classes, and functions.
8) Add comments for tricky logic, decisions, and policy rules.

## Acceptance checks
- Docstrings added where required.
- Comments added for non-obvious behavior.
- Imports are grouped and unused imports removed.
- No Unicode punctuation substitutions are introduced.

## Failure modes and remediation
- Missing docstrings: add short, precise docstrings.
- Unclear logic: add a comment that explains the intent, not the obvious.
- Unicode punctuation detected: replace with ASCII equivalents.
