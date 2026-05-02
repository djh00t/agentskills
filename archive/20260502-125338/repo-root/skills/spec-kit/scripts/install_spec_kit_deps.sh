#!/usr/bin/env bash

set -euo pipefail

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  echo "uv is not installed; installing uv..."

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "Neither curl nor wget is available to install uv" >&2
    exit 1
  fi

  export PATH="$HOME/.local/bin:$PATH"

  if ! command -v uv >/dev/null 2>&1; then
    echo "uv installation completed but uv is not on PATH" >&2
    echo "Add $HOME/.local/bin to PATH and re-run this script" >&2
    exit 1
  fi
}

ensure_uv

echo "Installing specify CLI from upstream Spec-Kit..."
uv tool install --force specify-cli --from git+https://github.com/github/spec-kit.git

echo "Verifying specify CLI..."
specify --help >/dev/null
echo "specify CLI is installed and ready."
