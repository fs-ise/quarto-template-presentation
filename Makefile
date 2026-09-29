QUARTO_VERSION := 1.8.0
QUARTO := $(CURDIR)/.tools/quarto-$(QUARTO_VERSION)/bin/quarto

.PHONY: test test-static test-install test-copier test-render test-browser test-public-install clean-test-tools

$(QUARTO):
	mkdir -p .tools
	curl --fail --location --retry 3 \
	  https://github.com/quarto-dev/quarto-cli/releases/download/v$(QUARTO_VERSION)/quarto-$(QUARTO_VERSION)-linux-amd64.tar.gz \
	  | tar -xz -C .tools

test: $(QUARTO)
	uv sync
	uv run playwright install chromium
	mkdir -p test-results
	PATH="$(dir $(QUARTO)):$$PATH" uv run pytest --junitxml=test-results/pytest.xml

test-static:
	uv sync
	mkdir -p test-results
	uv run pytest tests/test_manifest.py tests/test_render.py -m static --junitxml=test-results/static.xml

test-install: $(QUARTO)
	uv sync
	mkdir -p test-results
	PATH="$(dir $(QUARTO)):$$PATH" uv run pytest tests/test_install.py --junitxml=test-results/install.xml

test-copier: $(QUARTO)
	uv sync
	mkdir -p test-results
	PATH="$(dir $(QUARTO)):$$PATH" uv run pytest tests/test_copier.py tests/test_render.py::test_generated_project_rendering --junitxml=test-results/copier.xml

test-render: $(QUARTO)
	uv sync
	mkdir -p test-results
	PATH="$(dir $(QUARTO)):$$PATH" uv run pytest tests/test_render.py::test_canonical_example_rendering --junitxml=test-results/render.xml

test-browser: $(QUARTO)
	uv sync
	uv run playwright install chromium
	mkdir -p test-results
	PATH="$(dir $(QUARTO)):$$PATH" uv run pytest tests/test_browser.py --junitxml=test-results/browser.xml

# Deliberately separate from PR source-revision tests: this checks that the
# public command remains usable, not that GitHub already contains this commit.
test-public-install: $(QUARTO)
	uv sync
	PATH="$(dir $(QUARTO)):$$PATH" FS_ISE_TEST_PUBLIC_INSTALL=1 uv run pytest tests/test_install.py -k public

clean-test-tools:
	rm -rf .tools .test-artifacts
