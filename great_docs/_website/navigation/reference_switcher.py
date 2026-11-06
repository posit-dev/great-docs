"""
The switcher between a site's API, CLI and MCP references

Sites with a switcher load `reference-switcher.js` on every page. The script reads the
available sections from the `data-gd-ref-sections` attribute on `<body>`. Sites with only an
API reference have no switcher and no copy of the script in the build directory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from .. import quarto_yml, scripts
from . import navbar as nav_navbar

if TYPE_CHECKING:
    from pathlib import Path

    from ...config import Config

__all__ = ["Section", "register"]

Section = Literal["api", "cli", "mcp"]
"""A reference section: the API, command-line or MCP server reference"""

_INDEX_PAGES: dict[Section, str] = {
    "api": "reference/index.qmd",
    "cli": "reference/cli/index.qmd",
    "mcp": "reference/mcp/index.qmd",
}

_OTHER_SECTIONS: tuple[Section, ...] = ("cli", "mcp")

_SCRIPT = "reference-switcher.js"
_SECTIONS_ATTRIBUTE = "data-gd-ref-sections"


def register(
    quarto_config: dict[str, Any], config: Config, build_dir: Path, *, has_api_reference: bool
) -> None:
    """
    Add the reference switcher when the site has a CLI or MCP reference

    The switcher offers the API reference when present and the CLI and MCP references
    whose index pages exist in the build directory. `ref_section_order` sets their order.
    If the first section is not the API reference, the navbar's Reference link opens that
    section's index page.

    Copy the switcher script into the build directory, list it in `project.resources`
    and load it on every page.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    build_dir
        The Quarto project directory.
    has_api_reference
        Whether the site has an API reference.

    Returns
    -------
    :
    """
    available: list[Section] = []
    if has_api_reference:
        available.append("api")
    available.extend(
        section for section in _OTHER_SECTIONS if (build_dir / _INDEX_PAGES[section]).is_file()
    )
    if all(section == "api" for section in available):
        return

    sections = _order(available, config.ref_section_order)
    if sections[0] != "api":
        _point_reference_link(quarto_config, _INDEX_PAGES[sections[0]])

    attribute_script = {
        "text": (
            "<script>"
            "document.addEventListener('DOMContentLoaded',function(){"
            f"document.body.setAttribute('{_SECTIONS_ATTRIBUTE}','{','.join(sections)}');"
            "});"
            "</script>"
        )
    }
    headers = quarto_yml.includes(quarto_config, "include-in-header")
    theme = quarto_yml.find(headers, "theme-init.js")
    headers.insert(len(headers) if theme is None else theme + 1, attribute_script)

    scripts.copy_asset(_SCRIPT, build_dir)
    quarto_yml.add_resources(quarto_config, [_SCRIPT])
    quarto_yml.add_include(
        quarto_config,
        "include-after-body",
        scripts.script_include(_SCRIPT),
        marker=_SCRIPT,
        before="tooltips.js",
    )


def _order(available: list[Section], preferred: list[str] | None) -> list[Section]:
    """
    Order the available sections by the configured preference

    Parameters
    ----------
    available
        The site's sections, in their default order.
    preferred
        Section names in the preferred order, or `None` for the default order.

    Returns
    -------
    :
        Available sections in the preferred order, followed by unlisted sections in
        their default order.
    """
    rank = {name: index for index, name in enumerate(preferred or [])}
    return sorted(available, key=lambda section: rank.get(section, len(rank)))


def _point_reference_link(quarto_config: dict[str, Any], href: str) -> None:
    """
    Set the navbar's Reference link to open the given page

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    href
        The destination page.

    Returns
    -------
    :
    """
    navbar = quarto_config.get("website", {}).get("navbar", {})
    for item in navbar.get("left", []):
        if isinstance(item, dict):
            link = cast("dict[str, Any]", item)
            if nav_navbar.REFERENCE.owns(link.get("href")):
                link["href"] = href
                return
