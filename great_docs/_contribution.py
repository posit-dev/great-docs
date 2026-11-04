"""
Additions to the site's Quarto configuration from a build step
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

__all__ = ["Contribution", "NavbarLink", "Sidebar", "SidebarItem"]


@dataclass(frozen=True)
class NavbarLink:
    """A link in the site's navbar"""

    text: str
    """The label; a label that Great Docs generates in English is shown in the site's language"""

    href: str
    """The link's target, which identifies the link among the navbar's items"""

    before: str | None = None
    """The `href` of the item the link goes in front of; the link goes last without one"""


SidebarItem: TypeAlias = str | dict[str, Any]
"""A sidebar entry: a page path, a labelled link, or a section with its own contents"""


@dataclass(frozen=True)
class Sidebar:
    """A sidebar selected by its `id` in a page's `sidebar` front matter"""

    id: str
    """The name pages use to select the sidebar, unique among the site's sidebars"""

    title: str
    """The heading above the entries"""

    contents: tuple[SidebarItem, ...]
    """The entries, in order"""


@dataclass(frozen=True)
class Contribution:
    """Navigation, resources and render exclusions supplied by a build step"""

    navbar: tuple[NavbarLink, ...] = ()
    """Links for the left side of the navbar, in order"""

    sidebars: tuple[Sidebar, ...] = ()
    """Sidebars that replace those with the same `id` or follow the existing sidebars"""

    resources: tuple[str, ...] = ()
    """Files and globs that Quarto copies into the site as they are, relative to the project"""

    render_excludes: tuple[str, ...] = ()
    """Files and globs that Quarto must not render, relative to the project"""
