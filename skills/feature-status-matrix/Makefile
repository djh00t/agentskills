PYTHON ?= python3

.PHONY: check quality-gates install clean build publish

check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -q
	bash -n harnesses/codex/.codex-plugin/fsm-ledger-hook harnesses/codex-marketplace/plugins/fsm-ledger/.codex-plugin/fsm-ledger-hook
	$(PYTHON) -m json.tool harnesses/codex/.codex-plugin/hooks.json > /dev/null
	$(PYTHON) -m json.tool harnesses/codex-marketplace/plugins/fsm-ledger/.codex-plugin/hooks.json > /dev/null

quality-gates: check

install:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install PyYAML

clean:
	$(PYTHON) -c 'import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path(".").rglob("__pycache__")]; shutil.rmtree(".venv", ignore_errors=True)'

build: check
	@echo "Source-only skill; no build artifact"

publish:
	@echo "Publish this skill through a reviewed repository merge"
