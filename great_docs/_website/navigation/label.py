"""
Translated prefixes for reference navigation labels

Below 992px, the bar beside the sidebar toggle shows `API / name`, `CLI / name`
or `MCP / name`. Quarto supplies the page title when breadcrumbs are disabled.
CSS adds the prefix using custom properties declared in the site's language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..._translations import get_translations_bundle
from ..._yaml import YamlMapping

if TYPE_CHECKING:
    from ...config import Config


_PREFIX_PROPERTY = "--gd-nav-prefix-api:"


def _css_string(text: str) -> str:
    """
    Escape and quote text for use in CSS and an HTML style element

    Parameters
    ----------
    text
        Text to display unchanged.

    Returns
    -------
    :
        A double-quoted CSS string with `<` escaped to prevent it from
        closing an HTML `style` element.
    """
    escaped = (
        text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\a ").replace("<", "\\3c ")
    )
    return f'"{escaped}"'


def register(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add translated navigation prefixes to the HTML header

    Set `--gd-nav-prefix-api`, `--gd-nav-prefix-cli` and `--gd-nav-prefix-mcp`
    on `:root`. Leave the configuration unchanged if it has no HTML mapping.
    Replace the style from an earlier call so repeated calls keep one style
    with prefixes in the current language.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    """
    html_config = quarto_config.get("format", {}).get("html")
    if not isinstance(html_config, dict):
        return
    html_config = cast("dict[str, Any]", html_config)

    bundle = get_translations_bundle(config.lang)
    # MCP is a protocol name, so it is not translated.
    prefixes = {"api": bundle["api"], "cli": bundle["cli"], "mcp": "MCP"}
    declarations = "".join(
        f"--gd-nav-prefix-{kind}:{_css_string(text)};" for kind, text in prefixes.items()
    )

    headers = [
        header
        for header in YamlMapping(html_config).entries("include-in-header")
        if _PREFIX_PROPERTY not in str(header)
    ]
    headers.append({"text": f"<style>:root{{{declarations}}}</style>"})
    html_config["include-in-header"] = headers
