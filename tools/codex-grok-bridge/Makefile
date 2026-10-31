PYTHON ?= python3

.PHONY: check quality-gates

check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -q
	$(PYTHON) -m json.tool roles.json > /dev/null

quality-gates: check
