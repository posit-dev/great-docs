"""
Batch script: Add coverage_exclude to all spec files that don't have it.

For each spec, determines which coverage levels the package structurally cannot
pass (based on its expected dict and features), then injects coverage_exclude
into the spec's expected dict.

DED is never auto-excluded as it's kept as an aspirational target.

Run from repo root:
    python test-packages/apply_coverage_excludes.py [--dry-run] [--batch N]
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from render_all import (
    _COVERAGE_LEVELS,
    ALL_PACKAGES,
    _compute_coverage,
    _spec_file_exists,
    get_spec,
)

SPEC_DIR = Path(__file__).parent / "synthetic" / "specs"

# DED is aspirational — never auto-exclude
NEVER_EXCLUDE = {"DED"}


def determine_exclusions(name: str) -> list[str]:
    """Determine which levels should be excluded for a package."""
    coverage = _compute_coverage(name)
    return [
        level
        for level in _COVERAGE_LEVELS
        if not coverage.get(level) and level not in NEVER_EXCLUDE
    ]


def inject_coverage_exclude(spec_path: Path, exclusions: list[str]) -> bool:
    """Inject coverage_exclude into a spec file's expected dict.

    Returns `True` if the file was modified, `False` if skipped.
    """
    content = spec_path.read_text(encoding="utf-8")

    # Skip if already has coverage_exclude or coverage_include
    if "coverage_exclude" in content or "coverage_include" in content:
        return False

    if not exclusions:
        return False

    # Build the exclude line
    exclude_str = repr(exclusions)

    # Find the closing of the "expected" dict: look for the pattern
    # where "expected": { ... } ends with },\n} or just \n    },\n}
    # Strategy: find `"expected": {` then find its closing `}`

    # Try to find the last key-value in expected dict and add after it
    # Pattern: look for the last line before the closing `},` or `}` of expected

    # Find "expected": { ... }
    # We'll use a regex to find the expected dict and insert before its closing brace
    # The expected dict typically ends with:
    #     "some_key": some_value,
    #   },
    # }

    # Find the "expected" key
    expected_match = re.search(r'"expected"\s*:\s*\{', content)
    if not expected_match:
        # No expected dict — need to add one
        # Find the closing `}` of the SPEC dict and add expected before it
        # For now, skip these (19 packages without expected)
        return False

    # Find the matching closing brace for the expected dict
    start = expected_match.end()
    brace_depth = 1
    pos = start
    while pos < len(content) and brace_depth > 0:
        if content[pos] == "{":
            brace_depth += 1
        elif content[pos] == "}":
            brace_depth -= 1
        pos += 1

    # pos is now just past the closing } of expected
    closing_brace_pos = pos - 1

    # Find the last non-whitespace before the closing brace
    before_close = content[:closing_brace_pos].rstrip()

    # Determine indentation (look at lines inside expected)
    lines_in_expected = content[expected_match.start() : closing_brace_pos].split("\n")
    # Find a typical key line for indentation reference
    indent = "        "  # default 8 spaces
    for line in lines_in_expected[1:]:
        stripped = line.lstrip()
        if stripped.startswith('"') and ":" in stripped:
            indent = line[: len(line) - len(stripped)]
            break

    # Build the new line to insert
    new_line = f'{indent}"coverage_exclude": {exclude_str},'

    # Insert before the closing brace
    # Check if the last content line before } has a trailing comma
    if before_close.endswith(","):
        # Good, just add our line
        new_content = before_close + "\n" + new_line + "\n" + content[closing_brace_pos:]
    else:
        # Add a comma to the previous line
        new_content = before_close + ",\n" + new_line + "\n" + content[closing_brace_pos:]

    spec_path.write_text(new_content, encoding="utf-8")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Add coverage_exclude to spec files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--batch", type=int, default=0, help="Process only N specs (0=all)")
    parser.add_argument("--start", type=int, default=0, help="Start at this index")
    args = parser.parse_args()

    modified = 0
    skipped = 0
    errors = []

    packages = ALL_PACKAGES[args.start :]
    if args.batch > 0:
        packages = packages[: args.batch]

    for name in packages:
        if not _spec_file_exists(name):
            continue

        spec = get_spec(name)
        exp = spec.get("expected", {})

        # Skip if already configured
        if exp.get("coverage_exclude") or exp.get("coverage_include"):
            skipped += 1
            continue

        exclusions = determine_exclusions(name)
        if not exclusions:
            skipped += 1
            continue

        spec_path = SPEC_DIR / f"{name}.py"
        if not spec_path.exists():
            errors.append(f"{name}: spec file not found")
            continue

        if args.dry_run:
            print(f"  {name}: would exclude {exclusions}")
            modified += 1
        else:
            try:
                if inject_coverage_exclude(spec_path, exclusions):
                    modified += 1
                    print(f"  ✓ {name}: {len(exclusions)} levels excluded")
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"{name}: {e}")

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Modified: {modified}, Skipped: {skipped}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")


if __name__ == "__main__":
    main()
