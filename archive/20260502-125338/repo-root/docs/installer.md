# Installer

The hosted installer lives at the repo root as `install.sh` and is designed for
`curl | bash` usage.

## Preferred Command

- `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install`

## Hosted URL

- `https://raw.githubusercontent.com/djh00t/agentskills/main/install.sh`
- This shell script forwards to the same `uvx` command.

## Examples

- Interactive selection:
  - `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install`
- Global install of one skill:
  - `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install --skills spec-kit --scope global`
- Repo-local install of one skill:
  - `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install --skills spec-kit --scope repo --repo-dir .`
- Install multiple skills:
  - `uvx --from git+https://github.com/djh00t/agentskills.git agentskills install --skills spec-kit,another-skill --scope global`

## Targets

- Global scope: `~/.agents/skills/<skill_name>`
- Repo scope: `<repo>/.agents/skills/<skill_name>`

## Options

- `--skills <csv>`: one or more skill names.
- `--scope <global|repo>`: destination scope.
- `--repo-dir <path>`: repo target path for repo scope.
- `--ref <git-ref>`: source ref (default `main`).
- `--force`: overwrite existing installed skills without prompt.

## Runtime behavior

- Installer uses a temporary GitHub source archive directory.
- Temporary files are cleaned up automatically after install.
- Shell bootstrap installs `uv` automatically if `uvx` is missing.
