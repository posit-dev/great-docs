"""
Unified catalog for all 200 synthetic test packages.

Merges the v1 suite (100 layout/structure packages) and v2 suite (100
config/docstring packages) into a single ``ALL_PACKAGES`` list, a merged
``DIMENSIONS`` dict, a merged ``PACKAGE_DESCRIPTIONS`` dict, and a single
``get_spec()`` entry-point that routes to the correct sub-catalog.

>>> from catalog import ALL_PACKAGES, get_spec
>>> len(ALL_PACKAGES)
200
>>> spec = get_spec("gdtest_minimal")
>>> spec["name"]
'gdtest_minimal'
"""

from __future__ import annotations

from typing import Any

# ── Import both sub-catalogs ────────────────────────────────────────────────
from synthetic.catalog import (
    ALL_PACKAGES as _SUITE_A_PACKAGES,
)
from synthetic.catalog import (
    DIMENSIONS as _SUITE_A_DIMENSIONS,
)
from synthetic.catalog import (
    PACKAGE_DESCRIPTIONS as _SUITE_A_DESCRIPTIONS,
)
from synthetic.catalog import (
    get_spec as _suite_a_get_spec,
)
from synthetic_v2.catalog_v2 import (
    ALL_PACKAGES as _SUITE_B_PACKAGES,
)
from synthetic_v2.catalog_v2 import (
    DIMENSIONS as _SUITE_B_DIMENSIONS,
)
from synthetic_v2.catalog_v2 import (
    PACKAGE_DESCRIPTIONS as _SUITE_B_DESCRIPTIONS,
)
from synthetic_v2.catalog_v2 import (
    get_spec as _suite_b_get_spec,
)

# ── Merged exports ──────────────────────────────────────────────────────────

ALL_PACKAGES: list[str] = _SUITE_A_PACKAGES + _SUITE_B_PACKAGES
"""All 200 synthetic package names in canonical order (suite A 1-100, suite B 101-200)."""

DIMENSIONS: dict[str, dict[str, str]] = {**_SUITE_A_DIMENSIONS, **_SUITE_B_DIMENSIONS}
"""Merged dimension codes → {axis, label} for both suites."""

PACKAGE_DESCRIPTIONS: dict[str, str] = {**_SUITE_A_DESCRIPTIONS, **_SUITE_B_DESCRIPTIONS}
"""Human-readable descriptions for all 200 packages."""

# Fast lookup set for routing
_SUITE_B_SET: set[str] = set(_SUITE_B_PACKAGES)


# ── Dimension badge colors (union of both suites) ───────────────────────────

AXIS_COLORS: dict[str, str] = {
    # Suite A axes
    "layout": "#3b82f6",  # blue
    "exports": "#8b5cf6",  # violet
    "objects": "#f59e0b",  # amber
    "docstrings": "#10b981",  # emerald
    "directives": "#ef4444",  # red
    "user_guide": "#06b6d4",  # cyan
    "landing": "#f97316",  # orange
    "extras": "#6366f1",  # indigo
    # Suite B axes
    "config": "#2563eb",  # blue-700
    "docstring": "#059669",  # emerald-600
    "sections": "#ea580c",  # orange-600
    "reference": "#7c3aed",  # violet-600
    "theme": "#d97706",  # amber-600
}


# ── Spec routing ────────────────────────────────────────────────────────────


def get_spec(name: str) -> dict[str, Any]:
    """
    Load and return the spec dict for any of the 200 packages.

    Routes to the correct sub-catalog based on package name.

    Parameters
    ----------
    name
        One of the names in :data:`ALL_PACKAGES`.

    Returns
    -------
    dict
        The full spec dict (keys: name, dimensions, files, expected, …).
    """
    if name in _SUITE_B_SET:
        return _suite_b_get_spec(name)
    return _suite_a_get_spec(name)


def get_specs_by_dimension(dim_code: str) -> list[dict[str, Any]]:
    """
    Return all specs whose ``dimensions`` list contains *dim_code*.

    Parameters
    ----------
    dim_code
        A dimension code like ``"A2"`` or ``"K5"``.

    Returns
    -------
    list[dict]
        Matched specs (loaded lazily).
    """
    results: list[dict[str, Any]] = []
    for name in ALL_PACKAGES:
        spec = get_spec(name)
        if dim_code in spec.get("dimensions", []):
            results.append(spec)
    return results
