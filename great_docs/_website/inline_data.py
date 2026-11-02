"""
Data for the site's scripts, embedded in every page

An inline `<script>` assigns data to a global before the script that reads it runs.
This avoids fetching a JSON file at runtime and works under `file://` at any page depth.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["add"]


def add(quarto_config: dict[str, Any], name: str, data: Mapping[str, Any], *, before: str) -> None:
    """
    Embed a global assignment in an after-body include

    The assignment precedes the first `format.html.include-after-body` entry containing
    `before`, so the data exists when that script runs. It is appended when no entry
    matches. A configuration that already assigns the global is left unchanged.

    Parameters
    ----------
    quarto_config
        The configuration, changed in place.
    name
        The global name, such as `__GD_TAGS_DATA__`.
    data
        The value to assign, serialisable as JSON.
    before
        Text that identifies the script entry that reads the global, such as `page-tags.js`.

    Returns
    -------
    :
    """
    html = cast("dict[str, Any]", quarto_config.setdefault("format", {})).setdefault("html", {})
    html = cast("dict[str, Any]", html)
    entries = html.get("include-after-body", [])
    if isinstance(entries, str):
        entries = [entries]
    entries = cast("list[Any]", entries)
    html["include-after-body"] = entries

    assignment = f"window.{name}="
    if any(assignment in str(entry) for entry in entries):
        return
    # "</" inside a <script> element would end it early, as in the "</svg>" of an icon.
    text = json.dumps(data).replace("</", r"<\/")
    entry = {"text": f"<script>{assignment}{text};</script>"}
    position = next((i for i, item in enumerate(entries) if before in str(item)), len(entries))
    entries.insert(position, entry)
