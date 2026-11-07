"""
Shared file discovery for link checking and proofreading

Find authored documentation pages, the package's `README.md` and Python source files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._content import authored
from .._layout import PACKAGE_DIRS

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from .._layout import Layout
    from ..config import Config

__all__ = ["expand_directories", "find_modules", "find_pages", "find_pages_in"]


def find_pages(config: Config, layout: Layout, *, report: Callable[[str], None]) -> list[Path]:
    """
    Find authored documentation pages and the package README

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's paths.
    report
        Receives warnings about the user guide and custom page directories.

    Returns
    -------
    :
        The authored `.qmd` and `.md` pages published by the build, in order: the homepage
        source, then pages in the user guide, sections and custom page directories.
        An existing `README.md` at the package root is appended unless already included.
    """
    return _with_readme(authored.find_pages(config, layout, report=report), layout)


def find_pages_in(directory: Path, layout: Layout) -> list[Path]:
    """
    Find documentation pages recursively and include the package README

    Parameters
    ----------
    directory
        The documentation directory, absolute or relative to the package root.
    layout
        The project's paths.

    Returns
    -------
    :
        The `.qmd` and `.md` pages under `directory`, sorted by path. Paths with a
        component starting with `_` or `.` below `directory` are excluded. An existing
        `README.md` at the package root is appended unless already included.
    """
    return _with_readme(authored.find_pages_in(layout.package_root / directory), layout)


def expand_directories(paths: Iterable[Path]) -> list[Path]:
    """
    Expand directory paths into documentation pages

    Parameters
    ----------
    paths
        Files and directories named on the command line.

    Returns
    -------
    :
        The paths in their original order, with each directory replaced by its `.qmd`
        and `.md` pages, sorted by path. Paths with a component starting with `_` or
        `.` below each directory are excluded. File paths are unchanged.
    """
    return [
        file
        for path in paths
        for file in (authored.find_pages_in(path) if path.is_dir() else [path])
    ]


def find_modules(layout: Layout, module: str) -> list[Path]:
    """
    Find Python source files for an importable module in the project

    Parameters
    ----------
    layout
        The project's paths.
    module
        The importable module name, with dots separating nested directories, as in
        `firebird.base`.

    Returns
    -------
    :
        All `.py` files under the first matching module directory, or an empty list if
        none matches. As in the build, the search checks the package root first, then
        its `src/`, `python/` and `lib/` directories.
    """
    for root in (layout.package_root, *(layout.package_root / name for name in PACKAGE_DIRS)):
        module_dir = root.joinpath(*module.split("."))
        if module_dir.is_dir():
            return list(module_dir.rglob("*.py"))
    return []


def _with_readme(pages: list[Path], layout: Layout) -> list[Path]:
    """
    Append the package README if it exists and is not already included

    Parameters
    ----------
    pages
        The pages to extend in place.
    layout
        The project's paths.

    Returns
    -------
    :
        The same list, extended in place with `README.md` from the package root if the
        file exists and is not already included.
    """
    readme = layout.package_root / "README.md"
    if readme.exists() and readme not in pages:
        pages.append(readme)
    return pages
