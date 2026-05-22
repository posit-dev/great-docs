"""Termshow Editor: browser-based NLE for .termshow recordings.

Serves a local web page with a timeline editor for adding chapters,
annotations, and cuts to termshow recordings.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from .parser import Recording, parse_termshow
from .script import Script, load_script


def _build_editor_data(recording: Recording, script: Script | None) -> dict[str, Any]:
    """Build the JSON data payload for the editor UI."""
    # Build event timeline with absolute times
    events = []
    for ev in recording.events:
        events.append({"time": ev.time, "code": ev.code, "data": ev.data})

    data: dict[str, Any] = {
        "recording": {
            "title": recording.title,
            "duration": recording.duration,
            "term": {
                "cols": recording.term.cols,
                "rows": recording.term.rows,
            },
            "events": events,
        },
        "script": {
            "settings": {
                "idle_time_limit": script.idle_time_limit if script else None,
                "speed": script.speed if script else 1.0,
                "window_chrome": script.window_chrome if script else "colorful",
            },
            "chapters": [
                {"time": ch.time, "label": ch.label} for ch in (script.chapters if script else [])
            ],
            "annotations": [
                {
                    "time": ann.time,
                    "duration": ann.duration,
                    "text": ann.text,
                    "position": ann.position,
                    "style": ann.style,
                }
                for ann in (script.annotations if script else [])
            ],
            "cuts": [
                {
                    "start": cut.start,
                    "end": cut.end,
                    "type": cut.type,
                }
                for cut in (script.cuts if script else [])
            ],
        },
    }
    return data


