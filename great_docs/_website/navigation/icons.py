"""
Lucide icons for navbar and sidebar entries

Every page embeds the icon data and script, so subpages need no relative path to an
external script.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import quarto_yml
from ..icons import get_icon_svg
from . import navbar as nav_navbar

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...config import Config

_SCRIPT = Path(__file__).parents[2] / "assets" / "nav-icons.js"
_DATA_ID = "gd-nav-icons-data"


def register(
    quarto_config: dict[str, Any], config: Config, *, report: Callable[[str], None]
) -> None:
    """
    Add the configured navigation icons to every page

    Each icon is keyed by the label of the navigation entry it precedes. For Great Docs
    navbar items, English keys also match translated labels. Unknown icon names are
    reported and skipped. An existing icon include is left unchanged.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    report
        A callback for warnings about unknown icon names.

    Returns
    -------
    :
    """
    nav_icons = config.nav_icons
    if not nav_icons:
        return

    resolved: dict[str, dict[str, str]] = {}
    for scope in ("navbar", "sidebar"):
        icons = nav_icons.get(scope, {})
        if scope == "navbar":
            icons = nav_navbar.icon_labels(icons, config)
        svgs: dict[str, str] = {}
        for label, name in icons.items():
            svg = get_icon_svg(name)
            if svg:
                svgs[label] = svg
            else:
                report(f"Warning: Unknown nav icon '{name}' for '{label}'")
        if svgs:
            resolved[scope] = svgs
    if not resolved:
        return

    data = json.dumps(resolved, separators=(",", ":"))
    script = _SCRIPT.read_text(encoding="utf-8")
    entry = {
        "text": (
            f'<script id="{_DATA_ID}" type="application/json">{data}</script>\n'
            f"<script>{script}</script>"
        )
    }
    quarto_yml.add_include(quarto_config, "include-after-body", entry, marker=_DATA_ID)
