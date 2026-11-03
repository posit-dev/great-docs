"""
The site-wide files that guide search-engine crawlers: `sitemap.xml` and `robots.txt`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import robots, sitemap

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ...config import Config

__all__ = ["write"]


def write(
    site_dir: Path,
    config: Config,
    base_url: str | None,
    *,
    report: Callable[[str], None],
) -> None:
    """
    Write `sitemap.xml` and `robots.txt` to the rendered site when SEO is enabled

    Both files describe the rendered site. Run this after the last change to the site
    directory.

    Parameters
    ----------
    site_dir
        The rendered site.
    config
        Project configuration.
    base_url
        The site's canonical address, with a trailing slash, or `None` when it is unknown.
    report
        A callback that receives progress and skip messages. Disabling SEO or an individual
        file produces no skip message.

    Returns
    -------
    :
        Nothing.
    """
    if not config.seo_enabled:
        return

    report("\n🔍 Generating SEO files...")
    sitemap.write(site_dir, config, base_url, report=report)
    robots.write(site_dir, config, base_url, report=report)
