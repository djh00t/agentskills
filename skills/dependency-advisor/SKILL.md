---
name: dependency-advisor
description: Choose a safe dependency version before adding or upgrading a package.
---

## What I do

- Run `depadvisor recommend <package> --ecosystem <ecosystem> --policy <policy>` before adding or upgrading a direct dependency.
- Use the JSON response as the source of truth for `status`, `recommended_version`, `reason`, and `minimum_release_age_hours`.
- Stop and explain the blocker when the result is not `recommended`.

## When to use me

Use this for direct dependency adds, upgrades, pin updates, or dependency review tasks in Python, Rust, JavaScript, shell, or Swift projects.

## CLI Setup

- Keep the `dependency-advisor` code in a git checkout that Codex can access. The canonical skill source lives in the repository tree at `https://github.com/djh00t/dependency-advisor/tree/main/.agents/skills`.
- Clone or open the repository checkout that contains that tree, for example `git clone https://github.com/djh00t/dependency-advisor.git ~/work/src/github.com_local/djh00t/dependency-advisor`.
- From that repository checkout, run `make install` to sync the environment and install the `depadvisor` console script.
- Run the tool from the same checkout with `uv run depadvisor <command>` when you need an on-demand execution path.
- Do not install the executable under `~/.agents/skills`; that directory is for the skill instructions only.

## Workflow

1. Determine the package name, ecosystem, and policy mode.
2. Run `depadvisor recommend` with the requested package, ecosystem, and `--policy <policy>`.
3. If `status` is `recommended`, use `recommended_version` exactly and mention the policy mode that approved it.
4. If `status` is `unknown_package` or `no_match`, stop and explain that Dependency Advisor could not approve a version automatically.
5. Do not bypass this check for direct dependencies unless the user explicitly instructs you to override the policy outcome.

## Output

- State the chosen version or the blocking reason.
- Include the ecosystem, policy mode, and minimum release age in hours.
