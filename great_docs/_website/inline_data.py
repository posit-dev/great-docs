"""
Data for the site's scripts, embedded in every page

An inline `<script>` assigns data to a global before the script that reads it runs.
This avoids fetching a JSON file at runtime and works under `file://` at any page depth.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from . import scripts

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["add"]


def add(quarto_config: dict[str, Any], name: str, data: Mapping[str, Any], *, before: str) -> None:
    """
    Embed a global assignment in an after-body include

    The assignment precedes the first `format.html.include-after-body` entry that loads
    the script named by `before`, so the data exists when that script runs. Match by file
    name or, for an embedded script, by a name it defines. Append the assignment if no
    entry matches, and leave an existing assignment to the global unchanged.

    Parameters
    ----------
    quarto_config
        The configuration, changed in place.
    name
        The global name, such as `__GD_TAGS_DATA__`.
    data
        The value to assign, serialisable as JSON.
    before
        The file name of the Great Docs script that reads the global, such as
        `page-tags.js`.

    Returns
    -------
    :

    Raises
    ------
    KeyError
        If `before` is not the file name of a script shipped with Great Docs.
    """
    script = scripts.named(before)
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
    position = next((i for i, item in enumerate(entries) if script.is_entry(item)), len(entries))
    entries.insert(position, entry)
