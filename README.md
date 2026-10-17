# Agent skills

Personal agent instructions and reusable skills.

Run `make check` before committing or pushing instruction changes. It checks
TOML syntax, delivery-helper metadata and links, and patch whitespace.
`make quality-gates` runs the complete root instruction checks. Applications
bundled inside individual skills have their own Makefiles and test suites;
these root checks do not claim to test those applications or perform a
resolved/transitive dependency security audit.

The canonical commit contract is
[Conventional Commit Helper](skills/conventional-commit-helper/SKILL.md).
[Commit Helper](skills/commit-helper/SKILL.md) provides a short entry point;
[PR Helper](skills/pr-helper/SKILL.md) governs PR preparation and merge handoff.
