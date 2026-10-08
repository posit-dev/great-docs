"""
Canonical links that point search engines at the preferred address of a page

Rendered pages get their link from the `canonical` Quarto filter, which reads
the base address from `_quarto.yml`. Raw custom pages skip Quarto and get theirs
here. Older documentation versions point at the matching page of the latest
version with a script, because their build never sees the latest address.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from . import head

if TYPE_CHECKING:
    from ...config import Config

FILTER = "canonical"
BASE_URL_KEY = "gd-canonical-base-url"


def resolve_base_url(
    config: Config, github_owner: str | None, github_repo: str | None
) -> str | None:
    """
    Resolve the address that canonical links, sitemaps and robots files use

    Prefer `seo.canonical.base_url`, which names the preferred address when it
    differs from where the site is served. Then use `site_url`, then the GitHub
    Pages address of the repository.

    Parameters
    ----------
    config
        Project configuration.
    github_owner
        Owner of the project's GitHub repository, if it has one.
    github_repo
        Name of the project's GitHub repository, if it has one.

    Returns
    -------
    :
        The address with a trailing slash, or `None` when none is known.
    """
    base_url = config.canonical_base_url or config.site_url
    if base_url:
        return base_url.rstrip("/") + "/"
    if github_owner and github_repo:
        return f"https://{github_owner}.github.io/{github_repo}/"
    return None


def page_url(base_url: str, page_path: str) -> str:
    """
    Build the address of a page, mapping an `index.html` to its directory

    Parameters
    ----------
    base_url
        The site address with a trailing slash.
    page_path
        The page's path relative to the site root.

    Returns
    -------
    :
        The page's address.
    """
    if page_path == "index.html" or page_path.endswith("/index.html"):
        page_path = page_path.removesuffix("index.html")
    return base_url + page_path


def register(quarto_config: dict, config: Config, base_url: str | None) -> None:
    """
    Register the filter that adds a canonical link to each rendered page

    Register nothing when canonical links are disabled or `base_url` is empty.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    base_url
        The site address with a trailing slash.
    """
    if not config.canonical_enabled or not base_url:
        return
    filters = quarto_config.setdefault("filters", [])
    if FILTER not in filters:
        filters.append(FILTER)
    quarto_config[BASE_URL_KEY] = base_url


def unregister(quarto_config: dict) -> None:
    """
    Remove the filter and its base address from a `_quarto.yml` mapping

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    """
    filters = quarto_config.get("filters")
    if isinstance(filters, list):
        quarto_config["filters"] = [name for name in filters if name != FILTER]
    quarto_config.pop(BASE_URL_KEY, None)


def add_to_raw_page(html: str, config: Config, base_url: str | None, page_path: str) -> str:
    """
    Add a canonical link to a raw custom page

    Leave the page unchanged when canonical links are disabled, `base_url` is
    empty, the page has a canonical link already, or it has no `<head>`.

    Parameters
    ----------
    html
        The page source.
    config
        Project configuration.
    base_url
        The site address with a trailing slash.
    page_path
        The page's path relative to the site root.

    Returns
    -------
    :
        The page with the link added.
    """
    if not config.canonical_enabled or not base_url:
        return html
    tag = f'<link rel="canonical" href="{page_url(base_url, page_path)}">'
    return head.insert(html, tag, unless='rel="canonical"')


def latest_version_script(site_url: str, version_segment: str) -> str:
    """
    Build the script that points a page of an older version at the latest one

    The script runs in the browser, so it adds the link from the page's own
    location: it replaces `<site path>/v/<version>/` with `<site path>/` and maps
    a trailing `index.html` to its directory.

    Parameters
    ----------
    site_url
        The site address, with or without a path or trailing slash.
    version_segment
        The version's directory name under `v/`.

    Returns
    -------
    :
        A `<script>` element.
    """
    site = urlsplit(site_url)
    origin = f"{site.scheme}://{site.netloc}"
    root = site.path.rstrip("/")
    return (
        "<script>"
        'document.addEventListener("DOMContentLoaded",function(){'
        "var path=window.location.pathname;"
        f'var prefix="{root}/v/{version_segment}/";'
        f'if(path.startsWith(prefix)){{path="{root}/"+path.slice(prefix.length)}}'
        'path=path.replace(/(^|\\/)index\\.html$/,"$1");'
        'var link=document.createElement("link");'
        'link.rel="canonical";'
        f'link.href="{origin}"+path;'
        "document.head.appendChild(link)"
        "});"
        "</script>"
    )
