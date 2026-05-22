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


def serve_editor(
    source: str | Path,
    port: int = 8765,
    no_browser: bool = False,
) -> None:
    """Launch the editor server for a .termshow file.

    Parameters
    ----------
    source
        Path to the .termshow recording file.
    port
        Local port to serve on.
    no_browser
        If True, don't auto-open the browser.
    """
    source_path = Path(source).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Recording not found: {source_path}")

    recording = parse_termshow(source_path)

    # Auto-detect script
    script_path = source_path.with_suffix(".termshow.yml")
    script: Script | None = None
    if script_path.exists():
        script = load_script(script_path)

    editor_data = _build_editor_data(recording, script)
    editor_data["source_file"] = source_path.name

    # Create handler class with bound data
    class BoundHandler(EditorHandler):
        pass

    BoundHandler.editor_data = editor_data  # type: ignore[attr-defined]
    BoundHandler.source_path = str(source_path.relative_to(source_path.parent.parent))  # type: ignore[attr-defined]
    BoundHandler.script_path = script_path  # type: ignore[attr-defined]

    server = HTTPServer(("127.0.0.1", port), BoundHandler)

    url = f"http://127.0.0.1:{port}"
    print(f"✦ Termshow Editor serving at {url}")
    print(f"  Recording: {source_path.name}")
    print(
        f"  Script:    {script_path.name} {'(exists)' if script_path.exists() else '(will create)'}"
    )
    print("  Press Ctrl+C to stop\n")

    if not no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Editor stopped.")
        server.shutdown()


def _get_editor_html() -> str:
    """Return the full editor HTML page."""
    return _EDITOR_HTML


# ---------------------------------------------------------------------------
# Editor HTML (single-page app)
# ---------------------------------------------------------------------------

_EDITOR_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Termshow Editor</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #0f0f14;
  --surface: #1a1a24;
  --surface2: #242430;
  --border: #3d4775;
  --tick: #4a4a60;
  --tick-minor: #3a3a50;
  --text: #e0e0ea;
  --text-dim: #8888a0;
  --accent: #89b4fa;
  --accent-hover: #a6c8ff;
  --chapter: #f9e2af;
  --annotation: #a6e3a1;
  --cut: #f38ba8;
  --playhead: #cba6f7;
  --radius: 6px;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.editor-title {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.editor-title .logo {
  color: var(--accent);
}

.editor-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 6px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.btn:hover { background: var(--border); }
.btn-primary { background: var(--accent); color: #000; border-color: var(--accent); }
.btn-primary:hover { background: var(--accent-hover); }
.btn-dirty { background: var(--chapter); border-color: var(--chapter); animation: pulse-save 1.5s ease infinite; }
@keyframes pulse-save {
  0%, 100% { box-shadow: 0 0 0 0 rgba(249, 226, 175, 0.4); }
  50% { box-shadow: 0 0 8px 2px rgba(249, 226, 175, 0.4); }
}

/* Main area */
.editor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Viewport - terminal preview */
.preview-area {
  flex: 0 0 45%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 16px;
  position: relative;
  overflow: hidden;
}

.preview-viewport {
  background: #1e1e2e;
  border-radius: 8px;
  border: 1px solid var(--border);
  overflow: hidden;
  position: relative;
}

.preview-viewport pre {
  font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
  font-size: 13px;
  line-height: 1.3;
  padding: 12px;
  margin: 0;
  white-space: pre;
  overflow: hidden;
  color: #cdd6f4;
  width: calc(var(--term-cols) * 1ch + 24px);
  height: calc(var(--term-rows) * 1lh + 24px);
}

.preview-wrapper {
  display: flex;
  flex-direction: column;
  transform: scale(var(--viewport-scale, 1));
  transform-origin: center center;
}

.chapter-title-overlay {
  text-align: center;
  padding: 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--chapter);
  background: var(--surface);
  border: 1px solid var(--border);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  pointer-events: none;
  opacity: 0;
  height: 0;
  overflow: hidden;
  transition: opacity 0.3s ease, height 0.2s ease, padding 0.2s ease;
}

.chapter-title-overlay.visible {
  opacity: 1;
  height: auto;
  padding: 5px 12px;
}

.chapter-title-overlay.visible + .preview-viewport {
  border-top: none;
  border-radius: 0 0 8px 8px;
}

.cut-indicator {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  color: var(--text-dim);
  background: rgba(15, 15, 20, 0.85);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  z-index: 8;
  letter-spacing: 8px;
}

.cut-indicator.flash {
  opacity: 1;
}

.annotation-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.annotation-bubble {
  position: absolute;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  max-width: 60%;
  animation: ann-fade-in 0.2s ease;
}

.annotation-bubble.style-callout {
  background: rgba(137, 180, 250, 0.9);
  color: #1e1e2e;
}

.annotation-bubble.style-subtle {
  background: rgba(49, 50, 68, 0.85);
  color: #cdd6f4;
  border: 1px solid var(--border);
}

.annotation-bubble.style-highlight {
  background: rgba(249, 226, 175, 0.9);
  color: #1e1e2e;
}

.annotation-bubble.pos-top-left { top: 10px; left: 10px; }
.annotation-bubble.pos-top-right { top: 10px; right: 10px; }
.annotation-bubble.pos-bottom-left { bottom: 10px; left: 10px; }
.annotation-bubble.pos-bottom-right { bottom: 10px; right: 10px; }

@keyframes ann-fade-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Transport controls */
.transport {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.transport-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface2);
}

.transport-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.transport-btn:hover { background: var(--border); }
.transport-btn.active { background: var(--accent); color: #000; border-color: var(--accent); }

/* Press flash for non-toggle transport buttons */
@keyframes transport-flash {
  0% { background: var(--accent); color: #000; border-color: var(--accent); transform: scale(1.1); }
  100% { background: transparent; color: var(--text); border-color: var(--border); transform: scale(1); }
}
.transport-btn.flash {
  animation: transport-flash 0.3s ease-out;
}

.transport-time {
  font-size: 1.2em;
  font-variant-numeric: tabular-nums;
  font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
  color: var(--text);
  padding: 4px 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 5px;
  margin-left: 6px;
  cursor: pointer;
}
.transport-time:hover {
  border-color: var(--accent);
}

/* Inline time editor */
.time-editor {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 6px;
  font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
  font-size: 1.2em;
}
.time-editor input {
  width: 2.2em;
  padding: 3px 4px;
  background: var(--bg);
  border: 1px solid var(--accent);
  border-radius: 3px;
  color: var(--text);
  font: inherit;
  text-align: center;
  outline: none;
}
.time-editor input.te-cs {
  width: 2.6em;
}
.time-editor .te-sep {
  color: var(--text-dim);
  font-size: 0.9em;
}

.transport-spacer {
  flex: 1;
}

.transport-duration {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
  color: var(--text-dim);
  margin-right: 16px;
}

/* Timeline panel */
.timeline-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--surface);
  overflow-y: auto;
  position: relative;
}

.timeline-ruler {
  height: 29px;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  position: relative;
  flex-shrink: 0;
  cursor: grab;
  margin-left: 90px;
  margin-right: 16px;
}
.timeline-ruler:active { cursor: grabbing; }

.ruler-tick {
  position: absolute;
  top: 0;
  height: 100%;
  border-left: 1px solid var(--tick);
  font-size: 9px;
  color: var(--text-dim);
  padding: 2px 4px;
  pointer-events: none;
}
.ruler-tick-minor {
  position: absolute;
  top: 60%;
  height: 40%;
  border-left: 1px solid var(--tick-minor);
  pointer-events: none;
}
.ruler-tick-mid {
  position: absolute;
  top: 40%;
  height: 60%;
  border-left: 1px solid var(--tick);
  pointer-events: none;
}

/* Timeline tracks */
.timeline-track {
  position: relative;
  height: 36px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
}

.track-label {
  width: 90px;
  padding: 0 10px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  height: 100%;
  display: flex;
  align-items: center;
}

.track-content {
  flex: 1;
  position: relative;
  height: 100%;
  overflow: visible;
  margin-right: 16px;
}

/* Track items */
.track-item-chapter {
  position: absolute;
  top: 4px;
  bottom: 4px;
  width: 3px;
  background: var(--chapter);
  border-radius: 2px;
  cursor: grab;
  z-index: 2;
}

.track-item-chapter::before {
  content: '';
  position: absolute;
  left: -6px;
  right: -6px;
  top: -4px;
  bottom: -4px;
}

.track-item-chapter:hover {
  width: 5px;
  transform: translateX(-1px);
}

.track-item-chapter.selected {
  width: 5px;
  transform: translateX(-1px);
  top: -14px;
  bottom: -14px;
  box-shadow: 0 0 10px 2px rgba(249, 226, 175, 0.7);
}

.track-item-chapter.selected .item-label {
  font-weight: 700;
  top: 16px;
  text-shadow: 0 0 6px rgba(249, 226, 175, 0.5);
}

.track-item-chapter .item-label {
  position: absolute;
  top: -2px;
  left: 8px;
  font-size: 10px;
  color: var(--chapter);
  white-space: nowrap;
  pointer-events: none;
}

#track-chapters {
  cursor: crosshair;
}

