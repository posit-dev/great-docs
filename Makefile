# Python command - uses venv if available, otherwise system python
VENV_PYTHON := .venv/bin/python
PYTHON := $(shell if [ -f $(VENV_PYTHON) ]; then echo $(VENV_PYTHON); else command -v python3 2> /dev/null || command -v python 2> /dev/null; fi)

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: test
test: ## Run core tests (fast, no package builds)
	@$(PYTHON) -m pytest tests/ \
		-n auto \
		--ignore=tests/test_integration.py \
		--ignore=tests/test_synthetic.py

.PHONY: test-synthetic
test-synthetic: ## Run synthetic package tests
	@$(PYTHON) -m pytest tests/test_synthetic.py -n auto

.PHONY: test-integration
test-integration: ## Run integration tests with external packages
	@$(PYTHON) -m pytest tests/test_integration.py -n auto

.PHONY: test-all
test-all: ## Run all tests (core + synthetic + integration)
	@$(PYTHON) -m pytest tests/ -n auto

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report
	@$(PYTHON) -m pytest \
		--cov=great_docs \
		--cov-report=term-missing \
		--cov-report=html \
		tests/ -v

.PHONY: test-verbose
test-verbose: ## Run tests with verbose output
	@$(PYTHON) -m pytest tests/ -vv

.PHONY: lint
lint: ## Run ruff formatter and linter
	@$(PYTHON) -m ruff format
	@$(PYTHON) -m ruff check --fix

.PHONY: format
format: ## Format code with ruff
	@$(PYTHON) -m ruff format

.PHONY: check-format
check-format: ## Check code formatting without making changes
	@$(PYTHON) -m ruff format --check
	@$(PYTHON) -m ruff check

.PHONY: type-check
type-check: ## Run type checking with mypy
	@$(PYTHON) -m mypy great_docs --python-version 3.8
	@$(PYTHON) -m mypy great_docs --python-version 3.9
	@$(PYTHON) -m mypy great_docs --python-version 3.10
	@$(PYTHON) -m mypy great_docs --python-version 3.11
	@$(PYTHON) -m mypy great_docs --python-version 3.12

.PHONY: type-check-renderer
type-check-renderer: ## Run type checking with pyright on the renderer
	@$(PYTHON) -m pyright great_docs/_renderer/_render

.PHONY: check
check: lint test ## Run all checks (lint and test)

.PHONY: clean
clean: clean-build clean-pyc clean-test ## Remove all build, test, coverage and Python artifacts

.PHONY: clean-build
clean-build: ## Remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc: ## Remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: clean-test
clean-test: ## Remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr .mypy_cache/

.PHONY: build
build: clean ## Build source and wheel distribution
	@$(PYTHON) -m build

.PHONY: dist
dist: build ## Alias for build

.PHONY: install
install: ## Install the package in editable mode
	@pip install -e .

.PHONY: install-dev
install-dev: ## Install package with development dependencies
	@pip install -e ".[dev]"

.PHONY: uninstall
uninstall: ## Uninstall the package
	@pip uninstall -y great-docs

.PHONY: reinstall
reinstall: uninstall install ## Reinstall the package

.PHONY: publish-test
publish-test: clean build ## Publish to TestPyPI
	@python -m twine upload --repository testpypi dist/*

.PHONY: publish
publish: clean build ## Publish to PyPI
	@python -m twine upload dist/*

.PHONY: test-install
test-install: build ## Test installation in a clean environment
	@echo "Testing installation from wheel..."
	@pip install --force-reinstall dist/great_docs*.whl
	@great-docs --version
	@great-docs --help

.PHONY: test-cli
test-cli: ## Test the CLI in a temp directory
	@echo "Testing CLI installation..."
	@mkdir -p /tmp/test_great_docs
	@cd /tmp/test_great_docs && great-docs init --force
	@echo "CLI test passed"
	@rm -rf /tmp/test_great_docs

.PHONY: dev-setup
dev-setup: ## Set up development environment
	@pip install -e ".[dev]"
	@echo "Development environment ready"

.PHONY: docs-build
docs-build: ## Build documentation with Quarto
	@cd docs && quarto render

.PHONY: docs-preview
docs-preview: ## Preview documentation locally
	@cd docs && quarto preview

.PHONY: docs-install
docs-install: ## Install documentation dependencies
	@pip install -e ".[docs]"

.PHONY: site-build
site-build: ## Build the great-docs site
	@great-docs build

.PHONY: hub-build
hub-build: ## Full build of the Great Docs Gauntlet (200 packages, port 3333)
	@$(PYTHON) test-packages/render_all.py --build

.PHONY: hub-resume
hub-resume: ## Resume an interrupted full GDG build (skip already-ok packages)
	@$(PYTHON) test-packages/render_all.py --build --skip-ok

.PHONY: hub-rebuild
hub-rebuild: ## Selective GDG rebuild: make hub-rebuild PKG="gdtest_minimal gdtest_github_icon"
	@test -n "$(PKG)" || (echo "Usage: make hub-rebuild PKG=\"name1 name2\"" && exit 1)
	@$(PYTHON) test-packages/render_all.py --build --only $(PKG)

.PHONY: hub-refresh
hub-refresh: ## Reassemble GDG hub pages (updates test coverage, no rebuild)
	@$(PYTHON) -c "\
	import sys; sys.path.insert(0, 'test-packages'); \
	from build_state import load_state; \
	from render_all import assemble_hub, STATE_FILE, _result_from_state; \
	from synthetic.catalog import ALL_PACKAGES; \
	state = load_state(STATE_FILE); \
	pkgs = state.get('packages', {}); \
	results = [_result_from_state(n, pkgs[n]) for n in ALL_PACKAGES if n in pkgs]; \
	assemble_hub(results, state=state)" 2>/dev/null || \
	 echo "No build state found. Run 'make hub-build' first."

.PHONY: hub-open
hub-open: ## Open the Great Docs Gauntlet in the default browser
	@open test-packages/_rendered/_hub/index.html 2>/dev/null || \
	 xdg-open test-packages/_rendered/_hub/index.html 2>/dev/null || \
	 echo "GDG page: test-packages/_rendered/_hub/index.html"

.PHONY: hub-serve
hub-serve: ## Serve the Great Docs Gauntlet locally (port 3333)
	@$(PYTHON) test-packages/render_all.py --serve

.PHONY: hub-state
hub-state: ## Show GDG build state summary
	@$(PYTHON) -c "\
	import sys, json; sys.path.insert(0, 'test-packages'); \
	from build_state import load_state, summary; \
	from pathlib import Path; \
	p = Path('test-packages/_rendered/_build_state.json'); \
	s = load_state(p); \
	info = summary(s); info['last_run_id'] = s.get('last_run_id'); \
	print(json.dumps(info, indent=2))" 2>/dev/null || \
	 echo "No build state found. Run 'make hub-build' first."

.PHONY: hub-deploy
hub-deploy: ## Trigger GDG hub deployment to GitHub Pages (requires gh CLI)
	@gh workflow run deploy.yml --repo rich-iannone/gdg \
	  -f great_docs_ref=$$(git rev-parse --abbrev-ref HEAD) && \
	 echo "Deployment triggered. Watch at: https://github.com/rich-iannone/gdg/actions"
