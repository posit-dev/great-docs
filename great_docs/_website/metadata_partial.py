"""
The HTML metadata partial that shapes each page's `<head>`

Quarto renders page titles, translation metadata, the Open Graph page type and the build time
from this partial. The site uses a bundled copy of Quarto's partial, so the metadata does not
depend on the installed Quarto version.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from . import i18n, page_dates, social_cards
from .seo import title as seo_title

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._layout import Layout
    from ..config import Config

__all__ = ["FILENAME", "title_element", "write"]

FILENAME = "metadata.html"
"""
Name of the partial in the bundled assets and in the Quarto project
"""

_BUNDLED = Path(__file__).parents[1] / "assets" / FILENAME


def title_element(template: object) -> str | None:
    """
    Convert the configured page-title template to a Pandoc `<title>` element

    Apply the template only to titled pages. For untitled pages, including the home page,
    Quarto leaves `$title-prefix$` unset and sets `$pagetitle$` to the site name. These pages
    therefore show only the site name.

    Parameters
    ----------
    template
        Value of `seo.title_template`, written with `{page_title}` and an optional
        `{site_name}`. Configuration values may have any type, but only strings are supported.

    Returns
    -------
    :
        The `<title>` element, or `None` unless the template is a string that contains
        `{page_title}` and excludes `$`.
    """
    if not seo_title.is_valid(template):
        return None

    titled = seo_title.apply(template, "$pagetitle$", "$title-prefix$")
    return f"<title>$if(title-prefix)${titled}$else$$pagetitle$$endif$</title>"


def write(
    quarto_config: dict[str, Any],
    config: Config,
    layout: Layout,
    *,
    report: Callable[[str], None],
) -> None:
    """
    Write the metadata partial to the build directory and register it with Quarto

    Start with the bundled partial. Add the configured SEO title template, translations for
    languages other than English, and the Open Graph page type for social cards. Include the
    site build time when `show_dates` is enabled. Write nothing when the Quarto configuration has
    no HTML format mapping.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place to list the partial in
        `format.html.template-partials`.
    config
        Project configuration.
    layout
        Project directories, including the build directory for the metadata partial.
    report
        A callback that receives a warning when SEO is enabled and the title template is
        invalid.

    Returns
    -------
    :
        Nothing.
    """
    html_format = quarto_config.get("format", {}).get("html")
    if not isinstance(html_format, dict):
        return
    html_config = cast("dict[str, Any]", html_format)

    partial = _BUNDLED.read_text(encoding="utf-8")

    if config.seo_enabled:
        title_line = title_element(config.seo_title_template)
        if title_line is None:
            report(
                "Warning: seo.title_template must be a string containing "
                "{page_title} but no '$'. Using Quarto's default page titles."
            )
        else:
            # Use a callable replacement so backslashes and `$` remain literal.
            partial = re.sub(r"<title>.*</title>", lambda _match: title_line, partial)

    meta_tag = i18n.meta_tag(config)
    if meta_tag is not None:
        # Pandoc templates require `$$` to render a literal `$`.
        partial = partial.rstrip("\n") + "\n" + meta_tag.replace("$", "$$") + "\n"

    if social_cards.applies(quarto_config, config, layout.build_dir):
        partial = partial.rstrip("\n") + "\n" + social_cards.OG_TYPE_PARTIAL + "\n"

    if config.show_dates:
        date_lines = page_dates.partial_lines(datetime.now().isoformat())
        partial = partial.rstrip("\n") + "\n" + date_lines + "\n"

    _ = (layout.build_dir / FILENAME).write_text(partial, encoding="utf-8")

    partials = cast("str | list[str]", html_config.get("template-partials", []))
    if isinstance(partials, str):
        partials = [partials]
    if FILENAME not in partials:
        partials.append(FILENAME)
    html_config["template-partials"] = partials
