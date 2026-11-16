"""
Preferred page addresses for canonical links and Open Graph tags

Rendered pages receive canonical links and `og:url` tags during Quarto
rendering. Raw custom pages receive their canonical links here. Older
documentation versions use the latest version's base address for both tags.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import head

if TYPE_CHECKING:
    from .._project.repository import Repository
    from ..config import Config

FILTER = "page-url"
BASE_URL_KEY = "gd-base-url"
CANONICAL_KEY = "gd-canonical"
OG_URL_KEY = "gd-og-url"
_CANONICAL_LINK = re.compile(r"""rel=["']?canonical""")


def resolve_base_url(config: Config, repository: Repository | None) -> str | None:
    """
    Resolve the address that canonical links, sitemaps and robots files use

    Prefer `seo.canonical.base_url`, which names the preferred address when it
    differs from where the site is served. Then use `site_url`, then the GitHub
    Pages address of a GitHub repository. Other providers require an explicit address.

    Parameters
    ----------
    config
        Project configuration.
    repository
        The project's repository, if it has one.

    Returns
    -------
    :
        The address with a trailing slash, or `None` when none is known.
    """
    base_url = config.canonical_base_url or config.site_url
    if base_url:
        return base_url.rstrip("/") + "/"
    if repository is not None and repository.provider == "github":
        return f"https://{repository.namespace}.github.io/{repository.name}/"
    return None


def address(base_url: str, page_path: str) -> str:
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


def register(
    quarto_config: dict[str, Any],
    config: Config,
    base_url: str | None,
    project_dir: Path,
    *,
    og_url: bool,
) -> None:
    """
    Register canonical-link and Open Graph URL tags for rendered pages

    Generate canonical links unless they are disabled or the site's header
    includes contain one. Generate `og:url` when `og_url` is true. Register
    nothing without a base address or when neither tag is needed.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    base_url
        The site address with a trailing slash.
    project_dir
        Base directory for relative header file paths.
    og_url
        Whether pages get an `og:url` tag.
    """
    canonical = config.canonical_enabled and not head.includes_match(
        quarto_config, project_dir, _CANONICAL_LINK
    )
    if not base_url or not (canonical or og_url):
        return
    quarto_config.setdefault("filters", []).append(FILTER)
    quarto_config[BASE_URL_KEY] = base_url
    quarto_config[CANONICAL_KEY] = canonical
    quarto_config[OG_URL_KEY] = og_url


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
    tag = f'<link rel="canonical" href="{address(base_url, page_path)}">'
    return head.insert(html, tag, unless='rel="canonical"')
