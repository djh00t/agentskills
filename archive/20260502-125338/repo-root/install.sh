#!/usr/bin/env bash

set -euo pipefail

CLI_REF="${AGENTSKILLS_CLI_REF:-main}"
CLI_SOURCE="git+https://github.com/djh00t/agentskills.git@${CLI_REF}"

ensure_uvx() {
  if command -v uvx >/dev/null 2>&1; then
    return
  fi

  echo "uvx is not installed; installing uv..."
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "Neither curl nor wget is available to install uv" >&2
    exit 1
  fi

  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uvx >/dev/null 2>&1; then
    echo "uv installed but uvx is not on PATH" >&2
    echo "Add $HOME/.local/bin to PATH and re-run installer" >&2
    exit 1
  fi
}

ensure_uvx

exec uvx --from "$CLI_SOURCE" agentskills install "$@"
