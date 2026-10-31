.PHONY: check build test source-check clean

check: test source-check

build:
	swift build

test:
	swift test

# The helper must never delete a keychain item: a delete syncs to every device.
source-check:
	@if command -v rg >/dev/null 2>&1; then hits=$$(rg -n "SecItemDelete" Sources || true); else hits=$$(grep -rn "SecItemDelete" Sources || true); fi; \
	if [ -n "$$hits" ]; then echo "source-check: Sources must not call SecItemDelete:"; echo "$$hits"; exit 1; fi; \
	echo "source-check: ok (no SecItemDelete in Sources)"

clean:
	rm -rf .build dist
