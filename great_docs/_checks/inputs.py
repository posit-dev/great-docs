"""
Shared file discovery for link checking and proofreading

Find authored documentation pages, the package's `README.md` and Python source files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._content import authored
from .._layout import PACKAGE_DIRS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .._layout import Layout
    from ..config import Config

__all__ = ["find_modules", "find_pages"]


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
    pages = authored.find_pages(config, layout, report=report)
    readme = layout.package_root / "README.md"
    if readme.exists() and readme not in pages:
        pages.append(readme)
    return pages


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
