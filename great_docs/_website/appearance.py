"""
Site appearance settings for wide layout, announcements, colours and styles

The features are the wide layout toggle, the announcement banner, the navbar and content
styles, the accent and navbar colours, and the scale-to-fit selectors. Each adds HTML include
entries to every page. Meta tags carry settings to the site's scripts, and style blocks
override CSS custom properties.
"""

from __future__ import annotations

import html
import json
import re
from typing import TYPE_CHECKING, Any

from ..contrast import ideal_text_color, parse_color
from . import quarto_yml
from .scripts import script_include

if TYPE_CHECKING:
    from ..config import Config

_LIGHT_PREFIXES = ("html.quarto-light", ":root[data-bs-theme='light']")
_DARK_PREFIXES = ("html.quarto-dark", ":root[data-bs-theme='dark']")


def register_wide_layout(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add the wide layout toggle when it is enabled

    Place the `gd-wide-layout` meta tag and scale-factor styles before `theme-init.js`,
    which reads the tag before first paint. Load `wide-layout.js` after the body at its
    position in the site's script order, or append it if missing.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    settings = config.wide_layout
    if not settings:
        return

    css_vars = (
        f"--gd-wide-content-scale:{settings['content_scale']:g};"
        f"--gd-wide-sidebar-scale:{settings['sidebar_scale']:g};"
    )
    if settings.get("prose_max_width"):
        css_vars += f"--gd-wide-prose-max:{settings['prose_max_width']};"
    header_entry = {
        "text": (
            f'<meta name="gd-wide-layout" data-default="{settings["default"]}" '
            f'data-min-viewport="{settings["min_viewport"]}">\n'
            f'<style id="gd-wide-layout-vars">:root{{{css_vars}}}</style>'
        )
    }
    quarto_yml.add_include(quarto_config, "include-in-header", header_entry, before="theme-init")
    quarto_yml.add_include(
        quarto_config,
        "include-after-body",
        script_include("wide-layout.js"),
        marker="wide-layout.js",
    )


def register(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add the configured announcement banner, colours, styles and scale-to-fit selectors

    Unconfigured features add nothing.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    _add_announcement(quarto_config, config)
    _add_navbar_style(quarto_config, config)
    _add_accent_colour(quarto_config, config)
    _add_navbar_colour(quarto_config, config)
    _add_content_style(quarto_config, config)
    _add_scale_to_fit(quarto_config, config)


def _add_announcement(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add the announcement settings and place its script first after the body

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    announcement = config.announcement
    if not announcement:
        return

    # Escape HTML for the attribute; `getAttribute()` decodes it back to HTML.
    content = html.escape(_inline_markdown_to_html(announcement["content"]))
    dismissable = "true" if announcement.get("dismissable", True) else "false"
    meta = (
        f'<meta name="gd-announcement"'
        f' data-content="{content}"'
        f' data-type="{html.escape(announcement.get("type", "info"))}"'
        f' data-dismissable="{dismissable}"'
        f' data-url="{html.escape(announcement.get("url") or "")}"'
        f' data-style="{html.escape(announcement.get("style") or "")}"'
        f' data-position="{html.escape(announcement.get("position", "above-navbar"))}">'
    )
    quarto_yml.add_include(quarto_config, "include-in-header", {"text": meta})

    after_body = quarto_yml.includes(quarto_config, "include-after-body")
    after_body.insert(0, script_include("announcement-banner.js"))


def _inline_markdown_to_html(text: str) -> str:
    """
    Convert inline Markdown code, bold, italic and links to HTML

    Parameters
    ----------
    text
        The announcement text.

    Returns
    -------
    :
        The announcement text with inline Markdown replaced by HTML elements.
    """
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:inherit">\1</a>', text)


def _add_navbar_style(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add the navbar gradient preset and the script that applies it

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    preset = config.navbar_style
    if not preset:
        return
    meta = f'<meta name="gd-navbar-style" data-preset="{html.escape(preset)}">'
    quarto_yml.add_include(quarto_config, "include-in-header", {"text": meta})
    quarto_yml.add_include(
        quarto_config,
        "include-after-body",
        script_include("navbar-style.js"),
        marker="navbar-style",
    )


def _add_accent_colour(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add a style block that sets the accent colour for the light and dark themes

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    accent = config.accent_color
    if not accent:
        return
    rules: list[str] = []
    for mode, selector in (
        ("light", ":root, html.quarto-light, :root[data-bs-theme='light']"),
        ("dark", "html.quarto-dark, :root[data-bs-theme='dark']"),
    ):
        colour = accent.get(mode)
        if colour:
            rules.append(f"{selector} {{\n    --gd-accent: {html.escape(colour)};\n}}")
    if not rules:
        return
    style = "<style>\n/* Great Docs: accent_color overrides */\n" + "\n".join(rules) + "\n</style>"
    quarto_yml.add_include(quarto_config, "include-after-body", {"text": style})


def _add_navbar_colour(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add a solid navbar colour for each configured light or dark theme

    Use black or white for navbar text and controls, whichever contrasts more with the
    background. Skip colours that cannot be parsed.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration. `navbar_color` is unset when `navbar_style` is set.

    Returns
    -------
    :
    """
    colours = config.navbar_color
    if not colours:
        return
    rules: list[str] = []
    for mode, prefixes in (("light", _LIGHT_PREFIXES), ("dark", _DARK_PREFIXES)):
        background = colours.get(mode)
        if not background:
            continue
        try:
            rules.append(_navbar_colour_rules(background, prefixes))
        except ValueError:
            continue
    if not rules:
        return
    style = "<style>\n/* Great Docs: navbar_color overrides */\n" + "\n".join(rules) + "\n</style>"
    quarto_yml.add_include(quarto_config, "include-after-body", {"text": style})


def _navbar_colour_rules(background: str, prefixes: tuple[str, str]) -> str:
    """
    Build CSS for a solid navbar background and contrasting controls in one theme

    Parameters
    ----------
    background
        The navbar's background colour, as a hex code or CSS colour name.
    prefixes
        The two selectors that match the theme on the root element.

    Returns
    -------
    :
        The CSS rules for the navbar's colours and controls.

    Raises
    ------
    ValueError
        If `background` cannot be parsed as a colour.
    """
    r, g, b = parse_color(background)
    bg_hex = f"#{r:02x}{g:02x}{b:02x}"
    text_hex = ideal_text_color(background)
    if text_hex.lower() in ("#ffffff", "#fff", "white"):
        # Light controls on a dark background
        hover_bg = "rgba(255, 255, 255, 0.15)"
        border_col = "rgba(255, 255, 255, 0.15)"
        btn_bg = "rgba(255, 255, 255, 0.08)"
        btn_border = "rgba(255, 255, 255, 0.15)"
        btn_hover_bg = "rgba(255, 255, 255, 0.12)"
        btn_hover_border = "rgba(255, 255, 255, 0.25)"
        active_underline = "rgba(255, 255, 255, 0.75)"
        toggler_stroke = "%23e0e0e0"
    else:
        # Dark controls on a light background
        hover_bg = "rgba(0, 0, 0, 0.08)"
        border_col = "rgba(0, 0, 0, 0.08)"
        btn_bg = "rgba(0, 0, 0, 0.06)"
        btn_border = "rgba(0, 0, 0, 0.15)"
        btn_hover_bg = "rgba(0, 0, 0, 0.10)"
        btn_hover_border = "rgba(0, 0, 0, 0.25)"
        active_underline = "rgba(0, 0, 0, 0.45)"
        toggler_stroke = "rgba(0,0,0,0.65)"

    # Append each suffix to every prefix. Joining prefixes first would leave a bare root
    # selector and apply the navbar background to `<html>`, producing grey bars behind
    # the blended homepage in Firefox (issue #230).
    def sel(*suffixes: str) -> str:
        return ",\n".join(prefix + suffix for suffix in suffixes for prefix in prefixes)

    return f"""{sel("")} {{
    --gd-navbar-bg: {bg_hex};
    --gd-navbar-text: {text_hex};
}}
{sel(" .navbar")} {{
    background: {bg_hex} !important;
    border-bottom: 1px solid {border_col};
}}
{sel(" .navbar .navbar-title", " .navbar .nav-link")} {{
    color: {text_hex} !important;
}}
{sel(" .navbar .nav-link:hover")} {{
    background-color: {hover_bg} !important;
    color: {text_hex} !important;
}}
{sel(" .navbar .nav-item:has(#repository-widget) .nav-link:hover")} {{
    background-color: transparent !important;
}}
{sel(" .navbar .nav-link.active")} {{
    text-decoration-color: {active_underline} !important;
}}
{sel(" .navbar .dark-mode-toggle", " #quarto-search .aa-DetachedSearchButton")} {{
    background: {btn_bg};
    border-color: {btn_border};
    color: {text_hex};
}}
{sel(" .navbar .dark-mode-toggle:hover", " #quarto-search .aa-DetachedSearchButton:hover")} {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{sel(" .navbar .gh-widget-trigger")} {{
    background: {btn_bg};
    border-color: {btn_border};
    color: {text_hex};
}}
{sel(" .navbar .gh-widget-trigger:hover")} {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{sel(" .navbar .quarto-navbar-tools button", " .navbar .quarto-navbar-tools .quarto-navigation-tool")} {{
    background: {btn_bg};
    border-color: {btn_border};
    color: {text_hex};
}}
{sel(" .navbar .quarto-navbar-tools button:hover", " .navbar .quarto-navbar-tools .quarto-navigation-tool:hover")} {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{sel(" .navbar .nav-item.compact .nav-link", " .navbar .gd-navbar-icon")} {{
    background: {btn_bg};
    border: 1px solid {btn_border};
    border-radius: 6px;
    color: {text_hex};
}}
{sel(" .navbar .nav-item.compact .nav-link:hover", " .navbar .gd-navbar-icon:hover")} {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{sel(" .navbar .navbar-toggler-icon")} {{
    background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'%3e%3cpath stroke='{toggler_stroke}' stroke-linecap='round' stroke-miterlimit='10' stroke-width='2' d='M4 7h22M4 15h22M4 23h22'/%3e%3c/svg%3e") !important;
}}
{sel(" .navbar .bi", " .navbar .aa-SubmitIcon", " .navbar .aa-SearchIcon", " .navbar .aa-DetachedSearchButtonIcon", " .navbar .aa-DetachedSearchButtonIcon svg")} {{
    color: {text_hex} !important;
    fill: {text_hex} !important;
}}
{sel(" .navbar .version-badge")} {{
    color: {text_hex};
    opacity: 0.75;
    background-color: {btn_bg};
}}"""


def _add_content_style(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add the content-area gradient preset and the script that applies it

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    style = config.content_style
    if not style:
        return
    meta = (
        f'<meta name="gd-content-style" data-preset="{html.escape(style["preset"])}"'
        f' data-pages="{html.escape(style["pages"])}">'
    )
    quarto_yml.add_include(quarto_config, "include-in-header", {"text": meta})
    quarto_yml.add_include(
        quarto_config,
        "include-after-body",
        script_include("content-style.js"),
        marker="content-style",
    )


def _add_scale_to_fit(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add selectors and the minimum scale for elements that shrink to fit the page width

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    selectors = config.scale_to_fit
    if not selectors:
        return
    min_scale = config.scale_to_fit_min_scale
    min_scale_attr = f' data-min-scale="{min_scale}"' if min_scale else ""
    meta = (
        f'<meta name="gd-scale-to-fit" data-selectors="{html.escape(json.dumps(selectors))}"'
        f"{min_scale_attr}>"
    )
    quarto_yml.add_include(quarto_config, "include-in-header", {"text": meta})
