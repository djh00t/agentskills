PYTHON ?= python3

.PHONY: check quality-gates install clean build publish

# Scenarios in features/codex_turn_events.feature are executed by tests/ (one test per scenario).
check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -q
	$(PYTHON) codex_turn_events.py --help > /dev/null
	bash -n .codex-plugin/codex-turn-events-hook
	$(PYTHON) -m json.tool .codex-plugin/hooks.json > /dev/null
	$(PYTHON) -m json.tool .codex-plugin/plugin.json > /dev/null

quality-gates: check

install:
	@echo "Stdlib only. Trust the plugin in Codex with /hooks; see README."

clean:
	$(PYTHON) -c 'import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path(".").rglob("__pycache__")]'

build: check

publish:
	@echo "Publish through a reviewed repository merge"
