"""
Authored page directories and page metadata in the build directory

Each scan reads a page once for features that use its front matter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._content.pages import section_destination
from .page_metadata import Page

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from .._project.layout import Layout
    from ..config import Config

__all__ = ["ContentDir", "ScannedPage", "content_dirs", "scan"]


@dataclass(frozen=True)
class ContentDir:
    """A directory of authored pages in the build directory"""

    path: Path
    """The directory"""

    label: str
    """The section name shown beside its pages, such as `User Guide`"""


@dataclass(frozen=True)
class ScannedPage:
    """An authored page and the section it belongs to"""

    page: Page
    """The page as read"""

    href: str
    """
    The page's source path relative to the build directory

    Path separators are always `/`, as in `user-guide/intro.qmd`.
    """

    section: str
    """The section name shown beside the page"""


def content_dirs(config: Config, layout: Layout, *, reference: bool) -> list[ContentDir]:
    """
    List the build directory's authored page directories

    Directories appear in this order: `user-guide/`, `recipes/`, `reference/` when
    requested, then each custom section's destination. Missing directories and duplicate
    paths are excluded.

    Parameters
    ----------
    config
        The Great Docs configuration, including custom `sections`.
    layout
        The project's directories.
    reference
        Whether to include `reference/`, which contains the CLI and MCP pages at scan time.

    Returns
    -------
    :
        The directories in scan order.
    """
    build_dir = layout.build_dir
    candidates = [
        ContentDir(build_dir / "user-guide", "User Guide"),
        ContentDir(build_dir / "recipes", "Recipes"),
    ]
    if reference:
        candidates.append(ContentDir(build_dir / "reference", "Reference"))
    for section in config.sections:
        if (destination := section_destination(layout, section)) is not None:
            title = section.get("title")
            candidates.append(ContentDir(destination, str(title) if title else ""))

    dirs: list[ContentDir] = []
    seen: set[Path] = set()
    for candidate in candidates:
        # Custom sections can share built-in directories, so deduplicate by resolved path.
        resolved = candidate.path.resolve()
        if candidate.path.is_dir() and resolved not in seen:
            dirs.append(candidate)
            seen.add(resolved)
    return dirs


def scan(dirs: Iterable[ContentDir], build_dir: Path, *, skip_index: bool) -> Iterator[ScannedPage]:
    """
    Read the `.qmd` pages under each directory

    Unreadable pages and pages with invalid UTF-8 are skipped.

    Parameters
    ----------
    dirs
        The directories to scan, in order.
    build_dir
        The Quarto project directory that holds them.
    skip_index
        Whether to skip pages named `index.qmd`.

    Returns
    -------
    :
        The pages in directory order, sorted by path within each directory.
    """
    for directory in dirs:
        for path in sorted(directory.path.rglob("*.qmd")):
            if skip_index and path.name == "index.qmd":
                continue
            try:
                page = Page.make(path, build_dir)
            except (OSError, UnicodeDecodeError):
                continue
            yield ScannedPage(page, path.relative_to(build_dir).as_posix(), directory.label)
