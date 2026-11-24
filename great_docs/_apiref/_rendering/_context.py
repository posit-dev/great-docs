"""
An object's placement and rendering purpose
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import griffe as gf

    from .._settings import Settings


__all__ = ("RenderContext", "_RenderingPurpose")


@dataclass(frozen=True)
class RenderContext:
    """
    Where a prepared object appears in the generated documentation

    The aliases of an object share its prepared documentation, and each has its own
    authored name and page. Treat the object and settings referenced by this frozen
    record as read-only.
    """

    obj: gf.Object | gf.Alias
    """The prepared object, or the authored alias that wraps it"""
    authored_name: str
    """The name selected for this appearance"""
    canonical_identity: str
    """The canonical object's qualified path, shared by aliases"""
    page_path: str | None
    """
    The path of the containing QMD page, relative to the output directory

    `None` when no containing page is known, or when the page's path is absolute and
    not inside a known output directory.
    """
    level: int
    """The heading depth of this appearance"""
    contained: bool
    """Whether this appearance sits inside another object's documentation"""
    source_root: Path | None
    """The project's documentation source directory, or `None` when unknown"""
    output_root: Path | None
    """The directory the documentation is generated into, or `None` outside a build"""
    settings: Settings
    """The parser, introspection and rendering settings"""


class _RenderingPurpose(Enum):
    """The built-in context an object is rendered for: ordinary, an API page or a typing group"""

    OBJECT = auto()
    API_PAGE = auto()
    PROTOCOL = auto()
    TYPE_VARIABLE = auto()
    TYPE_ALIAS = auto()


def output_page_path(destination: str | Path | None, output_root: Path | None) -> str | None:
    """
    Express a page destination relative to the output directory

    Parameters
    ----------
    destination
        The page's destination, or `None` when no page is known.
    output_root
        The documentation output directory, or `None` outside a build.

    Returns
    -------
    :
        A relative destination unchanged, an absolute destination relative to
        `output_root`, or `None` when an absolute destination is not inside a known
        output directory. The working directory is never used as a fallback.
    """
    if destination is None:
        return None
    path = Path(destination)
    if path.is_absolute():
        if output_root is None:
            return None
        try:
            path = path.relative_to(output_root)
        except ValueError:
            return None
    return path.as_posix()
