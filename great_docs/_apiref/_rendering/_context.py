"""
An object's placement and rendering purpose
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import griffe as gf

    from .._settings import Settings


__all__ = ("RenderContext", "_RenderingPurpose")


@dataclass(frozen=True)
class RenderContext:
    """
    One object's appearance within generated documentation

    Freezing this record does not freeze its referenced object or settings.
    Treat semantic documentation as read-only during presentation.
    """

    obj: gf.Object | gf.Alias
    """The prepared object, or the authored alias that wraps it"""
    authored_name: str
    """The name selected for this appearance"""
    canonical_identity: str
    """The canonical object's qualified path, shared by aliases"""
    page_path: str | None
    """The output-relative page path, or `None` outside a known page"""
    level: int
    """The heading depth of this appearance"""
    contained: bool
    """Whether this appearance sits inside another object's documentation"""
    source_root: Path | None
    """The original package source root, or `None` when unavailable"""
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
