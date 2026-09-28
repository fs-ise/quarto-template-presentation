QUARTO_VERSION := 1.8.0
QUARTO := $(CURDIR)/.tools/quarto-$(QUARTO_VERSION)/bin/quarto

.PHONY: test test-static test-public-install clean-test-tools

$(QUARTO):
	mkdir -p .tools
	curl --fail --location --retry 3 \
	  https://github.com/quarto-dev/quarto-cli/releases/download/v$(QUARTO_VERSION)/quarto-$(QUARTO_VERSION)-linux-amd64.tar.gz \
	  | tar -xz -C .tools

test: $(QUARTO)
	uv sync
	uv run playwright install chromium
	PATH="$(dir $(QUARTO)):$$PATH" uv run pytest

test-static:
	uv sync
	uv run pytest -m "not integration and not browser"

# Deliberately separate from PR source-revision tests: this checks that the
# public command remains usable, not that GitHub already contains this commit.
test-public-install: $(QUARTO)
	uv sync
	PATH="$(dir $(QUARTO)):$$PATH" FS_ISE_TEST_PUBLIC_INSTALL=1 uv run pytest tests/test_install.py -k public

clean-test-tools:
	rm -rf .tools .test-artifacts
