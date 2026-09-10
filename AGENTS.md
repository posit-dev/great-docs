# AGENTS.md

Instructions for AI coding agents working in this repository.

## Environment

Use `uv` for dependency management. The project configuration is in `pyproject.toml`. Run commands
from the repository root using the Makefile.

## Key commands

- `make test`: Core tests (parallel, with coverage). Excludes synthetic and integration tests.
- `make test-synthetic`: Synthetic package tests. Run when changes affect rendering, site
  generation, or test-package specs.
- `make test-integration`: Integration tests with external packages. Run when changes affect
  package discovery, interlinks, or external API consumption.
- `make lint`: Run ruff formatter and linter with auto-fix.
- `make format`: Format code with ruff (formatting only, no lint fixes).
- `make check`: Lint + core tests combined.
- `make type-check`: Run mypy across multiple Python versions.
- `make type-check-renderer`: Run pyright on the API reference renderer.

Default to `make test` during iteration. Run `make test-synthetic` or `make test-integration`
when your changes touch areas those suites cover.

## Code style

Ruff handles formatting and linting. No manual style enforcement needed beyond what ruff checks.

Internal modules use a leading underscore (e.g., `_renderer`, `_apiref`, `_builtin`).
Public modules do not. Follow this convention when creating new modules.

Match the type annotation level of surrounding code. Both mypy (strict) and pyright (strict) are
configured, but not all code is fully annotated yet.

## Docstrings

Docstrings use a mixture of NumPy style and Quarto conventions:

- use Quarto-style markup, not reStructuredText.
- use single backticks for inline code (`` `value` ``), never double backticks (``` ``value`` ```).
- code cells in docstrings can be executed by Quarto, inserting output after them.

## CLI

The CLI is Click-based with its entry point in `cli.py`. CLI commands and their options are public
API. Do not rename, remove, or change command signatures without explicit discussion.

## Do not edit

These directories contain generated output. Do not hand-edit files in them:

- `_freeze/`: Quarto freeze directory
- `build/`, `dist/`: Python build artifacts
- `great-docs/`, `great-docs-dev/`, and other `great-docs-*` directories: rendered site output

Do not edit generated Quarto output. If rendered output looks wrong, fix the source and rebuild.

## Git

Do not create branches, stage files, commit, or push unless explicitly asked. Leave git history
alone (inspecting status and logs is fine).
