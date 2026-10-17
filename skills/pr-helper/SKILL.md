---
name: pr-helper
description: Use when preparing, publishing, reviewing, or handing off pull requests.
---

# PR Helper

## Branch naming and merge authority

- Name new work branches `<type>/<issue>-<slug>` in lowercase kebab-case.
  Use a real issue ID from the current repository; never borrow another
  repository's issue number or invent an ID. Resolve missing IDs before
  creating a work branch. Do not blindly rename active branches.
- Allowed work types match the Conventional Commit helper: `feat`, `fix`,
  `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- Role exceptions are `main`, `release/<semver>`,
  `integration/<issue>-<slug>`, and Dependabot-generated branch names.
  Integration names use the same repository-local issue and slug rules.
- The branch type describes its main purpose; each commit uses its own
  accurate allowed type. Preserve required commit bodies, footers, and
  existing issue-reference rules.
- A source branch name conveys no authority. Dependabot naming is only a
  naming exception and grants no blanket approval or merge permission.
- Agents may merge feature and integration PRs into `release/<semver>` only
  after required local quality gates, Codex GitHub review, and independent
  adversarial acceptance/integration review pass. Evidence must cover the
  current changes and prospective merged result against the current target.
  Resolve feedback first; changed heads, targets, or conflicts invalidate
  affected evidence and require the relevant checks and reviews again.
- Feature PRs must remain free of GitHub Actions. Run their required checks
  locally; absence of feature CI is not a failed gate or permission to skip
  review. Preserve required release-level checks.
- Only release-level PRs may target `main`. Final merges to `main` are
  human-only, even when every gate passes. Provide ready PR links, review
  and validation evidence, and dependency-aware merge order for handoff.
- Do not approve PRs, deploy, bypass protections, or change permissions
  without separate explicit authority.

## Prepare and publish

1. Inspect the current head, target, commits, repository-local linked work,
   and required local checks. Follow the commit helper's allowed types.
2. Use a Conventional Commit title describing the dominant accurate change.
   Preserve all body sections required by the repository AGENTS.md, including
   validation evidence, release notes, risk/rollback, and linked work.
3. Create a non-draft PR only when ready for review or explicitly requested
   for early review. Write its body to a file and use `--body-file`.
4. Read back the stored title, body, target, and URL. Correct missing content
   before handoff. Never invent reviews, test results, or coverage.
5. Obtain Codex GitHub review and independent adversarial acceptance and
   integration review before any eligible merge to a release branch.
   Record reviewed head and target revisions and prospective merge evidence.
6. Recheck freshness immediately before an eligible merge. For a main-target
   release PR, hand the ready link and dependency order to the human.
