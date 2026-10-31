"""
Sections: directories of authored pages that the `sections` setting publishes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from .._layout import Layout
    from ..config import Config

__all__ = ["source_dirs"]


def source_dirs(config: Config, layout: Layout) -> set[Path]:
    """
    Collect the source directories that `sections` entries publish

    Each directory published by a section belongs to that section. The user guide and custom
    pages do not also publish it.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's layout, which locates section directories.

    Returns
    -------
    :
        The resolved directory of every section entry with a `dir`.
    """
    sections = config.sections
    if not isinstance(sections, list):  # pyright: ignore[reportUnnecessaryIsInstance]
        return set()
    return {
        (layout.source_dir / section["dir"]).resolve()
        for section in sections
        if isinstance(section, dict) and isinstance(section.get("dir"), str)  # pyright: ignore[reportUnnecessaryIsInstance]
    }
