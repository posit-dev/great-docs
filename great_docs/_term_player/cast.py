"""asciicast export: write a recording as an asciinema file.

The file plays in asciinema's own player and CLI, and can be uploaded to
asciinema.org. Version 3 is written by default, and version 2 for older tools.

A script's cuts and speed changes are applied, since they only change timing,
and its chapters become markers. Annotations, highlights, snippets and the
prompt replacement need the Termshow player, so they're left out.
"""

from __future__ import annotations

import json

from .parser import Event, Recording, Theme
from .script import Script, apply_script

VERSIONS = (2, 3)
# Event codes each version can hold
_CODES = {2: ("o", "i", "r", "m"), 3: ("o", "i", "r", "m", "x")}


def export_asciicast(
    recording: Recording,
    script: Script | None = None,
    *,
    version: int = 3,
    theme: Theme | None = None,
) -> str:
    """Write a recording as asciicast text.

    Parameters
    ----------
    recording
        The recording, on its own timeline.
    script
        A script whose cuts, speed changes, chapters and theme are applied. Its chapters replace
        the recording's markers, as they do in the player.
    version
        The asciicast version: `3` (the default) or `2`.
    theme
        The colors to write in the header. By default, the script's theme (the light side of a
        pair), or else the recording's.

    Returns
    -------
    str
        The file's text: a header line, then one line per event.
    """
    if version not in VERSIONS:
        raise ValueError(f"asciicast version must be 2 or 3, got {version!r}")

    if script is not None:
        recording = apply_script(recording, script)
        if theme is None:
            theme = script.theme
    theme = theme or recording.term.theme

    events = [e for e in recording.events if e.code in _CODES[version]]
    if script is not None and script.chapters:
        events = [e for e in events if e.code != "m"]
        markers = [Event(c.time, "m", c.label) for c in script.chapters]
        # A marker goes before any event at the same time; the sort is stable
        events = sorted(markers + events, key=lambda e: e.time)

    lines = [json.dumps(_header(recording, theme, version), ensure_ascii=False)]
    previous = 0.0
    for event in events:
        time = round(max(event.time, previous), 6)
        stamp = round(time - previous, 6) if version == 3 else time
        lines.append(json.dumps([stamp, event.code, event.data], ensure_ascii=False))
        previous = time
    return "\n".join(lines) + "\n"


def _header(recording: Recording, theme: Theme, version: int) -> dict:
    term = recording.term
    colors = {"fg": theme.fg, "bg": theme.bg, "palette": ":".join(theme.palette)}
    if version == 3:
        header: dict = {
            "version": 3,
            "term": {"cols": term.cols, "rows": term.rows, "type": term.type, "theme": colors},
        }
    else:
        header = {"version": 2, "width": term.cols, "height": term.rows}
    if recording.timestamp is not None:
        header["timestamp"] = recording.timestamp
    if recording.title:
        header["title"] = recording.title
    if version == 2:
        header["env"] = {"TERM": term.type}
        header["theme"] = colors
    return header


def left_out(script: Script | None) -> list[str]:
    """The script features an asciicast file can't hold, for telling the user."""
    if script is None:
        return []
    features = [
        ("annotations", script.annotations),
        ("highlights", script.highlights),
        ("snippets", script.snippets),
        ("the prompt replacement", script.prompt),
    ]
    return [name for name, value in features if value]
