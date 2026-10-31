PYTHON ?= python3
STATE_DIR ?= $(HOME)/.local/state/codex-turn-events
PLIST := com.djh00t.codex-turn-events.reconcile.plist

.PHONY: check quality-gates install launchd-plist clean build publish

# Scenarios in features/codex_turn_events.feature are executed by tests/ (one test per scenario).
check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -q
	$(PYTHON) codex_turn_events.py --help > /dev/null
	bash -n .codex-plugin/codex-turn-events-hook
	$(PYTHON) -m json.tool .codex-plugin/hooks.json > /dev/null
	$(PYTHON) -m json.tool .codex-plugin/plugin.json > /dev/null
	$(PYTHON) -c 'import plistlib; plistlib.loads(open("launchd/$(PLIST).in","rb").read())'

quality-gates: check

install:
	@echo "Stdlib only. Trust the plugin in Codex with /hooks; see README for launchd."

# Renders the plist into build/; loading it is a manual, reviewed step (see README).
launchd-plist:
	mkdir -p build
	sed -e 's|@TOOL_DIR@|$(CURDIR)|' -e 's|@STATE_DIR@|$(STATE_DIR)|' launchd/$(PLIST).in > build/$(PLIST)
	@echo "Rendered build/$(PLIST)"

clean:
	$(PYTHON) -c 'import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path(".").rglob("__pycache__")]; shutil.rmtree("build", ignore_errors=True)'

build: check

publish:
	@echo "Publish through a reviewed repository merge"
