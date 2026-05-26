"""Importer for asciicast format."""

from __future__ import annotations

import json
from pathlib import Path

from .parser import Recording, parse_asciicast


def import_asciicast(source: str | Path, output: str | Path) -> Recording:
    """Import an asciicast v2/v3 file and save as .termshow.

    Parameters
    ----------
    source
        Path to .cast file.
    output
        Path to write .termshow file.

    Returns
    -------
    Recording
        The parsed recording.
    """
    recording = parse_asciicast(source)

    # Convert to termshow format and write
    _write_termshow(recording, output)
    return recording


def _write_termshow(recording: Recording, output: str | Path) -> None:
    """Write a Recording to .termshow format."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    # Header
    header = {
        "version": 1,
        "format": "termshow",
        "term": {
            "cols": recording.term.cols,
            "rows": recording.term.rows,
            "type": recording.term.type,
        },
        "title": recording.title,
    }
    if recording.timestamp:
        header["timestamp"] = recording.timestamp

    lines.append(json.dumps(header))

    # Events (convert absolute time back to relative intervals)
    prev_time = 0.0
    for event in recording.events:
        interval = round(event.time - prev_time, 3)
        lines.append(json.dumps([interval, event.code, event.data]))
        prev_time = event.time

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
