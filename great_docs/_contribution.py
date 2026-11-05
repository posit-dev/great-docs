"""
Additions to the site's Quarto configuration from a build step
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

__all__ = [
    "Contribution",
    "InlineData",
    "NavbarLink",
    "NavbarLinkKind",
    "Sidebar",
    "SidebarItem",
]

NavbarLinkKind: TypeAlias = Literal["generated", "authored", "user_guide"]
"""
What a navbar link opens, which decides where it goes and which items it yields to

- `generated`: a page Great Docs generates, such as the changelog or the tags index. The
  link yields to an item with the same `href` or one in the same Great Docs item, such as
  any page under `reference/` for Reference. It precedes the item named by `before`, or
  goes last.
- `authored`: a section or custom page. The link yields only to an item with the same
  `href`. It follows the item labelled `after`, else precedes the Reference item, else
  goes last.
- `user_guide`: the user guide. The link yields only to an item with the same `href`. It
  precedes the Reference item, else goes first.
"""


@dataclass(frozen=True)
class NavbarLink:
    """A link in the site's navbar"""

    text: str
    """The label; a label that Great Docs generates in English is shown in the site's language"""

    href: str
    """The link's target, which identifies the link among the navbar's items"""

    before: str | None = None
    """
    The `href` a `generated` link precedes, or `None` to place the link last
    """

    kind: NavbarLinkKind = "generated"
    """The link category that determines its placement and duplicate rules"""

    after: str | None = None
    """
    The label of the item an `authored` link follows

    Great Docs' own items, such as Reference, match either their English or translated
    label. Other items match their label as written.
    """

    def __post_init__(self) -> None:
        """
        Reject a placement field that the link's kind ignores

        Raises
        ------
        ValueError
            If `before` is set for a kind other than `generated`, or `after` for a kind
            other than `authored`.
        """
        if self.before is not None and self.kind != "generated":
            raise ValueError(f"A {self.kind} link takes no `before` placement: {self.href}")
        if self.after is not None and self.kind != "authored":
            raise ValueError(f"A {self.kind} link takes no `after` placement: {self.href}")


SidebarItem: TypeAlias = str | dict[str, Any]
"""A sidebar entry: a page path, a labelled link, or a section with its own contents"""


@dataclass(frozen=True)
class Sidebar:
    """A sidebar selected by its `id` in a page's `sidebar` front matter"""

    id: str
    """The name pages use to select the sidebar, unique among the site's sidebars"""

    title: str | None
    """The heading above the entries, or `None` for a sidebar without one"""

    contents: tuple[SidebarItem, ...]
    """The entries, in order"""


@dataclass(frozen=True)
class InlineData:
    """Data assigned to a global on every page before the script that reads it runs"""

    name: str
    """The global's name, such as `__GD_TAGS_DATA__`"""

    data: Mapping[str, Any]
    """The value, serialisable as JSON"""

    before: str
    """The file name of the Great Docs script that reads the global, such as `page-tags.js`"""


@dataclass(frozen=True)
class Contribution:
    """Navigation, resources, render exclusions and script data supplied by a build step"""

    navbar: tuple[NavbarLink, ...] = ()
    """Links for the left side of the navbar, in order"""

    sidebars: tuple[Sidebar, ...] = ()
    """Sidebars that replace those with the same `id` or follow the existing sidebars"""

    resources: tuple[str, ...] = ()
    """Files and globs that Quarto copies into the site as they are, relative to the project"""

    render_excludes: tuple[str, ...] = ()
    """Files and globs that Quarto must not render, relative to the project"""

    inline_data: tuple[InlineData, ...] = ()
    """Data for the site's scripts, preserving the value of any global already assigned"""
