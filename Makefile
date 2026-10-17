PYTHON ?= python3
export PUBLISH_DIR

.PHONY: install check quality-gates clean build publish

install:
	$(PYTHON) -m venv .venv
	.venv/bin/python scripts/check_instructions.py

check:
	$(PYTHON) scripts/check_instructions.py
	git diff --check
	git diff --cached --check

quality-gates: check
	$(PYTHON) -m unittest discover -s tests -v

build: check
	$(PYTHON) scripts/delivery_bundle.py build

# Destination validation happens before build or any publication writes.
publish:
	$(PYTHON) scripts/delivery_bundle.py validate-destination
	$(MAKE) build
	$(PYTHON) scripts/delivery_bundle.py publish

clean:
	$(PYTHON) scripts/delivery_bundle.py clean
