"""
Markdown companions of rendered pages

Quarto writes a `.md` companion beside each HTML page, from the page's own
document, except for drafts and `404.html`. Each page announces its
companion with `<link rel="alternate" type="text/markdown">`, and the
copy-page widget copies or opens it. Raw custom pages get no companion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import Config

FILTER = "markdown-pages"


def register(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Register the Markdown companion filter when `markdown_pages` is enabled

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    """
    if not config.markdown_pages:
        return
    filters = quarto_config.setdefault("filters", [])
    if FILTER not in filters:
        filters.append(FILTER)
