"""
Additions to the site's Quarto configuration from a build step
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Contribution", "NavbarLink"]


@dataclass(frozen=True)
class NavbarLink:
    """A link in the site's navbar"""

    text: str
    """The label; a label that Great Docs generates in English is shown in the site's language"""

    href: str
    """The link's target, which identifies the link among the navbar's items"""


@dataclass(frozen=True)
class Contribution:
    """The navigation that a build step adds to the site"""

    navbar: tuple[NavbarLink, ...] = ()
    """Links for the left side of the navbar, in order"""
