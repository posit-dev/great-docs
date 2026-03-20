#!/usr/bin/env bash
# Setup development environment for great-docs
set -euo pipefail

echo "Creating virtual environment..."
python -m venv .venv
source .venv/bin/activate

echo "Installing package in editable mode..."
pip install -e ".[dev]"

echo "Installing great-docs..."
pip install great-docs

echo "Checking Quarto..."
if command -v quarto &> /dev/null; then
    echo "Quarto $(quarto --version) found"
else
    echo "ERROR: Quarto not installed. Visit https://quarto.org/docs/get-started/"
    exit 1
fi

echo "Validating package import..."
PACKAGE=$(python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    d = tomllib.load(f)
pkg = d.get('project', {}).get('name', '').replace('-', '_')
print(pkg)
")
python -c "import ${PACKAGE}; print('Import OK: ${PACKAGE}')"

echo "Environment ready."
