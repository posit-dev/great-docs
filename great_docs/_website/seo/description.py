"""
Search descriptions declared in website headers and raw HTML pages
"""

from __future__ import annotations

import re
from html import escape, unescape
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..._content import metadata
from .. import head

if TYPE_CHECKING:
    from ...config import Config

_HEADER_DESCRIPTION = re.compile(r"""<meta\s+name=["']?description""")
_HEADER_DESCRIPTION_CONTENT = re.compile(
    r"""<meta\s+name=["']?description["']?\s+content=(?:"([^"]*)"|'([^']*)')"""
)


def applies(quarto_config: dict[str, Any], config: Config, project_dir: Path) -> bool:
    """
    Check whether pages get a generated `description-meta`

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`.
    config
        Project configuration.
    project_dir
        Base directory for relative header file paths.

    Returns
    -------
    :
        `True` when SEO is enabled and the site's header includes declare no
        description.
    """
    return config.seo_enabled and not head.includes_match(
        quarto_config, project_dir, _HEADER_DESCRIPTION
    )


def header_description(quarto_config: dict[str, Any], project_dir: Path) -> str | None:
    """
    Read the description that the site's header includes declare

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`.
    project_dir
        Base directory for relative header file paths.

    Returns
    -------
    :
        The description as a metadata value, or `None` when the header
        includes declare none or it has no readable `content`.
    """
    includes = head.site_includes(quarto_config)
    match = head.search_includes(includes, project_dir, _HEADER_DESCRIPTION_CONTENT)
    if match is None:
        return None
    text = unescape(match.group(1) or match.group(2) or "").strip()
    return metadata.as_metadata(text) if text else None


def add_to_raw_page(html: str, default: str | None) -> str:
    """
    Add the default description to a raw custom page

    Parameters
    ----------
    html
        The page source.
    default
        The site's default description as plain text.

    Returns
    -------
    :
        The page with the tag added, or unchanged when it has a description
        already, has no `<head>`, or `default` is `None`.
    """
    if not default:
        return html
    tag = f'<meta name="description" content="{escape(default, quote=True)}">'
    return head.insert(html, tag, unless='name="description"')