.track-item-annotation {
  position: absolute;
  top: 6px;
  bottom: 6px;
  background: rgba(166, 227, 161, 0.2);
  border: 1px solid rgba(166, 227, 161, 0.7);
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 0 6px;
  font-size: 10px;
  color: var(--annotation);
  overflow: visible;
  min-width: 8px;
}

.track-item-annotation .ann-text {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  flex: 1;
  pointer-events: none;
}

.track-item-annotation:hover {
  background: rgba(166, 227, 161, 0.3);
}

.track-item-annotation.selected {
  background: rgba(166, 227, 161, 0.35);
  border-color: var(--annotation);
  box-shadow: 0 0 8px 2px rgba(166, 227, 161, 0.4);
  font-weight: 600;
}

.track-item-annotation .ann-handle {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 6px;
  cursor: ew-resize;
  z-index: 5;
}

.track-item-annotation .ann-handle-left {
  left: -3px;
  border-left: 2px solid var(--annotation);
  border-radius: 2px 0 0 2px;
}

.track-item-annotation .ann-handle-right {
  right: -3px;
  border-right: 2px solid var(--annotation);
  border-radius: 0 2px 2px 0;
}

.track-item-annotation .ann-handle:hover,
.track-item-annotation .ann-handle.active {
  background: rgba(166, 227, 161, 0.4);
}

.track-item-annotation .ann-handle.selected {
  top: -14px;
  bottom: -14px;
  width: 4px;
  background: none;
  z-index: 20;
}

.track-item-annotation .ann-handle-left.selected {
  left: -2px;
  border-left: 3px solid var(--annotation);
  box-shadow: -2px 0 8px rgba(166, 227, 161, 0.7);
}

.track-item-annotation .ann-handle-right.selected {
  right: -2px;
  border-right: 3px solid var(--annotation);
  box-shadow: 2px 0 8px rgba(166, 227, 161, 0.7);
}

.track-item-cut {
  position: absolute;
  top: 4px;
  bottom: 4px;
  background: rgba(243, 139, 168, 0.15);
  border: 1px solid rgba(243, 139, 168, 0.6);
  border-radius: 3px;
  cursor: pointer;
  overflow: visible;
}

.track-item-cut:hover {
  background: rgba(243, 139, 168, 0.25);
}

.track-item-cut.cut-seamless {
  background: rgba(180, 190, 254, 0.12);
  border-color: rgba(180, 190, 254, 0.6);
  border-style: dashed;
}

.track-item-cut.cut-seamless:hover {
  background: rgba(180, 190, 254, 0.22);
}

.track-item-cut.cut-seamless.selected {
  background: rgba(180, 190, 254, 0.35);
  border-color: rgba(180, 190, 254, 0.8);
  box-shadow: 0 -4px 8px rgba(180, 190, 254, 0.3), 0 4px 8px rgba(180, 190, 254, 0.3);
}

.cut-label {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 10px;
  color: var(--cut);
  opacity: 0.7;
  pointer-events: none;
}

.track-item-cut .cut-handle {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 6px;
  cursor: ew-resize;
  z-index: 5;
}

.track-item-cut .cut-handle-left {
  left: -3px;
  border-left: 2px solid var(--cut);
  border-radius: 2px 0 0 2px;
}

.track-item-cut .cut-handle-right {
  right: -3px;
  border-right: 2px solid var(--cut);
  border-radius: 0 2px 2px 0;
}

.track-item-cut .cut-handle:hover,
.track-item-cut .cut-handle.active {
  background: rgba(243, 139, 168, 0.4);
}

.track-item-cut.selected {
  background: rgba(243, 139, 168, 0.4);
  border-color: var(--cut);
  box-shadow: 0 -4px 8px rgba(243, 139, 168, 0.3), 0 4px 8px rgba(243, 139, 168, 0.3);
}

.track-item-cut .cut-handle.selected {
  top: -14px;
  bottom: -14px;
  width: 4px;
  background: none;
  z-index: 20;
}

.track-item-cut .cut-handle-left.selected {
  left: -2px;
  border-left: 3px solid var(--cut);
  box-shadow: -2px 0 8px rgba(243, 139, 168, 0.7);
}

.track-item-cut .cut-handle-right.selected {
  right: -2px;
  border-right: 3px solid var(--cut);
  box-shadow: 2px 0 8px rgba(243, 139, 168, 0.7);
}

#track-cuts {
  cursor: crosshair;
}

/* Playhead — single line spanning ruler + 3 tracks */
.playhead {
  position: absolute;
  top: 0;
  left: 0;
  height: 141px; /* ruler 29px + 3 tracks × 36px + 4px overshoot */
  width: 2px;
  background: var(--playhead);
  z-index: 10;
  pointer-events: none;
  margin-left: -1px;
  will-change: transform;
  opacity: 0;
}

.playhead::before {
  content: '';
  position: absolute;
  top: 0;
  left: -4px;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 7px solid var(--playhead);
}

.playhead::after {
  content: '';
  position: absolute;
  bottom: -4px;
  left: -3px;
  width: 8px;
  height: 8px;
  background: var(--cut);
  border-radius: 50%;
}

/* Properties panel (right side or bottom) */
.properties-panel {
  position: fixed;
  right: 16px;
  top: 60px;
  width: 280px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px;
  display: none;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}

.properties-panel.open { display: block; }

.prop-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
}

.prop-field {
  margin-bottom: 10px;
}

.prop-label {
  font-size: 11px;
  color: var(--text-dim);
  margin-bottom: 3px;
}

.prop-input {
  width: 100%;
  padding: 5px 8px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 12px;
  outline: none;
}
/* Number input spinner arrows */
.prop-input[type="number"]::-webkit-inner-spin-button,
.prop-input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  appearance: none;
}
.prop-input[type="number"] {
  -moz-appearance: textfield;
  padding-right: 32px;
  font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', Menlo, monospace;
}

.prop-input:focus { border-color: var(--accent); }

/* Custom number spinner buttons */
.number-wrap {
  position: relative;
}
.number-wrap .num-btn {
  position: absolute;
  right: 2px;
  width: 24px;
  height: 50%;
  background: var(--surface);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  font-size: 14px;
  line-height: 1;
  border-radius: 3px;
}
.number-wrap .num-btn:hover {
  background: var(--border);
  color: var(--text);
}
.number-wrap .num-btn-up {
  top: 2px;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}
.number-wrap .num-btn-down {
  bottom: 2px;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}

.prop-select {
  width: 100%;
  padding: 5px 8px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 12px;
}

.prop-actions {
  display: flex;
  gap: 6px;
  margin-top: 12px;
}

/* Toast notifications */
.toast {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 20px;
  background: var(--surface2);
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  font-size: 13px;
  color: var(--text);
  z-index: 999;
  opacity: 0;
  transition: opacity 0.3s;
}

.toast.show { opacity: 1; }

/* YAML Preview Modal */
.yaml-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 1000;
  display: none;
  align-items: center;
  justify-content: center;
}
.yaml-modal-backdrop.visible { display: flex; }
.yaml-modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  width: min(90vw, 640px);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}
.yaml-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.yaml-modal-header h3 {
  margin: 0;
  font-size: 14px;
  color: var(--text);
}
.yaml-modal-header .yaml-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}
.yaml-status.saved {
  background: rgba(166, 227, 161, 0.15);
  color: #a6e3a1;
}
.yaml-status.unsaved {
  background: rgba(249, 226, 175, 0.15);
  color: #f9e2af;
}
.yaml-modal-close {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}
.yaml-modal-close:hover { color: var(--text); background: var(--surface2); }
.yaml-modal-body {
  overflow-y: auto;
  padding: 16px;
}
.yaml-modal-body pre {
  margin: 0;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-all;
}

/* Keyboard shortcut hints */
.shortcuts {
  font-size: 11px;
  color: var(--text-dim);
  padding: 4px 16px;
  background: var(--surface2);
  border-top: 1px solid var(--border);
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}

.shortcuts kbd {
  background: var(--border);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  font-family: inherit;
}
</style>
</head>
<body>
<div class="editor-header">
  <div class="editor-title">
    <span class="logo">&#9670;</span>
    <span>Termshow Editor</span>
    <span id="file-name" style="color: var(--text-dim); font-weight: 400; font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 0.85em; padding-top: 5px; padding-left: 5px;"></span>
  </div>
  <div class="editor-actions">
    <button class="btn" id="btn-add-chapter" title="Add chapter at playhead (C)">+ Chapter</button>
    <button class="btn" id="btn-add-annotation" title="Add annotation at playhead (A)">+ Annotation</button>
    <button class="btn" id="btn-add-cut" title="Mark cut region (X)">+ Cut</button>
    <button class="btn" id="btn-view-yaml" title="View YAML (Y)" style="margin-left: 8px;">YAML</button>
    <button class="btn btn-primary" id="btn-save" title="Save (Cmd+S)">Save</button>
  </div>
</div>

