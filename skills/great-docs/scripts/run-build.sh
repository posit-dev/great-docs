#!/usr/bin/env bash
# Build and validate a great-docs site
set -euo pipefail

echo "Building documentation..."
great-docs build

# Validate output
SITE_DIR="great-docs/_site"

if [[ ! -d "$SITE_DIR" ]]; then
    echo "ERROR: Build directory $SITE_DIR not found"
    exit 1
fi

if [[ ! -f "$SITE_DIR/index.html" ]]; then
    echo "ERROR: index.html not found in $SITE_DIR"
    exit 1
fi

echo "Build complete. Site at $SITE_DIR/"

# Count generated pages
PAGE_COUNT=$(find "$SITE_DIR" -name "*.html" | wc -l | tr -d ' ')
echo "Generated $PAGE_COUNT HTML pages"

# Check for key outputs
for file in llms.txt llms-full.txt; do
    if [[ -f "great-docs/$file" ]]; then
        echo "OK: $file exists"
    else
        echo "WARN: $file not found"
    fi
done

echo "Done."
