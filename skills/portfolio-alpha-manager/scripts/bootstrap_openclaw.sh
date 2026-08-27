#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-/home/node/.local/bin/python}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "python binary not found. Set PYTHON_BIN or install python3." >&2
  exit 1
fi

echo "Using Python: ${PYTHON_BIN}"

if ! "${PYTHON_BIN}" -c "import pip" >/dev/null 2>&1; then
  echo "pip missing; bootstrapping pip with get-pip.py..."
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "${tmpdir}"' EXIT
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "${tmpdir}/get-pip.py"
  "${PYTHON_BIN}" "${tmpdir}/get-pip.py" --user --break-system-packages
fi

echo "Installing portfolio-alpha-manager dependencies..."
"${PYTHON_BIN}" -m pip install --user --break-system-packages -e .

echo "Bootstrap complete."
echo "Try: ${PYTHON_BIN} -m pam.cli --help"