<div class="editor-main">
  <div class="preview-area">
    <div class="preview-wrapper">
      <div id="chapter-title-overlay" class="chapter-title-overlay"></div>
      <div class="preview-viewport">
        <pre id="terminal-output"></pre>
        <div id="annotation-overlay" class="annotation-overlay"></div>
        <div id="cut-indicator" class="cut-indicator">&#x22ef;</div>
      </div>
    </div>
  </div>

  <div class="transport">
    <span class="transport-spacer"></span>
    <div class="transport-controls">
      <button class="transport-btn" id="btn-rewind" title="Rewind to start"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5"/></svg></button>
      <button class="transport-btn" id="btn-prev-chapter" title="Previous chapter (,)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="4"/><polygon points="14 20 4 12 14 4"/></svg></button>
      <button class="transport-btn" id="btn-play" title="Play/Pause (Space)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg></button>
      <button class="transport-btn" id="btn-next-chapter" title="Next chapter (.)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="4" x2="6" y2="20"/><polygon points="10 4 20 12 10 20"/></svg></button>
      <span class="transport-time" id="time-display">0:00.00 / 0:00.00</span>
    </div>
    <span class="transport-spacer"></span>
    <span class="transport-duration" id="duration-display"></span>
  </div>

  <div class="timeline-panel" id="timeline-panel">
    <div class="playhead" id="main-playhead"></div>
    <div class="timeline-ruler" id="timeline-ruler"></div>
    <div class="timeline-track">
      <div class="track-label" style="color: var(--chapter);">Chapters</div>
      <div class="track-content" id="track-chapters"></div>
    </div>
    <div class="timeline-track">
      <div class="track-label" style="color: var(--annotation);">Annot.</div>
      <div class="track-content" id="track-annotations"></div>
    </div>
    <div class="timeline-track">
      <div class="track-label" style="color: var(--cut);">Cuts</div>
      <div class="track-content" id="track-cuts"></div>
    </div>
  </div>
</div>

<div class="shortcuts">
  <span><kbd>Space</kbd> Play/Pause</span>
  <span><kbd>C</kbd> Add chapter</span>
  <span><kbd>A</kbd> Add annotation</span>
  <span><kbd>X</kbd> Mark cut</span>
  <span><kbd>&larr;</kbd><kbd>&rarr;</kbd> Seek</span>
  <span><kbd>,</kbd><kbd>.</kbd> Prev/Next chapter</span>
  <span><kbd>&#x2318;S</kbd> Save</span>
  <span><kbd>Del</kbd> Delete selected</span>
</div>

<div class="properties-panel" id="properties-panel"></div>
<div class="toast" id="toast"></div>

<div class="yaml-modal-backdrop" id="yaml-modal-backdrop">
  <div class="yaml-modal">
    <div class="yaml-modal-header">
      <h3 id="yaml-modal-title"></h3>
      <span class="yaml-status" id="yaml-status"></span>
      <button class="yaml-modal-close" id="yaml-modal-close">&times;</button>
    </div>
    <div class="yaml-modal-body">
      <pre id="yaml-modal-content"></pre>
    </div>
  </div>
</div>

