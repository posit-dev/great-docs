"""
Authored Markdown pages published by the build
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .._website.homepage import source as homepage_source
from . import custom_pages, user_guide

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .._project.layout import Layout
    from ..config import Config

__all__ = ["find_pages", "find_pages_in"]

_PAGE_SUFFIXES = (".md", ".qmd")


def find_pages(config: Config, layout: Layout, *, report: Callable[[str], None]) -> list[Path]:
    """
    Find the authored `.qmd` and `.md` pages that the build publishes

    Paths with a part starting with `_` or `.` below their directory are left out, because
    Quarto does not render them.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    report
        Receives warnings about the user guide and custom page directories.

    Returns
    -------
    :
        The Markdown homepage source, followed by pages in the user guide, sections and
        custom page directories, in that order. Pages are sorted within each directory.
    """
    directories: list[Path] = []
    guide_dir = user_guide.find_dir(config, layout, report=report)
    if guide_dir is not None:
        directories.append(guide_dir)
    for section in cast("list[object]", config.sections or []):
        if isinstance(section, dict) and (
            directory := cast("dict[str, object]", section).get("dir")
        ):
            directories.append(layout.source_dir / str(directory))
    directories.extend(
        source.path for source in custom_pages.find_sources(config, layout, report=report)
    )

    pages = [path for path in homepage_source.find(layout)[:1] if path.suffix in _PAGE_SUFFIXES]
    for directory in directories:
        pages.extend(find_pages_in(directory))
    return pages


def find_pages_in(directory: Path) -> list[Path]:
    """
    Find documentation pages recursively in a directory

    Quarto does not render paths with a component starting with `_` or `.` below the
    directory. Exclude those paths from the results.

    Parameters
    ----------
    directory
        The directory to search recursively.

    Returns
    -------
    :
        The `.qmd` and `.md` pages sorted by path, or an empty list if `directory` is not
        a directory.
    """
    if not directory.is_dir():
        return []
    return [
        path
        for path in sorted([*directory.rglob("*.qmd"), *directory.rglob("*.md")])
        if not any(part.startswith(("_", ".")) for part in path.relative_to(directory).parts)
    ]
