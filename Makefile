.PHONY: check quality-gates

# Root checks cover the delivery instruction collection. Skill-specific
# applications retain their own Makefiles and tests.
check:
	python3 scripts/check_instructions.py
	git diff --check

quality-gates: check
