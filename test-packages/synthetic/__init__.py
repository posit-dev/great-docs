# Great Docs Gauntlet (GDG) — synthetic test package infrastructure
#
# This module provides a spec-driven system for generating minimal, fake-but-valid
# Python packages that exercise every Great Docs code path. See SYNTHETIC_TEST_PLAN.md
# for the full design document.

from __future__ import annotations

from .catalog import ALL_PACKAGES, get_spec, get_specs_by_dimension
from .generator import generate_package

__all__ = [
    "ALL_PACKAGES",
    "generate_package",
    "get_spec",
    "get_specs_by_dimension",
]
