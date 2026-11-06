"""
The homepage hero: logo, name, tagline and badges above the page body

The hero appears when `hero.enabled` is true. Unless explicitly disabled, it also appears
when the project has a hero logo file or its README has a centred block with a logo or tagline.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import TYPE_CHECKING, Any

from ..._content import publish
from ..._manifest import Manifest
from .. import branding
from ..scripts import script_tag
from .readme import Badge, HeroElements, extract_hero_elements

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from ..._content.pages import PageMap
    from ..._layout import Layout
    from ...config import Config

__all__ = ["Hero", "find", "render"]


@dataclass(frozen=True, kw_only=True)
class Hero:
    """The hero content that comes from the README or the badge settings"""

    badges: list[Badge]
    """The badges to show, from the README or from `hero.badges`"""

    logo_url: str | None = None
    """The logo image of the README's centred block"""

    tagline: str | None = None
    """The tagline of the README's centred block"""

    body: str | None = None
    """The README without its badges, or `None` when the hero took nothing from it"""


def find(config: Config, source_dir: Path, readme: str | None) -> Hero | None:
    """
    Decide whether the homepage has a hero, and take its content from the README

    With `hero.badges: auto`, the README's badges move into the hero.

    Parameters
    ----------
    config
        The Great Docs configuration.
    source_dir
        The documentation source directory, which may contain a hero logo file.
    readme
        The homepage Markdown without front matter, or `None` for a page that is not a README.

    Returns
    -------
    :
        The hero's README content or configured badges, or `None` if the homepage has no hero.
    """
    if config.hero_explicitly_disabled:
        return None

    elements = HeroElements(badges=[], body=readme or "")
    badges: list[Badge] = []
    if config.hero_badges == "auto" and readme:
        elements = extract_hero_elements(readme)
        badges = elements.badges
    elif isinstance(config.hero_badges, list):
        badges = [_configured_badge(entry) for entry in config.hero_badges]

    from_readme = elements.logo_url is not None or elements.tagline is not None
    if (
        not config.hero_enabled
        and not from_readme
        and branding.detect_hero_logo(source_dir) is None
    ):
        return None

    return Hero(
        badges=badges,
        logo_url=elements.logo_url,
        tagline=elements.tagline,
        body=elements.body if elements.badges else None,
    )


def _configured_badge(entry: Mapping[str, Any]) -> Badge:
    """
    Read a badge from the `hero.badges` list

    Parameters
    ----------
    entry
        A list entry with `alt`, `img` and `url` keys, any of which may be missing.

    Returns
    -------
    :
        The badge, with `""` for a missing key.
    """
    return Badge(
        alt=str(entry.get("alt") or ""),
        img=str(entry.get("img") or ""),
        url=str(entry.get("url") or ""),
    )


def render(
    hero: Hero,
    config: Config,
    layout: Layout,
    *,
    metadata: Manifest,
    package_name: str | None,
    pages: PageMap,
) -> str:
    """
    Render the hero as HTML

    The logo is the first available value from `hero.logo`, a hero logo file, `logo`, a navbar
    logo file and the README's logo. Its path is rewritten for the homepage, and a local file
    is copied into the layout's build directory.

    Parameters
    ----------
    hero
        The hero content from the README or configured badges.
    config
        The Great Docs configuration.
    layout
        The documentation source directory to search for logos, the configuration
        path for resolving logo references and the build directory for local logo
        copies and URLs relative to `index.qmd`.
    metadata
        The package metadata, whose description is the default tagline.
    package_name
        The package name, used as the default hero name.
    pages
        The published paths of the authored pages.

    Returns
    -------
    :
        The hero `<div>`, followed by the starfield script when `hero.starfield` is on, or
        `""` when the hero has nothing to show.
    """
    logo = config.hero_logo
    if logo is None:
        logo = branding.detect_hero_logo(layout.source_dir)
    if logo is None:
        logo = config.logo
    if logo is None:
        logo = branding.detect_logo(layout.source_dir, package_name)
    if logo is None and hero.logo_url:
        logo = hero.logo_url

    logo_html = ""
    if logo:
        height = config.hero_logo_height
        if isinstance(logo, dict):
            light = logo.get("light")
            dark = logo.get("dark")
            alt = escape(logo.get("alt", "Logo"))
            if light and dark and light != dark:
                logo_html = (
                    f'<img src="{escape(light)}" alt="{alt}" class="gd-hero-logo gd-only-light" style="max-height:{height}" />\n'
                    f'<img src="{escape(dark)}" alt="{alt}" class="gd-hero-logo gd-only-dark" style="max-height:{height}" />'
                )
            elif light:
                logo_html = f'<img src="{escape(light)}" alt="{alt}" class="gd-hero-logo" style="max-height:{height}" />'
        elif isinstance(logo, str):
            logo_html = f'<img src="{escape(logo)}" alt="Logo" class="gd-hero-logo" style="max-height:{height}" />'
        logo_html = publish.rebase_references(
            logo_html,
            layout.config_path,
            layout.build_dir / "index.qmd",
            layout=layout,
            pages=pages,
        )

    name = config.hero_name
    if name is None:
        name = metadata.get("name") or package_name
    name_html = f'<p class="gd-hero-name">{escape(str(name), quote=False)}</p>' if name else ""

    tagline = config.hero_tagline
    if tagline is None:
        tagline = hero.tagline or metadata.get("description", "")
    tagline_html = (
        f'<p class="gd-hero-tagline">{escape(tagline, quote=False)}</p>' if tagline else ""
    )

    badges_html = ""
    if hero.badges:
        items: list[str] = []
        for badge in hero.badges:
            image = f'<img alt="{escape(badge.alt)}" src="{escape(badge.img)}" />'
            items.append(f'<a href="{escape(badge.url)}">{image}</a>' if badge.url else image)
        badges_html = '<div class="gd-hero-badges">\n' + "\n".join(items) + "\n</div>"

    parts = [part for part in (logo_html, name_html, tagline_html, badges_html) if part]
    if not parts:
        return ""

    starfield = '<canvas id="gd-starfield"></canvas>\n' if config.hero_starfield else ""
    html = '<div class="gd-hero">\n' + starfield + "\n".join(parts) + "\n</div>\n\n"
    if config.hero_starfield:
        # The script runs after the canvas is in the DOM
        html += script_tag("starfield.js") + "\n\n"
    return html
