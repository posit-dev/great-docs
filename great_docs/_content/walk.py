"""File discovery under a documentation source directory"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

# Directories in a root-layout project that hold no documentation pages but
# may contain `.qmd` files or other files resembling documentation sources
# (virtual environments, installed packages and test fixtures)
NON_DOC_DIRS = frozenset(
    {"__pycache__", "node_modules", "site-packages", "build", "dist", "tests", "test"}
)


def find_files(
    root: Path,
    suffix: str,
    *,
    skip: Iterable[Path] = (),
    prune_non_doc: bool,
) -> list[Path]:
    """
    Find the files under `root` whose names end with `suffix`

    Hidden directories are never searched.

    Parameters
    ----------
    root
        Directory to search.
    suffix
        Filename suffix to match, such as `.qmd`.
    skip
        Directories to exclude with all their contents, such as the build output.
    prune_non_doc
        Whether to exclude directories without documentation when the source directory
        is the package root: those named in `NON_DOC_DIRS`, `*.egg-info` directories
        and virtual environments.

    Returns
    -------
    :
        The matching files in sorted path order.
    """
    skipped = [d.resolve() for d in skip]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        # Prune in place so `os.walk` never descends into these directories
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith(".")
            and not (
                prune_non_doc
                and (
                    d in NON_DOC_DIRS
                    or d.endswith(".egg-info")
                    or (current / d / "pyvenv.cfg").exists()
                )
            )
            and not any((current / d).resolve().is_relative_to(s) for s in skipped)
        ]
        found.extend(current / name for name in filenames if name.endswith(suffix))
    return sorted(found)
