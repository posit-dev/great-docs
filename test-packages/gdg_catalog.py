#!/usr/bin/env python
"""
GDG Catalog — at-a-glance visibility into all Great Docs Gauntlet packages.

Displays a summary table showing:
- Which packages have a great-docs.yml config vs. pure "init → build"
- Which test levels each package participates in (L0–L3, init, rendered)
- Dimension axes covered

Usage:
    python test-packages/gdg_catalog.py                # full summary
    python test-packages/gdg_catalog.py --no-config    # only packages WITHOUT great-docs.yml
    python test-packages/gdg_catalog.py --with-config  # only packages WITH great-docs.yml
    python test-packages/gdg_catalog.py --init-gap     # no-config packages missing init tests
    python test-packages/gdg_catalog.py --stats        # summary statistics only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make test-packages importable
_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from synthetic.catalog import ALL_PACKAGES, DIMENSIONS, get_spec

# ── Which packages are tested through init ───────────────────────────────────
# As of the expansion, ALL available specs are tested through init (L2).
# This set is populated dynamically from the spec files on disk.
_SPECS_DIR = _DIR / "synthetic" / "specs"
INIT_TESTED = {p.stem for p in _SPECS_DIR.glob("gdtest_*.py")}

# ── Rendered sites (check _rendered/) ────────────────────────────────────────
_RENDERED_DIR = _DIR / "_rendered"


def _has_rendered(name: str) -> bool:
    return (_RENDERED_DIR / name).is_dir()


# ── Classify each package ────────────────────────────────────────────────────


def classify_packages() -> list[dict]:
    """Return a list of dicts with metadata for each GDG package."""
    results = []
    for name in ALL_PACKAGES:
        try:
            spec = get_spec(name)
        except Exception:
            continue

        has_config = bool(spec.get("config"))
        expected = spec.get("expected", {})

        # Determine which test levels apply
        levels = []
        if "detected_name" in expected or "detected_module" in expected:
            levels.append("L0")
        if "export_names" in expected or "section_titles" in expected:
            levels.append("L1")
        if any(
            k in expected
            for k in (
                "has_user_guide",
                "has_license_page",
                "explicit_reference",
                "name_module_mismatch",
            )
        ):
            levels.append("L2")
        if expected.get("cli_enabled"):
            levels.append("L3")
        if name in INIT_TESTED:
            levels.append("init")
        if _has_rendered(name):
            levels.append("R")

        results.append(
            {
                "name": name,
                "has_config": has_config,
                "dimensions": spec.get("dimensions", []),
                "levels": levels,
                "init_tested": name in INIT_TESTED,
                "description": spec.get("description", ""),
            }
        )
    return results


# ── Display helpers ──────────────────────────────────────────────────────────

# Badge characters
_BADGE_CONFIG = "●"  # has great-docs.yml
_BADGE_NO_CONFIG = "○"  # no great-docs.yml (pure init → build)
_BADGE_INIT = "▶"  # covered by init test
_BADGE_NO_INIT = "·"  # NOT covered by init test


def _level_str(levels: list[str]) -> str:
    return ",".join(levels) if levels else "—"


def _dim_str(dims: list[str]) -> str:
    if not dims:
        return ""
    axes = set()
    for d in dims:
        info = DIMENSIONS.get(d, {})
        if info.get("axis"):
            axes.add(info["axis"])
    return ",".join(sorted(axes))


def print_table(packages: list[dict], title: str = "GDG Catalog"):
    """Print a formatted table of packages."""
    if not packages:
        print(f"\n{title}: (none)\n")
        return

    print(f"\n{'═' * 90}")
    print(f"  {title}  ({len(packages)} packages)")
    print(f"{'═' * 90}")
    print(f"  {'cfg':<3}  {'init':<4}  {'Name':<40}  {'Levels':<14}  {'Axes'}")
    print(f"  {'─' * 3}  {'─' * 4}  {'─' * 40}  {'─' * 14}  {'─' * 20}")

    for pkg in packages:
        cfg_badge = _BADGE_CONFIG if pkg["has_config"] else _BADGE_NO_CONFIG
        init_badge = _BADGE_INIT if pkg["init_tested"] else _BADGE_NO_INIT
        print(
            f"  {cfg_badge:<3}  {init_badge:<4}  "
            f"{pkg['name']:<40}  "
            f"{_level_str(pkg['levels']):<14}  "
            f"{_dim_str(pkg['dimensions'])}"
        )

    print()


def print_stats(packages: list[dict]):
    """Print summary statistics."""
    total = len(packages)
    with_config = sum(1 for p in packages if p["has_config"])
    no_config = total - with_config
    init_tested = sum(1 for p in packages if p["init_tested"])
    rendered = sum(1 for p in packages if "R" in p["levels"])

    no_config_no_init = sum(1 for p in packages if not p["has_config"] and not p["init_tested"])

    print(f"\n{'═' * 60}")
    print("  GDG Summary Statistics")
    print(f"{'═' * 60}")
    print(f"  Total packages:                      {total}")
    print(f"  With great-docs.yml (config):        {with_config}  ({_BADGE_CONFIG})")
    print(f"  Without great-docs.yml (pure init):  {no_config}  ({_BADGE_NO_CONFIG})")
    print(f"  Covered by init tests:               {init_tested}  ({_BADGE_INIT})")
    print(f"  Have rendered output:                 {rendered}")
    print(f"{'─' * 60}")
    print("  ⚠  No-config packages MISSING init test coverage:")
    print(f"     {no_config_no_init} / {no_config} pure-init packages untested")
    print(f"{'─' * 60}")
    print("\n  Legend:")
    print(
        f"    {_BADGE_CONFIG} = has great-docs.yml    {_BADGE_NO_CONFIG} = no config (pure init → build)"
    )
    print(f"    {_BADGE_INIT} = init-tested            {_BADGE_NO_INIT} = not init-tested")
    print()


def main():
    parser = argparse.ArgumentParser(description="GDG catalog at-a-glance")
    parser.add_argument("--no-config", action="store_true", help="Only no-config packages")
    parser.add_argument("--with-config", action="store_true", help="Only config packages")
    parser.add_argument("--init-gap", action="store_true", help="No-config not init-tested")
    parser.add_argument("--stats", action="store_true", help="Statistics only")
    parser.add_argument("--axes", type=str, help="Filter by dimension axis (e.g. layout,config)")
    args = parser.parse_args()

    packages = classify_packages()

    if args.stats:
        print_stats(packages)
        return

    if args.no_config:
        filtered = [p for p in packages if not p["has_config"]]
        print_table(filtered, "No-Config Packages (pure init → build)")
        print_stats(filtered)
    elif args.with_config:
        filtered = [p for p in packages if p["has_config"]]
        print_table(filtered, "Config Packages (have great-docs.yml)")
        print_stats(filtered)
    elif args.init_gap:
        filtered = [p for p in packages if not p["has_config"] and not p["init_tested"]]
        print_table(filtered, "⚠ INIT TEST GAP: no-config packages missing init coverage")
        print(
            f"  These {len(filtered)} packages rely on pure `great-docs init` → `great-docs build`"
        )
        print("  but are NOT covered by test_L2_init_creates_config or similar.\n")
    elif args.axes:
        target_axes = set(args.axes.split(","))
        filtered = [p for p in packages if target_axes & set(_dim_str(p["dimensions"]).split(","))]
        print_table(filtered, f"Packages on axes: {args.axes}")
    else:
        print_table(packages)
        print_stats(packages)


if __name__ == "__main__":
    main()
