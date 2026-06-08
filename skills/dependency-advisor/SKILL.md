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

## Workflow

1. Determine the package name, ecosystem, and policy mode.
2. Run `depadvisor recommend` with the requested package, ecosystem, and `--policy <policy>`.
3. If `status` is `recommended`, use `recommended_version` exactly and mention the policy mode that approved it.
4. If `status` is `unknown_package` or `no_match`, stop and explain that Dependency Advisor could not approve a version automatically.
5. Do not bypass this check for direct dependencies unless the user explicitly instructs you to override the policy outcome.

## Output

- State the chosen version or the blocking reason.
- Include the ecosystem, policy mode, and minimum release age in hours.
