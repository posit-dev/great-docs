"""
Repository branding, navigation and optional counts in the navbar
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..._project.repository import Repository

WIDGET_ID = "repository-widget"
"""The mount point for the repository navigation widget"""


def navbar_item(repo: Repository, style: str, stats: Mapping[str, int] | None) -> dict[str, str]:
    """
    Build repository navigation with provider branding and optional counts

    Parameters
    ----------
    repo
        The repository and its web destinations.
    style
        `"widget"` for a dropdown; any other value for an icon link.
    stats
        Known star and fork counts. Missing values stay unknown. GitHub can
        fetch missing public counts in the browser; GitLab never does.

    Returns
    -------
    :
        A Quarto navbar item. The widget uses an inline span because Quarto
        escapes raw HTML in navbar text without a link and drops block elements.
    """
    if style != "widget":
        return {"icon": repo.provider, "href": repo.url, "aria-label": repo.label}
    attrs = {
        "id": WIDGET_ID,
        "data-provider": repo.provider,
        "data-label": repo.label,
        "data-url": repo.url,
        "data-issues-url": repo.issues_url,
        "data-requests-url": repo.requests_url,
        "data-releases-url": repo.releases_url,
        "data-fork-url": repo.fork_url,
    }
    if repo.provider == "github":
        attrs["data-public-api"] = (
            f"https://api.github.com/repos/{quote(repo.namespace, safe='')}/{quote(repo.name, safe='')}"
        )
    for key in ("stars", "forks"):
        value = stats.get(key) if stats is not None else None
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            attrs[f"data-{key}"] = str(value)
    attr_html = "".join(
        f' {key}="{html.escape(value, quote=True)}"' for key, value in attrs.items()
    )
    return {"href": repo.url, "text": f"<span{attr_html}></span>"}
