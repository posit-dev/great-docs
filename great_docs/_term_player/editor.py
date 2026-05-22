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


def _serialize_script(script_data: dict[str, Any], source_path: str) -> str:
    """Serialize editor script data back to YAML string."""
    lines = [f"source: {source_path}", ""]

    settings = script_data.get("settings", {})
    if any(v is not None for v in settings.values()):
        lines.append("settings:")
        if settings.get("idle_time_limit") is not None:
            lines.append(f"  idle_time_limit: {settings['idle_time_limit']}")
        if settings.get("speed") and settings["speed"] != 1.0:
            lines.append(f"  speed: {settings['speed']}")
        if settings.get("window_chrome"):
            lines.append(f"  window_chrome: {settings['window_chrome']}")
        lines.append("")

    chapters = script_data.get("chapters", [])
    if chapters:
        lines.append("chapters:")
        for ch in sorted(chapters, key=lambda c: c["time"]):
            lines.append(f"  - at: {ch['time']}")
            lines.append(f'    label: "{ch["label"]}"')
        lines.append("")

    annotations = script_data.get("annotations", [])
    if annotations:
        lines.append("annotations:")
        for ann in sorted(annotations, key=lambda a: a["time"]):
            lines.append(f"  - at: {ann['time']}")
            lines.append(f"    duration: {ann['duration']}")
            lines.append(f'    text: "{ann["text"]}"')
            lines.append(f"    position: {ann['position']}")
            lines.append(f"    style: {ann['style']}")
        lines.append("")

    cuts = script_data.get("cuts", [])
    if cuts:
        lines.append("cuts:")
        for cut in sorted(cuts, key=lambda c: c["start"]):
            lines.append(f"  - from: {cut['start']}")
            lines.append(f"    to: {cut['end']}")
            lines.append(f"    type: {cut['type']}")
        lines.append("")

    return "\n".join(lines) + "\n"


class EditorHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the Termshow Editor."""

    editor_data: dict[str, Any]
    source_path: str
    script_path: Path

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Suppress default logging."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._serve_editor_page()
        elif self.path == "/api/data":
            self._json_response(self.editor_data)
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/save":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                script_data = json.loads(body)
                yaml_str = _serialize_script(script_data, self.source_path)
                self.script_path.write_text(yaml_str, encoding="utf-8")
                self._json_response({"ok": True, "path": str(self.script_path)})
            except Exception as e:
                self._json_response({"ok": False, "error": str(e)}, status=400)
        elif self.path == "/api/preview-yaml":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                script_data = json.loads(body)
                yaml_str = _serialize_script(script_data, self.source_path)
                self._json_response({"yaml": yaml_str})
            except Exception as e:
                self._json_response({"error": str(e)}, status=400)
        else:
            self.send_error(404)

    def _json_response(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_editor_page(self) -> None:
        html = _get_editor_html()
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


