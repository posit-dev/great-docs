"""
Collect authored page statuses and prepare badge data for embedding
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from .._contribution import Contribution, InlineData
from .._icons import get_icon_svg
from .._translations import get_translation
from . import page_scan

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from .._layout import Layout
    from ..config import Config

__all__ = ["add_upcoming", "collect", "process", "write"]

_BUILTIN_STATUSES = {"new", "updated", "beta", "deprecated", "experimental", "upcoming"}


def collect(config: Config, layout: Layout, build_dir: Path) -> dict[str, str]:
    """
    Map published authored pages to their declared status

    Scan user-guide, recipe and custom section pages, excluding index pages.
    Unknown statuses produce a warning and are omitted.
    """
    statuses: dict[str, str] = {}
    valid = config.page_status_definitions
    scan_layout = replace(layout, build_dir=build_dir)
    dirs = page_scan.content_dirs(config, scan_layout, reference=False)
    for item in page_scan.scan(dirs, build_dir, skip_index=True):
        status = item.page.front_matter.string("status")
        if not status:
            continue
        status = status.strip().lower()
        if status not in valid:
            print(f"Warning: Unknown page status '{status}' in {item.href}")
            continue
        statuses[item.href] = status
    return statuses


def write(config: Config, build_dir: Path, statuses: Mapping[str, str]) -> dict[str, Any]:
    """
    Write the page status data and resolved badge definitions

    Returns
    -------
    :
        The data written to `_page_status.json`.
    """
    user_statuses = config.user_settings.get("page_status", {})
    user_overrides: dict[str, Any] = (
        cast("dict[str, Any]", user_statuses).get("statuses", {})
        if isinstance(user_statuses, dict)
        else {}
    )
    definitions: dict[str, dict[str, str]] = {}
    for key, definition in config.page_status_definitions.items():
        icon_name = definition.get("icon", "")
        icon = get_icon_svg(icon_name, size=12, css_class="gd-status-icon-svg") if icon_name else ""
        if icon_name and not icon:
            print(f"Warning: Unknown page status icon '{icon_name}' for '{key}'")
        override = cast("dict[str, Any]", user_overrides.get(key, {}))
        label = definition.get("label", key.title())
        description = definition.get("description", "")
        if key in _BUILTIN_STATUSES:
            if "label" not in override:
                label = get_translation(f"status_label_{key}", config.lang)
            if "description" not in override:
                description = get_translation(f"status_desc_{key}", config.lang)
        definitions[key] = {
            "label": label,
            "icon": icon,
            "color": definition.get("color", "#6b7280"),
            "description": description,
        }
    data = {
        "page_statuses": dict(statuses),
        "definitions": definitions,
        "show_in_sidebar": config.page_status_show_in_sidebar,
        "show_on_pages": config.page_status_show_on_pages,
    }
    _ = (build_dir / "_page_status.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def process(config: Config, layout: Layout, build_dir: Path) -> Contribution | None:
    """
    Write badge data when authored pages declare a status

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories.
    build_dir
        The Quarto project directory whose pages are scanned and which receives
        `_page_status.json`.

    Returns
    -------
    :
        The badge data to embed before `page-status-badges.js`, or `None` when no
        page declares a known status.
    """
    statuses = collect(config, layout, build_dir)
    if not statuses:
        return None
    data = write(config, build_dir, statuses)
    return Contribution(
        inline_data=(InlineData("__GD_STATUS_DATA__", data, before="page-status-badges.js"),)
    )


def add_upcoming(quarto_config: dict[str, Any], upcoming: Mapping[str, str | bool]) -> bool:
    """
    Add upcoming page data after an existing status assignment

    The status and upcoming globals remain separate so each version can add its
    upcoming pages without rewriting the main badge data. Return whether the
    configuration changed.
    """
    if not upcoming:
        return False
    html = quarto_config.get("format", {}).get("html")
    if not isinstance(html, dict):
        return False
    for key in ("include-after-body", "include-in-header"):
        entries: Any = cast("dict[str, Any]", html).get(key)
        if isinstance(entries, str):
            entries = [entries]
            html[key] = entries
        if not isinstance(entries, list):
            continue
        entries = cast("list[Any]", entries)
        if any("<script>window.__GD_UPCOMING_DATA__=" in str(entry) for entry in entries):
            return False
        for index, entry in enumerate(entries):
            if "<script>window.__GD_STATUS_DATA__=" in str(entry):
                data = json.dumps(upcoming).replace("</", r"<\/")
                cast("list[Any]", entries).insert(
                    index + 1, {"text": f"<script>window.__GD_UPCOMING_DATA__={data};</script>"}
                )
                return True
    return False
