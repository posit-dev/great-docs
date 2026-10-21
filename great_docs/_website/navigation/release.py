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
import re
from dataclasses import dataclass
from typing import Any, cast

from ..._translations import get_translation
from ..head import raw_inline

_LOGO_TOOLTIP = "gd-logo-tooltip"

# A badge from an earlier call, matched so that a repeated call replaces it
_BADGE_SUFFIX = re.compile(r' (`+)<span class="version-badge".*?\1\{=html\}$')


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
    Add the latest release beside the navbar title, or on a logo-only brand

    Replace any badge or tooltip from an earlier call. Repeated calls with
    the same release leave the configuration unchanged. With no release,
    remove both.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    release
        The release to show, or `None` to remove the badge and tooltip.
    language
        Language code for the "Released {date}" hover text.
    """
    website = cast("dict[str, Any]", quarto_config.setdefault("website", {}))
    navbar = cast("dict[str, Any]", website.setdefault("navbar", {}))
    html_config = cast(
        "dict[str, Any]", quarto_config.setdefault("format", {}).setdefault("html", {})
    )
    header = html_config.get("include-in-header", [])
    if isinstance(header, str):
        header = [header]
    header = [entry for entry in header if _LOGO_TOOLTIP not in str(entry)]
    if "include-in-header" in html_config:
        html_config["include-in-header"] = header

    site_title = website.get("title")
    title = navbar.get("title")
    if isinstance(title, str):
        title = _BADGE_SUFFIX.sub("", title)
        if title == site_title:
            del navbar["title"]
        else:
            navbar["title"] = title

    if release is None:
        return

    version = html.escape(release.version)
    released = (
        get_translation("logo_tooltip_released", language).replace("{date}", release.date)
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
        html_config["include-in-header"] = [*header, {"text": meta}]
