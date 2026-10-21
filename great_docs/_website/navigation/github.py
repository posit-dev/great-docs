"""
The GitHub entry on the right of the navbar

The widget style shows live star and fork counts with a dropdown of repository
links. The icon style shows a plain GitHub icon linking to the repository.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

WIDGET_ID = "github-widget"
"""Element id that `github-widget.js` mounts the widget on"""


def navbar_item(
    repo_url: str,
    owner: str | None,
    repo: str | None,
    style: str,
    stats: Mapping[str, int] | None,
) -> dict[str, str]:
    """
    Build the navbar entry for the repository

    Quarto renders navbar text as inline Markdown when the item has an
    `href`. Without a link, it escapes the HTML. The widget is therefore an
    inline `<span>`, because inline Markdown drops block elements such as
    `<div>`.

    Parameters
    ----------
    repo_url
        URL of the repository.
    owner
        Repository owner, required for the widget.
    repo
        Repository name, required for the widget.
    style
        `"widget"` for the widget, anything else for the icon.
    stats
        Star and fork counts under the keys `stars` and `forks`, embedded so
        the widget can skip the GitHub API. Without them, the widget fetches
        the counts in the browser.

    Returns
    -------
    :
        A Quarto navbar item: the widget when `style` is `"widget"` and both
        `owner` and `repo` are given, otherwise a GitHub icon link.
    """
    if style != "widget" or not owner or not repo:
        return {"icon": "github", "href": repo_url}

    attrs = {"id": WIDGET_ID, "data-owner": owner, "data-repo": repo}
    if stats:
        attrs["data-stars"] = str(stats["stars"])
        attrs["data-forks"] = str(stats["forks"])
    attr_html = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in attrs.items())
    return {"href": repo_url, "text": f"<span{attr_html}></span>"}


def set_navbar_item(navbar: dict[str, Any], item: dict[str, str]) -> None:
    """
    Put the repository entry on the right of the navbar

    Parameters
    ----------
    navbar
        The `website.navbar` mapping of the Quarto configuration, modified
        in place.
    item
        The entry from `navbar_item`. It replaces every GitHub icon or widget
        entry already on the right, including one left by an earlier build,
        or is appended after the other entries when there is none.
    """
    right: list[Any] = navbar.setdefault("right", [])
    found = False
    for i, entry in enumerate(right):
        if not isinstance(entry, dict):
            continue
        fields = cast("dict[str, Any]", entry)
        if fields.get("icon") == "github" or WIDGET_ID in str(fields.get("text", "")):
            right[i] = item
            found = True
    if not found:
        right.append(item)
