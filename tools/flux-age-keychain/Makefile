.PHONY: check quality-gates build test source-check install clean

APP_DIR ?= $(HOME)/Applications
BIN_DIR ?= $(HOME)/.local/bin

check: test source-check

# check, plus shellcheck on package.sh when shellcheck is installed.
quality-gates: check
	@if command -v shellcheck >/dev/null 2>&1; then shellcheck package.sh && echo "shellcheck: ok"; \
	else echo "shellcheck: not installed, skipped"; fi

build:
	swift build

test:
	swift test

# The helper must never delete a keychain item: a delete syncs to every device.
source-check:
	@if command -v rg >/dev/null 2>&1; then hits=$$(rg -n "SecItemDelete" Sources || true); else hits=$$(grep -rn "SecItemDelete" Sources || true); fi; \
	if [ -n "$$hits" ]; then echo "source-check: Sources must not call SecItemDelete:"; echo "$$hits"; exit 1; fi; \
	echo "source-check: ok (no SecItemDelete in Sources)"

# Signed build (needs FLUX_AGE_TEAM_ID, FLUX_AGE_BUNDLE_ID, FLUX_AGE_GROUP_SUFFIX and the
# profile; see README.md), then install the app and link the binary onto PATH.
install:
	./package.sh
	mkdir -p "$(APP_DIR)" "$(BIN_DIR)"
	ditto dist/FluxAgeKeychain.app "$(APP_DIR)/FluxAgeKeychain.app"
	ln -sf "$(APP_DIR)/FluxAgeKeychain.app/Contents/MacOS/flux-age-keychain" "$(BIN_DIR)/flux-age-keychain"
	@echo "installed; run: flux-age-keychain doctor"

clean:
	rm -rf .build dist
