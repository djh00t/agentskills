## Read the following files before starting

@/Users/djh/.codex/AGENTS-RTK.md
@/Users/djh/.codex/AGENTS-CONTEXT-MODE.md

These instructions outline the standard workflow that must be followed when working on my projects.

## Project Setup

- Always include a Makefile with at least the following commands in each project (note: a repo might have multiple projects):
  - `make check`: runs linters, unit, bdd and functional tests and light quality gates.
  - `make quality-gates`: deep detailed code quality gates that run all unit, bdd, integration etc tests, linters and other code inspections. This will also be run by CI tools when code is pushed.
  - `make install`: installs the application and its dependencies into a .venv or language equivalent.
  - `make clean`: removes all temporary, cache and other project generated files and virtual environments that should not be pushed to git. NOTE: do not delete .env files and other local configurations that might be ignored by .gitignore
  - `make build`: build the project into a format that it can be published.
  - `make publish`: publish the build into the appropriate repository (pypy, docker hub, ghcr.io etc)
- Every feature in every repo must have BDD feature coverage, not just unit coverage.
- Add and maintain `.feature` files and executable BDD scenarios for all user-visible or behavior-changing features across the whole repo.

## Planning & Execution

- Use the Superpowers Skillset for planning and execution of work
- Make use of Parallel Execution and Subagent Driven Development where possible
- Ask clarifying questions
- Where possible offer recommendations
- Use multiple-choice where more than one option is available

## Before Committing Changes

- Always run `make check` and resolve all warnings and errors.
- Ensure every new or changed feature has corresponding BDD feature scenarios and that those BDD tests pass.

## Commit Rules

You generate strictly valid multi-line Conventional Commit messages.

Inputs:
- Changed file path: {{file_path}}
- Diff summary: {{diff_summary}}
- Issue IDs: {{issue_ids}}
- Breaking change: {{breaking_change}}
- Behaviour impact: {{behaviour_impact}}
- Test evidence: {{test_evidence}}

Rules:
- Output only the commit message.
- Use this format:

```plaintext
<type>(<scope>)<optional !>: <imperative summary>

- <what changed>
- <why it changed>
- <impact>
- <test evidence if relevant>

Refs: <issue ids>
BREAKING CHANGE: <required only if breaking_change is true>
```

- Use one file per commit.
- Use one logical change per commit.
- Use deterministic type and scope selection.
- Summary must be imperative, lowercase after the type/scope unless a proper noun is required.
- Summary must be <= 72 characters.
- Bullets must be specific and factual.
- Do not mention implementation details unless they affect behaviour, contracts, operations, or maintainability.

## Before pushing to origin

- Make sure ALL documentation (docstrings, code comments, markdown, READMEs etc) is up to date and in sync with the changes made.
- Run `make check`
- Run `make quality-gates`
- If any of the commands above fail, return a warning or an error, you must rectify the problems causing those errors and commit the changes appropriately BEFORE starting the "Before pushing to origin" stage again.

## Creating a Pull Request

You generate high-quality GitHub pull request titles and bodies from Conventional Commits.

Inputs:
- Branch name: {{branch_name}}
- Commit list: {{commit_list}}
- Diff summary: {{diff_summary}}
- Issue IDs: {{issue_ids}}
- Test output: {{test_output}}
- Coverage output: {{coverage_output}}
- Breaking changes: {{breaking_changes}}
- Migration notes: {{migration_notes}}
- Deployment notes: {{deployment_notes}}

Rules:
- Output markdown only.
- Title must use Conventional Commit style:
  <type>(<scope>): <summary>
- Pick the PR type from the highest-impact included commit:
  security > fix > feat > perf > schema > config > deps > docs > test > ci > build > infra > refactor > style > chore
- Pick the PR scope from the dominant scope by commit count.
- Body must include:
  - Summary
  - Conventional Commit Breakdown table
  - Release Notes Draft
  - Behaviour Changes
  - API / Schema / Contract Changes
  - Testing Evidence
  - Risk and Rollback
  - Operational Notes
  - Linked Work
  - Reviewer Checklist
- Do not invent test results.
- If evidence is missing, write "Not provided".
- Breaking changes must be impossible to miss.
- Optimise for generated changelogs, release notes, product docs, and reviewer comprehension.

## After creating a Pull Request(s)

- Monitor the pull request CI/CD pipeline and ensure that all checks are passing green.
  - If any checks have warnings or fail, it is your responsibility to figure out what needs to be fixed and how.
  - Keep working until all CI/CD checks are working as intended and passing without warning or error.
- Monitor the pull request for peer review feedback from the user, Copilot, or other agents.
  - When feedback appears it is your responsibility to consider the feedback and to decide how to action it.
  - All changes made as a result of feedback/peer review must follow the standard workflow outlined above.
- Once all CI/CD checks are green and all peer review feedback has been resolved you can hand the PR(s) off to the user for merge/approval.
- DO NOT EVER approve PRs yourself without explicit permission of the user.
