"""
The latest GitHub release beside the site title in the navbar

A navbar with a text title shows a version badge with the release date
in its hover text. A navbar with only a logo shows the version and date
in a tooltip. Quarto cannot add attributes to the logo link, so the
tooltip HTML travels in a header meta tag that `navbar-widgets.js` copies
onto the link.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, cast

from ..._translations import translate
from .. import quarto_yml
from ..head import raw_inline

_LOGO_TOOLTIP = "gd-logo-tooltip"


@dataclass(frozen=True)
class Release:
    """A published release of the package"""

    version: str
    """The version without a leading `v`"""

    date: str | None
    """The publication date as `YYYY-MM-DD`, if known"""

    @classmethod
    def make(cls, release: dict[str, Any]) -> Release | None:
        """
        Read a release from a GitHub API release entry

        Parameters
        ----------
        release
            An entry with `tag_name` and, optionally, an ISO 8601
            `published_at`.

        Returns
        -------
        :
            The release, or `None` if the tag is empty after removing leading `v` characters.
        """
        version = str(release.get("tag_name") or "").lstrip("v")
        if not version:
            return None
        published = str(release.get("published_at") or "")
        return cls(version=version, date=published[:10] or None)


def add_to_navbar(quarto_config: dict[str, Any], release: Release | None, language: str) -> None:
    """
    Show the release in a navbar badge or a logo tooltip

    Append the version badge to a text title. For a logo without a title, add
    header metadata for the release tooltip.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    release
        The release to show, or `None` to leave the configuration unchanged.
    language
        Language code for the "Released {date}" hover text.
    """
    if release is None:
        return

    website = cast("dict[str, Any]", quarto_config.setdefault("website", {}))
    navbar = cast("dict[str, Any]", website.setdefault("navbar", {}))
    site_title = website.get("title")
    version = html.escape(release.version)
    released = (
        translate("logo_tooltip_released", language).replace("{date}", release.date)
        if release.date
        else None
    )

    title = navbar.get("title", site_title)
    if title:
        hover = f' title="{html.escape(released)}"' if released else ""
        badge = f'<span class="version-badge"{hover}>v{version}</span>'
        navbar["title"] = f"{title} {raw_inline(badge)}"
    elif navbar.get("logo"):
        tooltip = f"<code>v{version}</code>"
        if released:
            tooltip += f"<br>{html.escape(released)}"
        meta = f'<meta name="{_LOGO_TOOLTIP}" content="{html.escape(tooltip)}">'
        quarto_yml.includes(quarto_config, "include-in-header").append({"text": meta})
