"""
Collect authored page statuses and embed badge data in Quarto projects
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from .._icons import get_icon_svg
from .._translations import get_translation
from . import inline_data, page_scan, quarto_yml

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from .._layout import Layout
    from ..config import Config

__all__ = ["add_upcoming", "collect", "inject", "is_script_entry", "process", "write"]

_BUILTIN_STATUSES = {"new", "updated", "beta", "deprecated", "experimental", "upcoming"}


def is_script_entry(entry: object) -> bool:
    """
    Report whether an after-body entry loads the status badge script
    """
    text = str(entry)
    return "page-status-badges" in text or "renderPageBadge" in text


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


def write(config: Config, build_dir: Path, statuses: Mapping[str, str]) -> None:
    """
    Write the page status data and resolved badge definitions
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


def inject(config: Config, build_dir: Path) -> None:
    """
    Embed status data before the badge script when both files exist
    """
    status_path = build_dir / "_page_status.json"
    if not status_path.is_file() or not quarto_yml.path(build_dir).is_file():
        return
    quarto_config = quarto_yml.read(build_dir)
    html = quarto_config.get("format", {}).get("html")
    if not isinstance(html, dict):
        return
    entries: Any = cast("dict[str, Any]", html).get("include-after-body", [])
    if isinstance(entries, str):
        entries = [entries]
    entries = cast("list[Any]", entries)
    if any("__GD_STATUS_DATA__=" in str(entry) for entry in entries):
        return
    anchor = next((str(entry) for entry in entries if is_script_entry(entry)), "page-status-badges")
    inline_data.add(
        quarto_config,
        "__GD_STATUS_DATA__",
        json.loads(status_path.read_text(encoding="utf-8")),
        before=anchor,
    )
    quarto_yml.write(build_dir, quarto_config, config)


def process(config: Config, layout: Layout, build_dir: Path) -> bool:
    """
    Write badge data when authored pages declare a status

    Return whether any matching page was found.
    """
    statuses = collect(config, layout, build_dir)
    if not statuses:
        return False
    write(config, build_dir, statuses)
    inject(config, build_dir)
    return True


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
