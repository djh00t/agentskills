# Agent skills

Personal agent instructions and reusable skills. Root delivery tooling needs
Python 3.11 or newer and Git; it has no third-party dependencies.

- `make install` creates `.venv` and validates instructions with that Python.
- `make check` checks TOML syntax, delivery-helper metadata and links, and
  both staged and unstaged patch whitespace.
- `make quality-gates` also executes the Gherkin workflow scenarios in
  `tests/features/delivery.feature` against isolated real Git repositories.
- `make build` validates and creates a reproducible `dist/delivery-policy.zip`.
  The bundle contains AGENTS.md and the three delivery helpers only; it is
  a policy bundle, not a distribution of every application in this repository.
- `make publish PUBLISH_DIR=/explicit/local/path` copies that bundle to the
  chosen local directory. A missing destination fails before building.
  No network service, package registry, GitHub release, or deployment is used.
- `make clean` removes `.venv` and `dist` while preserving local configuration.

Applications bundled inside individual skills retain their own Makefiles and
suites. Root checks do not claim to test those applications, execute an agent's
reasoning, or perform a resolved/transitive dependency security audit.
Independent semantic acceptance review is still required for instruction changes.

The canonical commit contract is
[Conventional Commit Helper](skills/conventional-commit-helper/SKILL.md).
[Commit Helper](skills/commit-helper/SKILL.md) provides a short entry point;
[PR Helper](skills/pr-helper/SKILL.md) governs PR preparation and merge handoff.
