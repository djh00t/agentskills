---
name: conventional-commit-helper
description: Draft and validate deterministic, scoped Conventional Commit messages for git commits. Use when preparing commits, splitting changes, or enforcing one-file one-change commit hygiene with strict header and footer rules.
compatibility: agents
metadata:
  scope_policy: function-class-file-feature
  commit_style: conventional-commits-1.0.0
---

## What I do

- Enforce strict Conventional Commit headers.
- Enforce scoped commit messages with deterministic normalization.
- Enforce one file per commit and one logical change per commit as the default workflow.
- Produce multiline commit bodies with concise, structured detail.
- Add traceability footers referencing GitHub issues, user stories, or task IDs when available.

## When to use me

- Use before every git commit.
- Use when splitting staged changes into clean atomic commits.
- Use when preparing machine-readable commit history for release notes and analytics.

## Required format contract

### 1) Header

Header must be exactly:

`type(scope): subject`

Rules:

- `type` must be one of:
  - `feat`
  - `fix`
  - `docs`
  - `style`
  - `refactor`
  - `perf`
  - `test`
  - `build`
  - `ci`
  - `chore`
  - `revert`
- `type` must be lowercase.
- `scope` is required.
- `scope` must be lowercase kebab-case ASCII (`[a-z0-9-]` only).
- `scope` must not start or end with `-`.
- `scope` must not contain `--`.
- `scope` should be at most 30 characters.
- `subject` must start with lowercase, be imperative style, and end without a period.
- Header length must be <= 72 characters.
- Exactly one space after `:`.
- No emoji or non-ASCII punctuation.

Validation regex (header structure only):

`^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)\([a-z0-9]+(?:-[a-z0-9]+)*\): [a-z][^\r\n.]{0,71}$`

Note: Also enforce the 72-character hard limit separately.

### 2) Scope selection (most specific wins)

Scope precedence is deterministic and must follow this order:

1. function
2. class
3. file name
4. feature

Selection rules:

- If exactly one function is the primary changed unit, use function name.
- Else if exactly one class is the primary changed unit, use class name.
- Else if one file is changed, use file stem.
- Else use feature slug.

Normalization rules:

- Convert CamelCase and snake_case to kebab-case.
- Lowercase all letters.
- Replace separators (`_`, `/`, `.`, whitespace) with `-`.
- Collapse repeated `-` to single `-`.
- Trim leading and trailing `-`.
- ASCII only.

Examples:

- `AgentMemoryJournal` -> `agent-memory-journal`
- `record_interaction` -> `record-interaction`
- `portal_api.py` -> `portal-api`

### 3) Commit body

Commit body must be multiline and bounded to this structure:

1. blank line after header
2. `Why: <one concise sentence>`
3. `Changes:`
4. `- <bullet 1>`
5. `- <bullet 2>` (optional)
6. `- <bullet 3>` (optional)
7. `Impact: <one concise sentence>`

Body rules:

- Keep each line <= 72 characters.
- Use concise, concrete statements.
- Do not include unrelated implementation history.

### 4) Footer block

Footer block is required when references are available.

Footer order is fixed:

1. `Refs: <comma-separated GitHub refs>`
2. `User-Story: <comma-separated IDs>`
3. `Task-ID: <comma-separated IDs>`

Rules:

- Include only keys that have known values.
- Preserve the fixed ordering of included keys.
- If no references are available, omit footer and include:
  - `Traceability: none provided`

## One-file one-change workflow

Default policy:

- One file per commit.
- One logical change per commit.

Flexible exception policy:

- Exceptions are allowed only when changes are technically inseparable.
- If exception is used, include this body line:
  - `Exception: inseparable multi-file change (<reason>)`
- Scope still must follow precedence and normalization rules.

## Step-by-step procedure

1. Inspect staged changes.
2. Count staged files.
3. Identify logical change boundary.
4. If multiple files or mixed changes, split into separate commits.
5. Determine scope with precedence: function > class > file > feature.
6. Select commit `type` from allowed set.
7. Draft header under 72 characters.
8. Draft bounded multiline body.
9. Add ordered footer references when available.
10. Validate against acceptance checks before committing.

## Deterministic commit template

Use this exact template:

```text
type(scope): subject

Why: <one concise sentence>
Changes:
- <concise change bullet>
- <optional concise change bullet>
- <optional concise change bullet>
Impact: <one concise sentence>

Refs: #123, #456
User-Story: US-12
Task-ID: TASK-44
```

If no references are available:

```text
type(scope): subject

Why: <one concise sentence>
Changes:
- <concise change bullet>
Impact: <one concise sentence>
Traceability: none provided
```

## Acceptance checks

- Header matches required format and allowed types.
- Header length <= 72 characters.
- Scope chosen by deterministic precedence.
- Scope normalized to lowercase kebab-case ASCII.
- Subject is imperative-like, lowercase start, no trailing period.
- Body includes `Why`, `Changes`, and `Impact` in fixed order.
- One file and one logical change policy satisfied, or explicit exception noted.
- Footer references included in fixed order when available.

## Failure modes and remediation

- Multiple files staged:
  - Split staging and create separate commits.
- Multiple logical changes in one file:
  - Split edit into separate commits by change intent.
- Missing or invalid scope:
  - Recompute scope using precedence and normalization rules.
- Header too long:
  - Shorten subject first, then shorten scope only if needed.
- References exist but footer missing:
  - Add the appropriate ordered footer lines before commit.
