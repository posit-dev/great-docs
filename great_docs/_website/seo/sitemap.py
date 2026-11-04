"""
The `sitemap.xml` file that lists the rendered site's pages for search engines

Each page's type selects its change frequency and priority from `seo.sitemap`.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ...config import Config

__all__ = ["page_type", "write"]

_NOINDEX = re.compile(
    r"""<meta\b(?=[^>]*\bname=["']?robots\b)(?=[^>]*\bnoindex\b)[^>]*>""", re.IGNORECASE
)
"""A robots `<meta>` element that asks search engines not to index the page"""


def page_type(path: str) -> str:
    """
    Classify a rendered page for its sitemap settings

    Parameters
    ----------
    path
        Path of the HTML file relative to the site directory. Forward slashes and
        backslashes are accepted as separators.

    Returns
    -------
    :
        `"homepage"`, `"reference"`, `"user_guide"` (which includes recipes), `"changelog"`
        or `"default"`.
    """
    path = path.replace("\\", "/")

    if path == "index.html":
        return "homepage"
    elif path.startswith("reference/"):
        return "reference"
    elif path.startswith("user-guide/"):
        return "user_guide"
    elif path == "changelog.html":
        return "changelog"
    elif path.startswith("recipes/"):
        return "user_guide"
    else:
        return "default"


def write(
    site_dir: Path,
    config: Config,
    base_url: str | None,
    *,
    report: Callable[[str], None],
) -> None:
    """
    Write `sitemap.xml` for HTML pages in the rendered site

    Exclude site-relative paths that start with `_` or `.`, pages with a `noindex` robots
    directive, and redirect stubs. In a site with versions, also exclude everything under
    `v/`: the older versions and the version aliases. Sort entries by descending
    priority, then by URL. Use each file's modification time for its page's last modification
    date. Write nothing when the sitemap is disabled, the site directory does not exist, or
    no base URL is known.

    Parameters
    ----------
    site_dir
        The rendered site.
    config
        Project configuration.
    base_url
        The site's canonical address, with a trailing slash, or `None` when it is unknown.
    report
        A callback that receives progress and skip messages. Disabling the sitemap produces
        no message.

    Returns
    -------
    :
        Nothing.
    """
    if not config.sitemap_enabled:
        return

    if not site_dir.exists():
        report("   ⚠️  _site directory not found, skipping sitemap generation")
        return

    if not base_url:
        report("   ⚠️  No base URL configured, skipping sitemap generation")
        report("      Set seo.canonical.base_url in great-docs.yml or configure a GitHub repo")
        return

    changefreq = config.sitemap_changefreq
    priority = config.sitemap_priority
    versioned = config.has_versions

    entries: list[tuple[float, str, str, str]] = []
    for html_file in site_dir.rglob("*.html"):
        rel_path = html_file.relative_to(site_dir).as_posix()

        # Keep internal site files out of search-engine discovery.
        if rel_path.startswith("_") or rel_path.startswith("."):
            continue

        # Older versions canonicalise to the latest version, which is the site root.
        if versioned and rel_path.startswith("v/"):
            continue

        # `great-docs seo` recognises redirect stubs by the same refresh directive.
        html = html_file.read_text(encoding="utf-8", errors="ignore")
        if _NOINDEX.search(html) or 'http-equiv="refresh"' in html:
            continue

        kind = page_type(rel_path)

        # A directory's `index.html` is served at the directory's address.
        if rel_path == "index.html":
            loc = base_url
        elif rel_path.endswith("/index.html"):
            loc = base_url + rel_path[: -len("index.html")]
        else:
            loc = base_url + rel_path

        lastmod = datetime.fromtimestamp(html_file.stat().st_mtime).strftime("%Y-%m-%d")
        entries.append(
            (
                priority.get(kind, priority["default"]),
                loc,
                lastmod,
                changefreq.get(kind, changefreq["default"]),
            )
        )

    entries.sort(key=lambda entry: (-entry[0], entry[1]))

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for page_priority, loc, lastmod, page_changefreq in entries:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{loc}</loc>")
        xml_lines.append(f"    <lastmod>{lastmod}</lastmod>")
        xml_lines.append(f"    <changefreq>{page_changefreq}</changefreq>")
        xml_lines.append(f"    <priority>{page_priority:.1f}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")

    _ = (site_dir / "sitemap.xml").write_text("\n".join(xml_lines), encoding="utf-8")
    report(f"   Generated sitemap.xml with {len(entries)} URLs")
