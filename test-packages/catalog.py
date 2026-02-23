"""
Great Docs Gauntlet (GDG) — unified catalog for all 200 test packages.

Re-exports everything from ``synthetic.catalog``, which contains all
GDG packages in a single catalog.

>>> from catalog import ALL_PACKAGES, get_spec
>>> len(ALL_PACKAGES)
200
>>> spec = get_spec("gdtest_minimal")
>>> spec["name"]
'gdtest_minimal'
"""

from __future__ import annotations

# ── Re-export from the single synthetic catalog ────────────────────────────
from synthetic.catalog import (
    ALL_PACKAGES,
    DIMENSIONS,
    PACKAGE_DESCRIPTIONS,
    get_spec,
    get_specs_by_dimension,
)

# ── Dimension badge colors ──────────────────────────────────────────────────

AXIS_COLORS: dict[str, str] = {
    # Layout/structure axes
    "layout": "#3b82f6",  # blue
    "exports": "#8b5cf6",  # violet
    "objects": "#f59e0b",  # amber
    "docstrings": "#10b981",  # emerald
    "directives": "#ef4444",  # red
    "user_guide": "#06b6d4",  # cyan
    "landing": "#f97316",  # orange
    "extras": "#6366f1",  # indigo
    # Config/docstring axes
    "config": "#2563eb",  # blue-700
    "docstring": "#059669",  # emerald-600
    "sections": "#ea580c",  # orange-600
    "reference": "#7c3aed",  # violet-600
    "theme": "#d97706",  # amber-600
}

__all__ = [
    "ALL_PACKAGES",
    "AXIS_COLORS",
    "DIMENSIONS",
    "PACKAGE_DESCRIPTIONS",
    "get_spec",
    "get_specs_by_dimension",
]
