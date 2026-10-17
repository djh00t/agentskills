PYTHON ?= python3
export PUBLISH_DIR

.PHONY: install check check-instructions quality-gates clean build publish

install:
	$(PYTHON) -m venv .venv
	.venv/bin/python scripts/check_instructions.py

check-instructions:
	$(PYTHON) scripts/check_instructions.py
	git diff --check
	git diff --cached --check

check: check-instructions
	$(PYTHON) -m unittest discover -s tests -v

quality-gates: check
	$(MAKE) build
	$(PYTHON) -m zipfile -t dist/delivery-policy.zip

build: check-instructions
	$(PYTHON) scripts/delivery_bundle.py build

# Destination validation happens before build or any publication writes.
publish:
	$(PYTHON) scripts/delivery_bundle.py validate-destination
	$(MAKE) build
	$(PYTHON) scripts/delivery_bundle.py publish

clean:
	$(PYTHON) scripts/delivery_bundle.py clean
