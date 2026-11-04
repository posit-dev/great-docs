"""
The version selector on every page of a versioned site

Each page carries the version map in a header meta element and loads
`version-selector.js`, which builds the selector from that map.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .._website import head, quarto_yml
from .._website.scripts import script_include
from .model import build_version_map, parse_versions_config

if TYPE_CHECKING:
    from ..config import Config

_VERSION_MAP = "gd-version-map"
_WARNING_BANNER = "gd-version-warning-banner"


def register(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Add version metadata and the selector script to every page

    The map lists the configured versions but contains no page paths. When
    the warning banner is disabled, a meta element tells the script to hide it.
    Registration replaces matching meta elements and includes the script once.
    The script loads before `navbar-widgets.js` so that the selector exists
    when the navbar widgets are collected.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration with at least one version.

    Returns
    -------
    :
    """
    versions = parse_versions_config(config.versions)
    version_map = build_version_map(versions, {version.tag: [] for version in versions})
    _replace_meta(quarto_config, _VERSION_MAP, json.dumps(version_map, separators=(",", ":")))
    if not config.version_warning_banner:
        _replace_meta(quarto_config, _WARNING_BANNER, "false")

    quarto_yml.add_include(
        quarto_config,
        "include-after-body",
        script_include("version-selector.js"),
        marker="version-selector",
        before="navbar-widgets",
    )


def _replace_meta(quarto_config: dict[str, Any], name: str, content: str) -> None:
    """
    Replace header includes mentioning `name` with one meta element

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    name
        The new element's `name` attribute.
    content
        The unescaped value for the element's `content` attribute.

    Returns
    -------
    :
    """
    header = quarto_yml.includes(quarto_config, "include-in-header")
    header[:] = [entry for entry in header if name not in str(entry)]
    header.append({"text": head.meta_element(name, content)})