<script>
(function() {
  'use strict';

  // --- State ---
  let data = null;
  let currentTime = 0;
  let playing = false;
  let animFrame = null;
  let lastTick = null;
  let selectedItem = null;

  // --- DOM ---
  const termOutput = document.getElementById('terminal-output');
  const timeDisplay = document.getElementById('time-display');
  const durationDisplay = document.getElementById('duration-display');
  const ruler = document.getElementById('timeline-ruler');
  const trackChapters = document.getElementById('track-chapters');
  const trackAnnotations = document.getElementById('track-annotations');
  const trackCuts = document.getElementById('track-cuts');
  const propsPanel = document.getElementById('properties-panel');
  const toast = document.getElementById('toast');
  const btnPlay = document.getElementById('btn-play');
  const fileName = document.getElementById('file-name');

  // --- Load data ---
  fetch('/api/data')
    .then(r => r.json())
    .then(d => { data = d; init(); })
    .catch(e => showToast('Failed to load: ' + e.message));

  function init() {
    fileName.textContent = data.source_file || data.recording.title || 'Untitled';
    durationDisplay.textContent = formatTimePrecise(data.recording.duration);

    // Set terminal viewport to captured dimensions
    const viewport = document.querySelector('.preview-viewport pre');
    viewport.style.setProperty('--term-cols', data.recording.term.cols);
    viewport.style.setProperty('--term-rows', data.recording.term.rows);

    buildRuler();
    renderTracks();
    renderTerminal();
    updateTimeDisplay();
    // Double-rAF ensures browser has painted before measuring layout
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        invalidatePlayheadCache();
        updatePlayhead();
        fitViewport();
        document.getElementById('main-playhead').style.opacity = '1';
      });
    });
  }

  // --- Ruler ---
  function buildRuler() {
    ruler.innerHTML = '';
    const dur = data.recording.duration;
    const interval = dur > 60 ? 10 : dur > 30 ? 5 : dur > 10 ? 2 : 1;
    for (let t = 0; t <= dur; t += interval) {
      const pct = (t / dur) * 100;
      const tick = document.createElement('div');
      tick.className = 'ruler-tick';
      tick.style.left = pct + '%';
      tick.textContent = formatTimeShort(t);
      ruler.appendChild(tick);
    }
    // Minor ticks every 0.2s
    const minorInterval = 0.2;
    const halfInterval = interval / 2;
    for (let t = 0; t <= dur; t += minorInterval) {
      // Skip positions that coincide with major ticks
      if (Math.abs(t % interval) < 0.001 || Math.abs(t % interval - interval) < 0.001) continue;
      const pct = (t / dur) * 100;
      const tick = document.createElement('div');
      // Use mid-tick style for halfway marks
      const isHalf = Math.abs(t % interval - halfInterval) < 0.001;
      tick.className = isHalf ? 'ruler-tick-mid' : 'ruler-tick-minor';
      tick.style.left = pct + '%';
      ruler.appendChild(tick);
    }
    // Playhead is now a single element on timeline-panel
  }

  // --- Tracks ---
  function renderTracks() {
    // Chapters
    trackChapters.innerHTML = '';

    data.script.chapters.forEach((ch, i) => {
      const el = document.createElement('div');
      el.className = 'track-item-chapter';
      el.style.left = timeToPct(ch.time);
      el.innerHTML = '<span class="item-label">' + escHtml(ch.label) + '</span>';
      el.addEventListener('mousedown', (e) => { e.stopPropagation(); startChapterDrag(i, e); });
      trackChapters.appendChild(el);
    });

    // Annotations
    trackAnnotations.innerHTML = '';

    data.script.annotations.forEach((ann, i) => {
      const el = document.createElement('div');
      el.className = 'track-item-annotation';
      el.style.left = timeToPct(ann.time);
      el.style.width = durationToPct(ann.duration);
      const textSpan = document.createElement('span');
      textSpan.className = 'ann-text';
      textSpan.textContent = ann.text;
      el.appendChild(textSpan);
      el.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('ann-handle')) return;
        e.stopPropagation();
        startBoxDrag('annotation', i, e);
      });

      // Left handle
      const lh = document.createElement('div');
      lh.className = 'ann-handle ann-handle-left';
      lh.addEventListener('mousedown', (e) => { e.stopPropagation(); startAnnotationHandleDrag(i, 'start', e); });
      el.appendChild(lh);

      // Right handle
      const rh = document.createElement('div');
      rh.className = 'ann-handle ann-handle-right';
      rh.addEventListener('mousedown', (e) => { e.stopPropagation(); startAnnotationHandleDrag(i, 'end', e); });
      el.appendChild(rh);

      trackAnnotations.appendChild(el);
    });

    // Cuts
    trackCuts.innerHTML = '';

    data.script.cuts.forEach((cut, i) => {
      const el = document.createElement('div');
      el.className = 'track-item-cut' + (cut.type === 'jump' ? ' cut-seamless' : '');
      el.style.left = timeToPct(cut.start);
      el.style.width = durationToPct(cut.end - cut.start);
      el.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('cut-handle')) return;
        e.stopPropagation();
        startBoxDrag('cut', i, e);
      });

      // Ellipsis label
      if (cut.type === 'ellipsis') {
        const lbl = document.createElement('span');
        lbl.className = 'cut-label';
        lbl.textContent = '\u22ef';
        el.appendChild(lbl);
      }

      // Left handle
      const lh = document.createElement('div');
      lh.className = 'cut-handle cut-handle-left';
      lh.addEventListener('mousedown', (e) => { e.stopPropagation(); startHandleDrag(i, 'start', e); });
      el.appendChild(lh);

      // Right handle
      const rh = document.createElement('div');
      rh.className = 'cut-handle cut-handle-right';
      rh.addEventListener('mousedown', (e) => { e.stopPropagation(); startHandleDrag(i, 'end', e); });
      el.appendChild(rh);

      trackCuts.appendChild(el);
    });
  }

  // --- Terminal rendering ---
  function renderTerminal() {
    // Replay events up to currentTime using a proper terminal emulator with color
    const cols = data.recording.term.cols;
    const rows = data.recording.term.rows;

    // Each cell: {char, fg, bg, bold}
    const EMPTY = {char: ' ', fg: null, bg: null, bold: false};
    const grid = [];
    for (let r = 0; r < rows; r++) {
      const row = [];
      for (let c2 = 0; c2 < cols; c2++) row.push({...EMPTY});
      grid.push(row);
    }
    let curRow = 0, curCol = 0;
    let curFg = null, curBg = null, curBold = false;

    const COLORS = [
      '#000', '#c00', '#0a0', '#a50', '#00a', '#a0a', '#0aa', '#aaa',
      '#555', '#f55', '#5f5', '#ff5', '#55f', '#f5f', '#5ff', '#fff',
    ];

    function color256(n) {
      if (n < 16) return COLORS[n];
      if (n >= 232) { const v = (n - 232) * 10 + 8; return 'rgb(' + v + ',' + v + ',' + v + ')'; }
      const idx = n - 16;
      const rv = Math.floor(idx / 36), gv = Math.floor((idx % 36) / 6), bv = idx % 6;
      const toVal = v => v === 0 ? 0 : 55 + v * 40;
      return 'rgb(' + toVal(rv) + ',' + toVal(gv) + ',' + toVal(bv) + ')';
    }

    function scrollUp() {
      grid.shift();
      const row = [];
      for (let c2 = 0; c2 < cols; c2++) row.push({...EMPTY});
      grid.push(row);
    }

    function clearCell(r, c2) { grid[r][c2] = {...EMPTY}; }

    function feedChar(ch) {
      if (curRow >= rows) { curRow = rows - 1; scrollUp(); }
      if (curCol >= cols) return;
      grid[curRow][curCol] = {char: ch, fg: curFg, bg: curBg, bold: curBold};
      curCol++;
    }

    function applySGR(nums) {
      if (nums.length === 0) nums = [0];
      let j = 0;
      while (j < nums.length) {
        const n = nums[j];
        if (n === 0) { curFg = null; curBg = null; curBold = false; }
        else if (n === 1) curBold = true;
        else if (n === 22) curBold = false;
        else if (n === 7) { const tmp = curFg; curFg = curBg || '#000'; curBg = tmp || '#aaa'; }
        else if (n === 27) { const tmp = curFg; curFg = curBg; curBg = tmp; }
        else if (n >= 30 && n <= 37) curFg = COLORS[n - 30];
        else if (n === 38) {
          if (nums[j+1] === 5 && nums.length > j+2) { curFg = color256(nums[j+2]); j += 2; }
          else if (nums[j+1] === 2 && nums.length > j+4) { curFg = 'rgb(' + nums[j+2] + ',' + nums[j+3] + ',' + nums[j+4] + ')'; j += 4; }
        }
        else if (n === 39) curFg = null;
        else if (n >= 40 && n <= 47) curBg = COLORS[n - 40];
        else if (n === 48) {
          if (nums[j+1] === 5 && nums.length > j+2) { curBg = color256(nums[j+2]); j += 2; }
          else if (nums[j+1] === 2 && nums.length > j+4) { curBg = 'rgb(' + nums[j+2] + ',' + nums[j+3] + ',' + nums[j+4] + ')'; j += 4; }
        }
        else if (n === 49) curBg = null;
        else if (n >= 90 && n <= 97) curFg = COLORS[n - 90 + 8];
        else if (n >= 100 && n <= 107) curBg = COLORS[n - 100 + 8];
        j++;
      }
    }

    for (const ev of data.recording.events) {
      if (ev.time > currentTime) break;
      if (ev.code !== 'o') continue;
      const s = ev.data;
      let i = 0;
      while (i < s.length) {
        const c = s[i];

        if (c === '\\x1b') {
          i++;
          if (i >= s.length) break;
          if (s[i] === '[') {
            i++;
            let params = '';
            while (i < s.length && s[i] >= '\\x20' && s[i] <= '\\x3f') { params += s[i]; i++; }
            const cmd = (i < s.length) ? s[i] : ''; i++;
            const nums = params ? params.split(';').map(n => parseInt(n, 10) || 0) : [];

            switch (cmd) {
              case 'm': applySGR(nums); break;
              case 'H': case 'f':
                curRow = (nums[0] || 1) - 1; curCol = (nums[1] || 1) - 1; break;
              case 'A': curRow = Math.max(0, curRow - (nums[0] || 1)); break;
              case 'B': curRow = Math.min(rows - 1, curRow + (nums[0] || 1)); break;
              case 'C': curCol = Math.min(cols - 1, curCol + (nums[0] || 1)); break;
              case 'D': curCol = Math.max(0, curCol - (nums[0] || 1)); break;
              case 'J':
                if ((nums[0] || 0) === 0) {
                  for (let c2 = curCol; c2 < cols; c2++) clearCell(curRow, c2);
                  for (let r = curRow + 1; r < rows; r++) for (let c2 = 0; c2 < cols; c2++) clearCell(r, c2);
                } else if (nums[0] === 1) {
                  for (let r = 0; r < curRow; r++) for (let c2 = 0; c2 < cols; c2++) clearCell(r, c2);
                  for (let c2 = 0; c2 <= curCol; c2++) clearCell(curRow, c2);
                } else if (nums[0] === 2) {
                  for (let r = 0; r < rows; r++) for (let c2 = 0; c2 < cols; c2++) clearCell(r, c2);
                }
                break;
              case 'K':
                if ((nums[0] || 0) === 0) { for (let c2 = curCol; c2 < cols; c2++) clearCell(curRow, c2); }
                else if (nums[0] === 1) { for (let c2 = 0; c2 <= curCol; c2++) clearCell(curRow, c2); }
                else if (nums[0] === 2) { for (let c2 = 0; c2 < cols; c2++) clearCell(curRow, c2); }
                break;
              default: break;
            }
          } else if (s[i] === ']') {
            i++;
            while (i < s.length && s[i] !== '\\x07' && !(s[i] === '\\x1b' && s[i+1] === '\\\\')) i++;
            if (i < s.length && s[i] === '\\x07') i++;
            else if (i < s.length) i += 2;
          } else { i++; }
          continue;
        }

        if (c === '\\r') { curCol = 0; i++; continue; }
        if (c === '\\n') { curRow++; if (curRow >= rows) { curRow = rows - 1; scrollUp(); } i++; continue; }
        if (c === '\\b' || c === '\\x08') { if (curCol > 0) curCol--; i++; continue; }
        if (c === '\\t') { curCol = Math.min(cols - 1, (Math.floor(curCol / 8) + 1) * 8); i++; continue; }
        if (c === '\\x07') { i++; continue; }
        const code = c.charCodeAt(0);
        if (code < 32) { i++; continue; }
        feedChar(c);
        i++;
      }
    }

    // Render grid as HTML with inline color styles
    const htmlLines = [];
    for (let r = 0; r < rows; r++) {
      let line = '';
      let spanOpen = false;
      let prevFg = null, prevBg = null, prevBold = false;
      for (let c2 = 0; c2 < cols; c2++) {
        const cell = grid[r][c2];
        if (cell.fg !== prevFg || cell.bg !== prevBg || cell.bold !== prevBold) {
          if (spanOpen) { line += '</span>'; spanOpen = false; }
          if (cell.fg || cell.bg || cell.bold) {
            let st = '';
            if (cell.fg) st += 'color:' + cell.fg + ';';
            if (cell.bg) st += 'background:' + cell.bg + ';';
            if (cell.bold) st += 'font-weight:bold;';
            line += '<span style="' + st + '">';
            spanOpen = true;
          }
          prevFg = cell.fg; prevBg = cell.bg; prevBold = cell.bold;
        }
        const ch = cell.char;
        if (ch === '<') line += '&lt;';
        else if (ch === '>') line += '&gt;';
        else if (ch === '&') line += '&amp;';
        else line += ch;
      }
      if (spanOpen) line += '</span>';
      htmlLines.push(line.trimEnd());
    }
    while (htmlLines.length > 0 && htmlLines[htmlLines.length - 1] === '') htmlLines.pop();
    termOutput.innerHTML = htmlLines.join('\\n');
    renderAnnotations();
    renderChapterTitle();
  }

  function renderChapterTitle() {
    const overlay = document.getElementById('chapter-title-overlay');
    if (!data.script.chapters.length) { overlay.classList.remove('visible'); fitViewport(); return; }
    // Find the active chapter (last chapter whose time <= currentTime)
    const sorted = [...data.script.chapters].sort((a,b) => a.time - b.time);
    let active = null;
    for (const ch of sorted) {
      if (ch.time <= currentTime) active = ch;
      else break;
    }
    if (active) {
      overlay.textContent = active.label;
      overlay.classList.add('visible');
    } else {
      overlay.classList.remove('visible');
    }
    fitViewport();
  }

  function renderAnnotations() {
    const overlay = document.getElementById('annotation-overlay');
    const active = data.script.annotations.filter(ann =>
      currentTime >= ann.time && currentTime < ann.time + ann.duration
    );

    // Only re-render if the set of visible annotations changed
    const activeKey = active.map(a => a.time + ':' + a.text).join('|');
    if (overlay.dataset.activeKey === activeKey) return;
    overlay.dataset.activeKey = activeKey;

    overlay.innerHTML = '';
    for (const ann of active) {
      const bubble = document.createElement('div');
      bubble.className = 'annotation-bubble'
        + ' style-' + (ann.style || 'callout')
        + ' pos-' + (ann.position || 'top-right');
      bubble.textContent = ann.text;
      overlay.appendChild(bubble);
    }
  }

  // --- Playback ---
  const ICON_PLAY = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
  const ICON_PAUSE = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/></svg>';

  function play() {
    if (currentTime >= data.recording.duration) {
      currentTime = 0;
    }
    playing = true;
    lastTick = performance.now();
    btnPlay.innerHTML = ICON_PAUSE;
    btnPlay.classList.add('active');
    tick();
  }

  function pause() {
    playing = false;
    btnPlay.innerHTML = ICON_PLAY;
    btnPlay.classList.remove('active');
    if (animFrame) cancelAnimationFrame(animFrame);
    animFrame = null;
  }

  function tick() {
    if (!playing) return;
    const now = performance.now();
    const dt = (now - lastTick) / 1000;
    lastTick = now;
    currentTime += dt;

    // Skip over cut regions
    for (const cut of data.script.cuts) {
      if (currentTime >= cut.start && currentTime < cut.end) {
        currentTime = cut.end;
        if (cut.type === 'ellipsis') {
          showCutIndicator();
        }
        break;
      }
    }

    if (currentTime >= data.recording.duration) {
      currentTime = data.recording.duration;
      pause();
    }

    renderTerminal();
    updatePlayhead();
    updateTimeDisplay();
    animFrame = requestAnimationFrame(tick);
  }

  let _renderTerminalRAF = null;

  function seek(time) {
    currentTime = Math.max(0, Math.min(time, data.recording.duration));
    updatePlayhead();
    updateTimeDisplay();
    // Debounce the expensive terminal render to next animation frame
    if (!_renderTerminalRAF) {
      _renderTerminalRAF = requestAnimationFrame(() => {
        _renderTerminalRAF = null;
        renderTerminal();
      });
    }
  }

  // --- UI updates ---
  // Cache layout values for playhead positioning (avoids forced reflow)
  let _phCacheValid = false;
  let _phOffsetX = 0;  // content area left relative to panel
  let _phWidth = 0;    // content area width

  function _cachePlayheadLayout() {
    const contentRect = trackChapters.getBoundingClientRect();
    const panelRect = document.getElementById('timeline-panel').getBoundingClientRect();
    _phOffsetX = contentRect.left - panelRect.left;
    _phWidth = contentRect.width;
    _phCacheValid = true;
  }

  function invalidatePlayheadCache() { _phCacheValid = false; }

  // --- Viewport auto-fit scaling ---
  function fitViewport() {
    const area = document.querySelector('.preview-area');
    const wrapper = document.querySelector('.preview-wrapper');
    if (!area || !wrapper) return;
    // Reset scale to 1 to measure natural size
    wrapper.style.setProperty('--viewport-scale', '1');
    const availW = area.clientWidth - 32;  // 16px padding each side
    const availH = area.clientHeight - 32;
    const natW = wrapper.offsetWidth;
    const natH = wrapper.offsetHeight;
    if (natW <= 0 || natH <= 0) return;
    const scale = Math.min(1, availW / natW, availH / natH);
    wrapper.style.setProperty('--viewport-scale', scale.toFixed(4));
  }

  window.addEventListener('resize', () => {
    invalidatePlayheadCache();
    fitViewport();
  });

  function updatePlayhead() {
    if (!_phCacheValid) _cachePlayheadLayout();
    const x = _phOffsetX + (currentTime / data.recording.duration) * _phWidth;
    document.getElementById('main-playhead').style.transform = 'translateX(' + x + 'px)';
  }

  function updateTimeDisplay() {
    const dur = data ? data.recording.duration : 0;
    timeDisplay.innerHTML = formatTimePrecise(currentTime) + '<span style="opacity:0.5;margin:0 2px">/</span>' + formatTimePrecise(dur);
  }

  // --- Clickable time editor ---
  let timeEditorActive = false;

  timeDisplay.addEventListener('click', () => {
    if (timeEditorActive) return;
    openTimeEditor();
  });

  function openTimeEditor() {
    timeEditorActive = true;
    if (playing) pause();

    const m = Math.floor(currentTime / 60);
    const sec = Math.floor(currentTime % 60);
    const cs = Math.round((currentTime % 1) * 100);

    const editor = document.createElement('span');
    editor.className = 'time-editor';
    editor.innerHTML =
      '<input type="text" inputmode="numeric" class="te-min" maxlength="2" value="' + String(m).padStart(2, '0') + '" placeholder="mm">' +
      '<span class="te-sep">:</span>' +
      '<input type="text" inputmode="numeric" class="te-sec" maxlength="2" value="' + String(sec).padStart(2, '0') + '" placeholder="ss">' +
      '<span class="te-sep">.</span>' +
      '<input type="text" inputmode="numeric" class="te-cs" maxlength="2" value="' + String(cs).padStart(2, '0') + '" placeholder="cs">';

    timeDisplay.style.display = 'none';
    timeDisplay.parentNode.insertBefore(editor, timeDisplay.nextSibling);

    const inputs = editor.querySelectorAll('input');
    inputs[0].focus();
    inputs[0].select();

    // Auto-advance: when field is full, move to next; strip non-digits
    inputs.forEach((inp, i) => {
      inp.addEventListener('input', () => {
        inp.value = inp.value.replace(/[^0-9]/g, '');
        if (inp.value.length >= 2 && i < inputs.length - 1) {
          inputs[i + 1].focus();
          inputs[i + 1].select();
        }
      });
    });

    function commit() {
      const dur = data.recording.duration;
      let minutes = parseInt(inputs[0].value, 10) || 0;
      let seconds = parseInt(inputs[1].value, 10) || 0;
      let centis = parseInt(inputs[2].value, 10) || 0;

      // Clamp individual fields
      minutes = Math.max(0, minutes);
      seconds = Math.max(0, Math.min(59, seconds));
      centis = Math.max(0, Math.min(99, centis));

      let time = minutes * 60 + seconds + centis / 100;
      // Clamp to duration
      time = Math.max(0, Math.min(time, dur));

      seek(time);
      closeEditor();
    }

    function closeEditor() {
      timeEditorActive = false;
      editor.remove();
      timeDisplay.style.display = '';
      updateTimeDisplay();
    }

    // Commit on Enter, cancel on Escape
    editor.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); commit(); }
      else if (e.key === 'Escape') { e.preventDefault(); closeEditor(); }
    });

    // Commit on blur (clicking away)
    editor.addEventListener('focusout', (e) => {
      // Only close if focus left the editor entirely
      setTimeout(() => {
        if (!editor.contains(document.activeElement)) {
          commit();
        }
      }, 0);
    });
  }

  // --- Selection / Properties ---
  function selectChapter(idx) {
    selectedItem = { type: 'chapter', index: idx };
    clearAllHighlights();
    const chEls = trackChapters.querySelectorAll('.track-item-chapter');
    if (chEls[idx]) chEls[idx].classList.add('selected');
    const ch = data.script.chapters[idx];
    propsPanel.innerHTML = `
      <div class="prop-title">Chapter</div>
      <div class="prop-field">
        <div class="prop-label">Time (s)</div>
        <input class="prop-input" type="number" step="0.01" value="${ch.time.toFixed(2)}" id="prop-time">
      </div>
      <div class="prop-field">
        <div class="prop-label">Label</div>
        <input class="prop-input" type="text" value="${escAttr(ch.label)}" id="prop-label">
      </div>
      <div class="prop-actions">
        <button class="btn" onclick="undoSelected()">Undo</button>
        <button class="btn" style="color:var(--cut)" onclick="deleteSelected()">Delete</button>
      </div>
    `;
    propsPanel.classList.add('open');
    attachLiveListeners();
  }

  function selectAnnotation(idx) {
    selectedItem = { type: 'annotation', index: idx };
    clearAllHighlights();
    const annEls = trackAnnotations.querySelectorAll('.track-item-annotation');
    if (annEls[idx]) annEls[idx].classList.add('selected');
    const ann = data.script.annotations[idx];
    propsPanel.innerHTML = `
      <div class="prop-title">Annotation</div>
      <div class="prop-field">
        <div class="prop-label">Time (s)</div>
        <input class="prop-input" type="number" step="0.01" value="${ann.time.toFixed(2)}" id="prop-time">
      </div>
      <div class="prop-field">
        <div class="prop-label">Duration (s)</div>
        <input class="prop-input" type="number" step="0.1" value="${ann.duration.toFixed(2)}" id="prop-duration">
      </div>
      <div class="prop-field">
        <div class="prop-label">Text</div>
        <input class="prop-input" type="text" value="${escAttr(ann.text)}" id="prop-text">
      </div>
      <div class="prop-field">
        <div class="prop-label">Position</div>
        <select class="prop-select" id="prop-position">
          <option value="top-left" ${ann.position==='top-left'?'selected':''}>Top Left</option>
          <option value="top-right" ${ann.position==='top-right'?'selected':''}>Top Right</option>
          <option value="bottom-left" ${ann.position==='bottom-left'?'selected':''}>Bottom Left</option>
          <option value="bottom-right" ${ann.position==='bottom-right'?'selected':''}>Bottom Right</option>
        </select>
      </div>
      <div class="prop-field">
        <div class="prop-label">Style</div>
        <select class="prop-select" id="prop-style">
          <option value="callout" ${ann.style==='callout'?'selected':''}>Callout</option>
          <option value="subtle" ${ann.style==='subtle'?'selected':''}>Subtle</option>
          <option value="highlight" ${ann.style==='highlight'?'selected':''}>Highlight</option>
        </select>
      </div>
      <div class="prop-actions">
        <button class="btn" onclick="undoSelected()">Undo</button>
        <button class="btn" style="color:var(--cut)" onclick="deleteSelected()">Delete</button>
      </div>
    `;
    propsPanel.classList.add('open');
    attachLiveListeners();
  }

  function highlightCut(idx, edge) {
    // Clear all cut selections
    trackCuts.querySelectorAll('.track-item-cut.selected').forEach(el => el.classList.remove('selected'));
    trackCuts.querySelectorAll('.cut-handle.selected').forEach(el => el.classList.remove('selected'));
    // Highlight the selected cut
    const cutEls = trackCuts.querySelectorAll('.track-item-cut');
    if (cutEls[idx]) {
      cutEls[idx].classList.add('selected');
      if (edge) {
        // Highlight specific edge handle
        const handle = cutEls[idx].querySelector('.cut-handle-' + (edge === 'start' ? 'left' : 'right'));
        if (handle) handle.classList.add('selected');
      }
    }
  }

  function highlightAnnotation(idx, edge) {
    trackAnnotations.querySelectorAll('.track-item-annotation.selected').forEach(el => el.classList.remove('selected'));
    trackAnnotations.querySelectorAll('.ann-handle.selected').forEach(el => el.classList.remove('selected'));
    const annEls = trackAnnotations.querySelectorAll('.track-item-annotation');
    if (annEls[idx]) {
      annEls[idx].classList.add('selected');
      if (edge) {
        const handle = annEls[idx].querySelector('.ann-handle-' + (edge === 'start' ? 'left' : 'right'));
        if (handle) handle.classList.add('selected');
      }
    }
  }

  function selectCut(idx) {
    selectedItem = { type: 'cut', index: idx };
    clearAllHighlights();
    highlightCut(idx, null);
    const cut = data.script.cuts[idx];
    propsPanel.innerHTML = `
      <div class="prop-title">Cut Region</div>
      <div class="prop-field">
        <div class="prop-label">From (s)</div>
        <input class="prop-input" type="number" step="0.01" value="${cut.start.toFixed(2)}" id="prop-start">
      </div>
      <div class="prop-field">
        <div class="prop-label">To (s)</div>
        <input class="prop-input" type="number" step="0.01" value="${cut.end.toFixed(2)}" id="prop-end">
      </div>
      <div class="prop-field">
        <div class="prop-label">Cut type</div>
        <select class="prop-select" id="prop-type">
          <option value="jump" ${cut.type==='jump'?'selected':''}>Jump</option>
          <option value="ellipsis" ${cut.type==='ellipsis'?'selected':''}>Ellipsis (…)</option>
        </select>
      </div>
      <div class="prop-actions">
        <button class="btn" onclick="undoSelected()">Undo</button>
        <button class="btn" style="color:var(--cut)" onclick="deleteSelected()">Delete</button>
      </div>
    `;
    propsPanel.classList.add('open');
    attachLiveListeners();
  }

  // --- Live input listeners for inspector ---
  let undoSnapshot = null;

  function attachLiveListeners() {
    // Snapshot for undo
    if (selectedItem) {
      const { type, index } = selectedItem;
      if (type === 'chapter') undoSnapshot = { ...data.script.chapters[index] };
      else if (type === 'annotation') undoSnapshot = { ...data.script.annotations[index] };
      else if (type === 'cut') undoSnapshot = { ...data.script.cuts[index] };
    }
    propsPanel.querySelectorAll('.prop-input, .prop-select').forEach(el => {
      el.addEventListener('input', liveApply);
      el.addEventListener('change', liveApply);
    });
    // Add custom number spinner buttons
    propsPanel.querySelectorAll('.prop-input[type="number"]').forEach(input => {
      const wrap = document.createElement('div');
      wrap.className = 'number-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
      const step = parseFloat(input.step) || 1;
      const btnUp = document.createElement('button');
      btnUp.type = 'button';
      btnUp.className = 'num-btn num-btn-up';
      btnUp.innerHTML = '&#x25B4;';
      btnUp.addEventListener('click', () => { input.value = (parseFloat(input.value) + step).toFixed(2); input.dispatchEvent(new Event('input')); });
      const btnDown = document.createElement('button');
      btnDown.type = 'button';
      btnDown.className = 'num-btn num-btn-down';
      btnDown.innerHTML = '&#x25BE;';
      btnDown.addEventListener('click', () => { input.value = (parseFloat(input.value) - step).toFixed(2); input.dispatchEvent(new Event('input')); });
      wrap.appendChild(btnUp);
      wrap.appendChild(btnDown);
    });
  }

  function liveApply() {
    if (!selectedItem) return;
    const { type, index } = selectedItem;

    if (type === 'chapter') {
      data.script.chapters[index].time = parseFloat(document.getElementById('prop-time').value) || 0;
      data.script.chapters[index].label = document.getElementById('prop-label').value;
    } else if (type === 'annotation') {
      data.script.annotations[index].time = parseFloat(document.getElementById('prop-time').value) || 0;
      data.script.annotations[index].duration = parseFloat(document.getElementById('prop-duration').value) || 1;
      data.script.annotations[index].text = document.getElementById('prop-text').value;
      data.script.annotations[index].position = document.getElementById('prop-position').value;
      data.script.annotations[index].style = document.getElementById('prop-style').value;
    } else if (type === 'cut') {
      data.script.cuts[index].start = parseFloat(document.getElementById('prop-start').value) || 0;
      data.script.cuts[index].end = parseFloat(document.getElementById('prop-end').value) || 0;
      data.script.cuts[index].type = document.getElementById('prop-type').value;
    }

    markDirty();
    renderTracks();
    updatePlayhead();
  }

  window.undoSelected = function() {
    if (!selectedItem || !undoSnapshot) return;
    const { type, index } = selectedItem;
    if (type === 'chapter') data.script.chapters[index] = { ...undoSnapshot };
    else if (type === 'annotation') data.script.annotations[index] = { ...undoSnapshot };
    else if (type === 'cut') data.script.cuts[index] = { ...undoSnapshot };
    renderTracks();
    updatePlayhead();
    // Re-open panel with restored values
    if (type === 'chapter') selectChapter(index);
    else if (type === 'annotation') selectAnnotation(index);
    else if (type === 'cut') selectCut(index);
    showToast('Reverted');
  };

  // --- Dirty state ---
  let isDirty = false;
  const saveBtn = document.getElementById('btn-save');

  function markDirty() {
    if (isDirty) return;
    isDirty = true;
    saveBtn.textContent = 'Save *';
    saveBtn.classList.add('btn-dirty');
  }

  function clearDirty() {
    isDirty = false;
    saveBtn.textContent = 'Save';
    saveBtn.classList.remove('btn-dirty');
  }

  window.applyProps = function() {
    liveApply();
  };

  window.deleteSelected = function() {
    if (!selectedItem) return;
    const { type, index } = selectedItem;

    if (type === 'chapter') data.script.chapters.splice(index, 1);
    else if (type === 'annotation') data.script.annotations.splice(index, 1);
    else if (type === 'cut') data.script.cuts.splice(index, 1);

    selectedItem = null;
    propsPanel.classList.remove('open');
    renderTracks();
    updatePlayhead();
    markDirty();
    showToast('Deleted');
  };

  // --- Chapter drag-to-move ---
  function startChapterDrag(chIdx, e) {
    e.preventDefault();
    const startX = e.clientX;
    let moved = false;
    selectChapter(chIdx);
    seek(data.script.chapters[chIdx].time);
    const rect = trackChapters.getBoundingClientRect();

    function onMove(ev) {
      moved = true;
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * data.recording.duration, data.recording.duration)));
      data.script.chapters[chIdx].time = t;
      renderTracks();
      updatePlayhead();
      // Re-highlight after re-render
      const chEls = trackChapters.querySelectorAll('.track-item-chapter');
      if (chEls[chIdx]) chEls[chIdx].classList.add('selected');
      seek(t);
      // Update inspector input live
      const timeInput = document.getElementById('prop-time');
      if (timeInput) timeInput.value = t.toFixed(2);
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (moved) {
        markDirty();
        showToast('Chapter moved to ' + formatTimePrecise(data.script.chapters[chIdx].time));
      }
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // --- Click on chapters track to create ---
  trackChapters.addEventListener('mousedown', (e) => {
    if (e.target !== trackChapters) return;
    e.preventDefault();
    const rect = trackChapters.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const clickTime = roundTime(ratio * data.recording.duration);
    addChapterAt(clickTime);
  });

  // --- Add items ---
  function addChapter() {
    addChapterAt(currentTime);
  }

  function addChapterAt(time) {
    const t = roundTime(time);
    data.script.chapters.push({ time: t, label: 'Chapter' });
    renderTracks();
    updatePlayhead();
    markDirty();
    const idx = data.script.chapters.length - 1;
    selectChapter(idx);
    seek(t);
    showToast('Chapter added at ' + formatTimePrecise(t));
  }

  function addAnnotation() {
    addAnnotationAt(currentTime);
  }

  function addCut() {
    addCutAt(currentTime);
  }

  function addCutAt(time) {
    const start = roundTime(time);
    const end = roundTime(Math.min(time + 1, data.recording.duration));
    if (end > start) {
      data.script.cuts.push({ start: start, end: end, type: 'jump' });
      renderTracks();
      updatePlayhead();
      markDirty();
      const idx = data.script.cuts.length - 1;
      selectCut(idx);
      showToast('Cut added — drag edges to adjust');
    }
  }

  // --- Cut drag-to-create ---
  let cutDragState = null;

  trackCuts.addEventListener('mousedown', (e) => {
    // Only start drag if clicking on the track itself (not on a cut item)
    if (e.target !== trackCuts) return;
    e.preventDefault();
    const rect = trackCuts.getBoundingClientRect();
    const startX = e.clientX;
    const startRatio = (startX - rect.left) / rect.width;
    const startTime = roundTime(startRatio * data.recording.duration);

    // Create a temporary cut
    const tempIdx = data.script.cuts.length;
    data.script.cuts.push({ start: startTime, end: startTime, type: 'jump' });
    renderTracks();
    updatePlayhead();

    cutDragState = { index: tempIdx, startTime: startTime };

    function onMove(ev) {
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * data.recording.duration, data.recording.duration)));
      const cut = data.script.cuts[cutDragState.index];
      if (t < cutDragState.startTime) {
        cut.start = t;
        cut.end = cutDragState.startTime;
      } else {
        cut.start = cutDragState.startTime;
        cut.end = t;
      }
      renderTracks();
      updatePlayhead();
    }

    function onUp(ev) {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      const cut = data.script.cuts[cutDragState.index];
      if (cut.end - cut.start < 0.15) {
        // Too small — treat as a click: drop a 1s cut at click position
        data.script.cuts.splice(cutDragState.index, 1);
        const ratio = (ev.clientX - rect.left) / rect.width;
        const clickTime = ratio * data.recording.duration;
        addCutAt(clickTime);
      } else {
        selectCut(cutDragState.index);
        markDirty();
        showToast('Cut: ' + formatTimePrecise(cut.start) + ' → ' + formatTimePrecise(cut.end));
      }
      cutDragState = null;
      renderTracks();
      updatePlayhead();
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  // --- Box drag-to-reposition (annotations and cuts) ---
  function startBoxDrag(type, index, e) {
    e.preventDefault();
    const startX = e.clientX;
    const track = type === 'annotation' ? trackAnnotations : trackCuts;
    const rect = track.getBoundingClientRect();
    const duration = data.recording.duration;
    let dragged = false;

    let item, itemStart, itemDuration;
    if (type === 'annotation') {
      item = data.script.annotations[index];
      itemStart = item.time;
      itemDuration = item.duration;
    } else {
      item = data.script.cuts[index];
      itemStart = item.start;
      itemDuration = item.end - item.start;
    }

    const origStart = itemStart;

    function onMove(ev) {
      const dx = ev.clientX - startX;
      if (!dragged && Math.abs(dx) < 4) return;
      dragged = true;
      const dt = (dx / rect.width) * duration;
      let newStart = roundTime(Math.max(0, Math.min(origStart + dt, duration - itemDuration)));
      if (type === 'annotation') {
        item.time = newStart;
      } else {
        item.start = newStart;
        item.end = roundTime(newStart + itemDuration);
      }
      renderTracks();
      updatePlayhead();
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (dragged) {
        markDirty();
      }
      // Always select on mouseup (whether drag or click)
      if (type === 'annotation') selectAnnotation(index);
      else selectCut(index);
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // --- Cut handle drag-to-resize ---
  let activeEdge = null; // { index, edge: 'start'|'end' }

  function startHandleDrag(cutIdx, edge, e) {
    e.preventDefault();
    activeEdge = { index: cutIdx, edge: edge };
    selectCut(cutIdx);
    selectedItem = { type: 'cut', index: cutIdx, edge: edge };
    highlightCut(cutIdx, edge);
    // Seek playhead to the edge being grabbed
    const cut = data.script.cuts[cutIdx];
    seek(edge === 'start' ? cut.start : cut.end);
    const rect = trackCuts.getBoundingClientRect();

    function onMove(ev) {
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * data.recording.duration, data.recording.duration)));
      const cut = data.script.cuts[cutIdx];
      if (edge === 'start') {
        cut.start = Math.min(t, cut.end - 0.1);
      } else {
        cut.end = Math.max(t, cut.start + 0.1);
      }
      renderTracks();
      updatePlayhead();
      seek(t);
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      activeEdge = null;
      markDirty();
      showToast('Edge set — use ←/→ arrows to fine-tune');
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // --- Cut edge nudge via keyboard ---
  function nudgeCutEdge(cutIdx, edge, delta) {
    const cut = data.script.cuts[cutIdx];
    if (!cut) return;
    if (edge === 'start') {
      cut.start = roundTime(Math.max(0, Math.min(cut.start + delta, cut.end - 0.1)));
      seek(cut.start);
    } else {
      cut.end = roundTime(Math.max(cut.start + 0.1, Math.min(cut.end + delta, data.recording.duration)));
      seek(cut.end);
    }
    renderTracks();
    updatePlayhead();
    highlightCut(cutIdx, edge);
    // Update the props panel inputs live
    const startInput = document.getElementById('prop-start');
    const endInput = document.getElementById('prop-end');
    if (startInput) startInput.value = cut.start.toFixed(2);
    if (endInput) endInput.value = cut.end.toFixed(2);
    markDirty();
  }

  // --- Annotation handle drag-to-resize ---
  let activeAnnEdge = null; // { index, edge: 'start'|'end' }

  function startAnnotationHandleDrag(annIdx, edge, e) {
    e.preventDefault();
    activeAnnEdge = { index: annIdx, edge: edge };
    selectAnnotation(annIdx);
    selectedItem = { type: 'annotation', index: annIdx, edge: edge };
    // Seek playhead to the edge being grabbed
    const ann = data.script.annotations[annIdx];
    seek(edge === 'start' ? ann.time : ann.time + ann.duration);
    // Highlight the handle
    const annEls = trackAnnotations.querySelectorAll('.track-item-annotation');
    if (annEls[annIdx]) {
      const handle = annEls[annIdx].querySelector('.ann-handle-' + (edge === 'start' ? 'left' : 'right'));
      if (handle) handle.classList.add('selected');
    }
    const rect = trackAnnotations.getBoundingClientRect();

    function onMove(ev) {
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * data.recording.duration, data.recording.duration)));
      const ann = data.script.annotations[annIdx];
      if (edge === 'start') {
        const end = ann.time + ann.duration;
        ann.time = Math.min(t, end - 0.1);
        ann.duration = roundTime(end - ann.time);
      } else {
        const newEnd = Math.max(t, ann.time + 0.1);
        ann.duration = roundTime(newEnd - ann.time);
      }
      renderTracks();
      updatePlayhead();
      seek(t);
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      activeAnnEdge = null;
      markDirty();
      showToast('Edge set — use ←/→ arrows to fine-tune');
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // --- Annotation edge nudge via keyboard ---
  function nudgeAnnotationEdge(annIdx, edge, delta) {
    const ann = data.script.annotations[annIdx];
    if (!ann) return;
    const end = ann.time + ann.duration;
    if (edge === 'start') {
      const newStart = roundTime(Math.max(0, Math.min(ann.time + delta, end - 0.1)));
      ann.duration = roundTime(end - newStart);
      ann.time = newStart;
      seek(ann.time);
    } else {
      const newEnd = roundTime(Math.max(ann.time + 0.1, Math.min(end + delta, data.recording.duration)));
      ann.duration = roundTime(newEnd - ann.time);
      seek(ann.time + ann.duration);
    }
    renderTracks();
    updatePlayhead();
    highlightAnnotation(annIdx, edge);
    // Update the props panel inputs live
    const timeInput = document.getElementById('prop-time');
    const durInput = document.getElementById('prop-duration');
    if (timeInput) timeInput.value = ann.time.toFixed(2);
    if (durInput) durInput.value = ann.duration.toFixed(2);
    markDirty();
  }

  // --- Annotation drag-to-create ---
  let annDragState = null;

  trackAnnotations.addEventListener('mousedown', (e) => {
    if (e.target !== trackAnnotations) return;
    e.preventDefault();
    const rect = trackAnnotations.getBoundingClientRect();
    const startX = e.clientX;
    const startRatio = (startX - rect.left) / rect.width;
    const startTime = roundTime(startRatio * data.recording.duration);

    // Create a temporary annotation
    const tempIdx = data.script.annotations.length;
    data.script.annotations.push({ time: startTime, duration: 0, text: 'Annotation', position: 'top-right', style: 'callout' });
    renderTracks();
    updatePlayhead();

    annDragState = { index: tempIdx, startTime: startTime };

    function onMove(ev) {
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * data.recording.duration, data.recording.duration)));
      const ann = data.script.annotations[annDragState.index];
      if (t < annDragState.startTime) {
        ann.time = t;
        ann.duration = roundTime(annDragState.startTime - t);
      } else {
        ann.time = annDragState.startTime;
        ann.duration = roundTime(t - annDragState.startTime);
      }
      renderTracks();
      updatePlayhead();
    }

    function onUp(ev) {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      const ann = data.script.annotations[annDragState.index];
      if (ann.duration < 0.15) {
        // Too small — treat as a click: drop a 1s annotation at click position
        data.script.annotations.splice(annDragState.index, 1);
        const ratio = (ev.clientX - rect.left) / rect.width;
        const clickTime = ratio * data.recording.duration;
        addAnnotationAt(clickTime);
      } else {
        selectAnnotation(annDragState.index);
        markDirty();
        showToast('Annotation: ' + formatTimePrecise(ann.time) + ' → ' + formatTimePrecise(ann.time + ann.duration));
      }
      annDragState = null;
      renderTracks();
      updatePlayhead();
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  function addAnnotationAt(time) {
    const start = roundTime(time);
    const end = roundTime(Math.min(time + 1, data.recording.duration));
    if (end > start) {
      data.script.annotations.push({ time: start, duration: roundTime(end - start), text: 'Annotation', position: 'top-right', style: 'callout' });
      renderTracks();
      updatePlayhead();
      markDirty();
      const idx = data.script.annotations.length - 1;
      selectAnnotation(idx);
      showToast('Annotation added — drag edges to adjust');
    }
  }

  // --- Save ---
  function save() {
    fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data.script),
    })
    .then(r => r.json())
    .then(res => {
      if (res.ok) { clearDirty(); showToast('Saved to ' + res.path); }
      else showToast('Error: ' + res.error);
    })
    .catch(e => showToast('Save failed: ' + e.message));
  }

  // --- YAML Preview Modal ---
  const yamlBackdrop = document.getElementById('yaml-modal-backdrop');
  const yamlContent = document.getElementById('yaml-modal-content');
  const yamlTitle = document.getElementById('yaml-modal-title');
  const yamlStatus = document.getElementById('yaml-status');
  const yamlClose = document.getElementById('yaml-modal-close');

  function showYamlPreview() {
    fetch('/api/preview-yaml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data.script),
    })
    .then(r => r.json())
    .then(res => {
      if (res.yaml) {
        yamlTitle.textContent = data.source_file.replace('.termshow', '.termshow.yml');
        yamlStatus.textContent = isDirty ? 'unsaved' : 'saved';
        yamlStatus.className = 'yaml-status ' + (isDirty ? 'unsaved' : 'saved');
        yamlContent.textContent = res.yaml;
        yamlBackdrop.classList.add('visible');
      } else {
        showToast('Error generating YAML');
      }
    })
    .catch(e => showToast('YAML preview failed: ' + e.message));
  }

  function hideYamlPreview() {
    yamlBackdrop.classList.remove('visible');
  }

  yamlClose.addEventListener('click', hideYamlPreview);
  yamlBackdrop.addEventListener('click', (e) => {
    if (e.target === yamlBackdrop) hideYamlPreview();
  });

  document.getElementById('btn-view-yaml').addEventListener('click', showYamlPreview);

  // --- Timeline ruler drag-to-scrub ---
  ruler.addEventListener('mousedown', (e) => {
    e.preventDefault();
    const rect = ruler.getBoundingClientRect();
    const duration = data.recording.duration;
    let lastRenderTime = 0;
    // Ensure playhead layout cache is fresh for this drag
    _cachePlayheadLayout();
    const ph = document.getElementById('main-playhead');

    function scrubTo(clientX) {
      const r = Math.max(0, Math.min((clientX - rect.left) / rect.width, 1));
      currentTime = r * duration;
      // Direct transform update — no getBoundingClientRect, no reflow
      const x = _phOffsetX + r * _phWidth;
      ph.style.transform = 'translateX(' + x + 'px)';
      updateTimeDisplay();
      // Throttle terminal render to ~20fps during drag
      const now = performance.now();
      if (now - lastRenderTime > 50) {
        lastRenderTime = now;
        renderTerminal();
      }
    }

    scrubTo(e.clientX);

    function onMove(ev) {
      scrubTo(ev.clientX);
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      renderTerminal();
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  [trackChapters, trackAnnotations, trackCuts].forEach(track => {
    track.addEventListener('click', (e) => {
      if (e.target === track || e.target.classList.contains('playhead')) {
        const rect = track.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const ratio = x / rect.width;
        seek(ratio * data.recording.duration);
      }
    });
  });

  // --- Event listeners ---
  function flashBtn(btn) {
    btn.classList.remove('flash');
    void btn.offsetWidth; // force reflow to restart animation
    btn.classList.add('flash');
    btn.addEventListener('animationend', () => btn.classList.remove('flash'), { once: true });
  }

  document.getElementById('btn-play').addEventListener('click', () => {
    playing ? pause() : play();
  });
  document.getElementById('btn-rewind').addEventListener('click', () => {
    flashBtn(document.getElementById('btn-rewind'));
    seek(0);
  });
  document.getElementById('btn-prev-chapter').addEventListener('click', () => {
    flashBtn(document.getElementById('btn-prev-chapter'));
    prevChapter();
  });
  document.getElementById('btn-next-chapter').addEventListener('click', () => {
    flashBtn(document.getElementById('btn-next-chapter'));
    nextChapter();
  });
  document.getElementById('btn-add-chapter').addEventListener('click', addChapter);
  document.getElementById('btn-add-annotation').addEventListener('click', addAnnotation);
  document.getElementById('btn-add-cut').addEventListener('click', addCut);
  document.getElementById('btn-save').addEventListener('click', save);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Don't capture when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === ' ') { e.preventDefault(); playing ? pause() : play(); }
    else if (e.key === 'c' || e.key === 'C') { addChapter(); }
    else if (e.key === 'a' && !e.metaKey) { addAnnotation(); }
    else if (e.key === 'x' || e.key === 'X') { addCut(); }
    else if (e.key === 'ArrowRight') {
      e.preventDefault();
      if (selectedItem && selectedItem.type === 'cut' && selectedItem.edge) {
        nudgeCutEdge(selectedItem.index, selectedItem.edge, 0.01);
      } else if (selectedItem && selectedItem.type === 'annotation' && selectedItem.edge) {
        nudgeAnnotationEdge(selectedItem.index, selectedItem.edge, 0.01);
      } else { seek(currentTime + 1); }
    }
    else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      if (selectedItem && selectedItem.type === 'cut' && selectedItem.edge) {
        nudgeCutEdge(selectedItem.index, selectedItem.edge, -0.01);
      } else if (selectedItem && selectedItem.type === 'annotation' && selectedItem.edge) {
        nudgeAnnotationEdge(selectedItem.index, selectedItem.edge, -0.01);
      } else { seek(currentTime - 1); }
    }
    else if (e.key === '.') { nextChapter(); }
    else if (e.key === ',') { prevChapter(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { window.deleteSelected(); }
    else if (e.key === 'Escape') {
      if (yamlBackdrop.classList.contains('visible')) { hideYamlPreview(); }
      else { propsPanel.classList.remove('open'); selectedItem = null; clearCutHighlights(); }
    }
    else if (e.key === 's' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
    else if (e.key === 'y' || e.key === 'Y') { showYamlPreview(); }
  });

  // Close panel on click outside
  document.addEventListener('click', (e) => {
    if (!propsPanel.contains(e.target) && !e.target.closest('.track-item-chapter, .track-item-annotation, .track-item-cut')) {
      propsPanel.classList.remove('open');
      selectedItem = null;
      clearCutHighlights();
    }
  });

  function clearAllHighlights() {
    trackChapters.querySelectorAll('.track-item-chapter.selected').forEach(el => el.classList.remove('selected'));
    trackAnnotations.querySelectorAll('.track-item-annotation.selected').forEach(el => el.classList.remove('selected'));
    trackAnnotations.querySelectorAll('.ann-handle.selected').forEach(el => el.classList.remove('selected'));
    trackCuts.querySelectorAll('.track-item-cut.selected').forEach(el => el.classList.remove('selected'));
    trackCuts.querySelectorAll('.cut-handle.selected').forEach(el => el.classList.remove('selected'));
  }

  function clearCutHighlights() {
    clearAllHighlights();
  }

  function nextChapter() {
    if (!data || !data.script.chapters.length) return;
    const sorted = [...data.script.chapters].sort((a,b) => a.time - b.time);
    for (const ch of sorted) {
      if (ch.time > currentTime + 0.1) { seek(ch.time); return; }
    }
  }

  function prevChapter() {
    if (!data || !data.script.chapters.length) return;
    const sorted = [...data.script.chapters].sort((a,b) => a.time - b.time);
    for (let i = sorted.length - 1; i >= 0; i--) {
      if (sorted[i].time < currentTime - 0.5) { seek(sorted[i].time); return; }
    }
    seek(0);
  }

  // --- Utilities ---
  function timeToPct(t) {
    return ((t / data.recording.duration) * 100) + '%';
  }

  function durationToPct(d) {
    return ((d / data.recording.duration) * 100) + '%';
  }

  function formatTime(s) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return m + ':' + (sec < 10 ? '0' : '') + sec;
  }

  function formatTimePrecise(s) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return String(m).padStart(2, '0') + ':' + (sec < 10 ? '0' : '') + sec.toFixed(2);
  }

  function formatTimeShort(s) {
    if (s < 60) return s + 's';
    return Math.floor(s/60) + ':' + (s%60 < 10 ? '0' : '') + (s%60) + '';
  }

  function roundTime(t) {
    return Math.round(t * 100) / 100;
  }

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function escAttr(s) {
    return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
  }

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
  }

  let cutIndicatorTimeout = null;
  function showCutIndicator() {
    const el = document.getElementById('cut-indicator');
    el.classList.add('flash');
    if (cutIndicatorTimeout) clearTimeout(cutIndicatorTimeout);
    cutIndicatorTimeout = setTimeout(() => {
      el.classList.remove('flash');
      cutIndicatorTimeout = null;
    }, 600);
  }
})();
</script>
</body>
</html>
"""
