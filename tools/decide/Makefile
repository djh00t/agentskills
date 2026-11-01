PYTHON ?= python3

.PHONY: check quality-gates install clean build publish

check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -q
	$(PYTHON) decide.py --help > /dev/null

quality-gates: check

install:
	@echo "Stdlib only; nothing to install"

clean:
	$(PYTHON) -c 'import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path(".").rglob("__pycache__")]'

build: check
	@echo "Source-only tool; no build artifact"

publish:
	@echo "Publish through a reviewed repository merge"
