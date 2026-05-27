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
                "font_family": script.font_family if script else None,
                "prompt": script.prompt if script else None,
                "prompt_pattern": script.prompt_pattern if script else None,
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
                    "width": ann.width,
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
            "snippets": [
                {
                    "time": cmd.time,
                    "duration": cmd.duration,
                    "text": cmd.text,
                    "match": cmd.match,
                    "label": cmd.label,
                }
                for cmd in (script.snippets if script else [])
            ],
            "highlights": [
                {
                    "time": hl.time,
                    "duration": hl.duration,
                    "target": {
                        **({"region": hl.target.region} if hl.target.region else {}),
                        **({"match": hl.target.match} if hl.target.match else {}),
                        **({"group": hl.target.group} if hl.target.group else {}),
                        **({"lines": hl.target.lines} if hl.target.lines else {}),
                        **({"track_scroll": True} if hl.target.track_scroll else {}),
                    },
                    "style": hl.style,
                    "color": hl.color,
                    "badge_text": hl.badge_text,
                    "badge_icon": hl.badge_icon,
                    "fade_in": hl.fade_in,
                    "fade_out": hl.fade_out,
                    "pulse": hl.pulse,
                }
                for hl in (script.highlights if script else [])
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
        if settings.get("font_family"):
            lines.append(f'  font_family: "{settings["font_family"]}"')
        if settings.get("prompt"):
            lines.append(f'  prompt: "{settings["prompt"]}"')
        if settings.get("prompt_pattern"):
            lines.append(f"  prompt_pattern: '{settings['prompt_pattern']}'")
        lines.append("")

    chapters = script_data.get("chapters", [])
    if chapters:
        lines.append("chapters:")
        for ch in sorted(chapters, key=lambda c: c["time"]):
            lines.append(f"  - at: {round(ch['time'], 2)}")
            lines.append(f'    label: "{ch["label"]}"')
        lines.append("")

    annotations = script_data.get("annotations", [])
    if annotations:
        lines.append("annotations:")
        for ann in sorted(annotations, key=lambda a: a["time"]):
            lines.append(f"  - at: {round(ann['time'], 2)}")
            lines.append(f"    duration: {round(ann['duration'], 2)}")
            lines.append(f'    text: "{ann["text"]}"')
            lines.append(f"    position: {ann['position']}")
            width = ann.get("width", "medium")
            if width != "medium":
                lines.append(f"    width: {width}")
            lines.append(f"    style: {ann['style']}")
        lines.append("")

    cuts = script_data.get("cuts", [])
    if cuts:
        lines.append("cuts:")
        for cut in sorted(cuts, key=lambda c: c["start"]):
            lines.append(f"  - from: {round(cut['start'], 2)}")
            lines.append(f"    to: {round(cut['end'], 2)}")
            lines.append(f"    type: {cut['type']}")
        lines.append("")

    snippets = script_data.get("snippets", [])
    if snippets:
        lines.append("snippets:")
        for cmd in sorted(snippets, key=lambda c: c["time"]):
            lines.append(f"  - at: {round(cmd['time'], 2)}")
            lines.append(f"    duration: {round(cmd['duration'], 2)}")
            text = cmd.get("text", "")
            match = cmd.get("match", "")
            if text:
                lines.append(f'    text: "{text}"')
            if match:
                lines.append(f"    match: '{match}'")
            label = cmd.get("label", "")
            if label:
                lines.append(f'    label: "{label}"')
        lines.append("")

    highlights = script_data.get("highlights", [])
    if highlights:
        lines.append("highlights:")
        for hl in sorted(highlights, key=lambda h: h["time"]):
            lines.append(f"  - at: {round(hl['time'], 2)}")
            lines.append(f"    duration: {round(hl['duration'], 2)}")
            lines.append(f"    style: {hl.get('style', 'outline')}")
            color = hl.get("color", "#f1fa8c")
            if color and color != "#f1fa8c":
                lines.append(f"    color: '{color}'")
            target = hl.get("target", {})
            if target:
                lines.append("    target:")
                if target.get("region"):
                    r = target["region"]
                    lines.append(
                        f"      region: {{row: {r.get('row', 0)}, col: {r.get('col', 0)}, width: {r.get('width', 10)}, height: {r.get('height', 1)}}}"
                    )
                if target.get("match"):
                    lines.append(f"      match: '{target['match']}'")
                    if target.get("group"):
                        lines.append(f"      group: {target['group']}")
                if target.get("lines"):
                    lines.append(f"      lines: {target['lines']}")
                if target.get("track_scroll"):
                    lines.append("      track_scroll: true")
            badge_text = hl.get("badge_text", "")
            if badge_text:
                lines.append(f'    badge_text: "{badge_text}"')
            if hl.get("pulse"):
                lines.append("    pulse: true")
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
    editor_data["source_bytes"] = source_path.stat().st_size

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
  --snippet: #89b4fa;
  --highlight: #cba6f7;
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
  flex: 0 0 auto;
  height: 45%;
  min-height: 150px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 16px;
  position: relative;
  overflow: hidden;
}

.resize-handle {
  flex-shrink: 0;
  height: 6px;
  background: var(--surface2);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  cursor: row-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.resize-handle:hover,
.resize-handle.active {
  background: var(--border);
}

.resize-handle::after {
  content: '';
  width: 32px;
  height: 2px;
  border-radius: 1px;
  background: var(--text-dim);
  opacity: 0.5;
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
  position: relative;
  z-index: 1;
  width: calc(var(--term-cols) * 1ch + 24px);
  height: calc(var(--term-rows) * 1lh + 24px);
}

.preview-wrapper {
  position: relative;
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

.chapter-title-overlay.visible + .snippet-preview + .preview-viewport {
  border-top: none;
  border-radius: 0 0 8px 8px;
}

.snippet-preview {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 10;
  padding: 4px 10px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.snippet-preview.visible {
  opacity: 1;
}

.snippet-preview-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid var(--snippet);
  border-radius: 4px;
  background: var(--surface);
  color: var(--snippet);
  font-family: inherit;
  font-size: 10px;
  white-space: nowrap;
}

.snippet-preview-btn svg {
  opacity: 0.7;
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

/* Highlight overlay in preview */
.highlight-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  overflow: hidden;
}
#highlight-underlay { z-index: 0; }
#highlight-overlay { z-index: 2; }

.highlight-overlay .hl-el {
  position: absolute;
  box-sizing: border-box;
  pointer-events: none;
  transition: opacity 0.15s ease;
  border-radius: 3px;
}

.highlight-overlay .hl-el.hl-outline {
  box-shadow: 0 0 0 2px var(--hl-color, #f1fa8c);
}

.highlight-overlay .hl-el.hl-underline {
  border-bottom: 2px solid var(--hl-color, #f1fa8c);
  border-radius: 0;
}

.highlight-overlay .hl-el.hl-underline-wavy {
  border-radius: 0;
}
.highlight-overlay .hl-el.hl-underline-wavy::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background-color: var(--hl-color, #f1fa8c);
  -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='4' viewBox='0 0 8 4'%3E%3Cpath d='M0 2Q2 0 4 2Q6 4 8 2' fill='none' stroke='black' stroke-width='1.5'/%3E%3C/svg%3E");
  -webkit-mask-repeat: repeat-x;
  -webkit-mask-size: 6px 3px;
  mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='4' viewBox='0 0 8 4'%3E%3Cpath d='M0 2Q2 0 4 2Q6 4 8 2' fill='none' stroke='black' stroke-width='1.5'/%3E%3C/svg%3E");
  mask-repeat: repeat-x;
  mask-size: 6px 3px;
}

.highlight-overlay .hl-el.hl-background {
  background: color-mix(in srgb, var(--hl-color, #f1fa8c) 20%, transparent);
}

.highlight-overlay .hl-el.hl-spotlight {
  background: color-mix(in srgb, var(--hl-color, #f1fa8c) 10%, transparent);
  box-shadow: 0 0 8px color-mix(in srgb, var(--hl-color, #f1fa8c) 40%, transparent);
}

.highlight-overlay .hl-el.hl-box {
  border: 2px solid var(--hl-color, #f1fa8c);
  background: var(--hl-fill, transparent);
}
.highlight-overlay .hl-el.hl-box.hl-glow {
  box-shadow: 0 0 4px 1px var(--hl-color, #f1fa8c), inset 0 0 2px 1px color-mix(in srgb, var(--hl-color, #f1fa8c) 30%, transparent);
}

.highlight-overlay .hl-el.hl-bracket {
  border-left: 3px solid var(--hl-color, #f1fa8c);
  border-radius: 0;
}

.highlight-overlay .hl-el.hl-badge-before,
.highlight-overlay .hl-el.hl-badge-after {
  border: 1px solid var(--hl-color, #f1fa8c);
}

.highlight-overlay .hl-badge-label {
  position: absolute;
  background: var(--hl-color, #f1fa8c);
  color: #1e1e2e;
  font-size: 9px;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 3px;
  white-space: nowrap;
  line-height: 1.3;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}

.highlight-overlay .hl-el.hl-badge-before .hl-badge-label {
  bottom: 100%;
  left: 0;
  margin-bottom: 2px;
}

.highlight-overlay .hl-el.hl-badge-after .hl-badge-label {
  top: 100%;
  left: 0;
  margin-top: 2px;
}

@keyframes hl-pulse-editor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.highlight-overlay .hl-el.hl-pulse {
  animation: hl-pulse-editor 1.5s ease-in-out infinite;
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
.annotation-bubble.pos-top { top: 10px; left: 50%; transform: translateX(-50%); }
.annotation-bubble.pos-bottom { bottom: 10px; left: 50%; transform: translateX(-50%); }
.annotation-bubble.pos-left { top: 50%; left: 10px; transform: translateY(-50%); }
.annotation-bubble.pos-right { top: 50%; right: 10px; transform: translateY(-50%); }
.annotation-bubble.width-small { max-width: 25%; }
.annotation-bubble.width-medium { max-width: 50%; }
.annotation-bubble.width-large { max-width: 75%; }

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

/* Snippet track items */
.track-item-snippet {
  position: absolute;
  top: 6px;
  bottom: 6px;
  background: rgba(137, 180, 250, 0.15);
  border: 1px solid rgba(137, 180, 250, 0.6);
  border-radius: 3px;
  cursor: pointer;
  overflow: visible;
  min-width: 8px;
}

.track-item-snippet .cmd-text {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 4px;
  right: 4px;
  display: flex;
  align-items: center;
  font-size: 9px;
  color: var(--snippet);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  pointer-events: none;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.track-item-snippet:hover {
  background: rgba(137, 180, 250, 0.25);
}

.track-item-snippet.selected {
  background: rgba(137, 180, 250, 0.35);
  border-color: var(--snippet);
  box-shadow: 0 -4px 8px rgba(137, 180, 250, 0.3), 0 4px 8px rgba(137, 180, 250, 0.3);
}

.track-item-snippet .cmd-handle {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 6px;
  cursor: ew-resize;
  z-index: 5;
}

.track-item-snippet .cmd-handle-left {
  left: -3px;
  border-left: 2px solid var(--snippet);
  border-radius: 2px 0 0 2px;
}

.track-item-snippet .cmd-handle-right {
  right: -3px;
  border-right: 2px solid var(--snippet);
  border-radius: 0 2px 2px 0;
}

.track-item-snippet .cmd-handle:hover,
.track-item-snippet .cmd-handle.active {
  background: rgba(137, 180, 250, 0.4);
}

.track-item-snippet .cmd-handle.selected {
  top: -14px;
  bottom: -14px;
  width: 4px;
  background: none;
  z-index: 20;
}

.track-item-snippet .cmd-handle-left.selected {
  left: -2px;
  border-left: 3px solid var(--snippet);
  box-shadow: -2px 0 8px rgba(137, 180, 250, 0.7);
}

.track-item-snippet .cmd-handle-right.selected {
  right: -2px;
  border-right: 3px solid var(--snippet);
  box-shadow: 2px 0 8px rgba(137, 180, 250, 0.7);
}

#track-snippets {
  cursor: crosshair;
}

/* Highlight track items */
.track-item-highlight {
  position: absolute;
  top: 6px;
  bottom: 6px;
  background: rgba(203, 166, 247, 0.15);
  border: 1px solid rgba(203, 166, 247, 0.6);
  border-radius: 3px;
  cursor: pointer;
  overflow: visible;
  min-width: 8px;
}

.track-item-highlight .hl-text {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 4px;
  right: 4px;
  display: flex;
  align-items: center;
  font-size: 9px;
  color: var(--highlight);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  pointer-events: none;
}

.track-item-highlight:hover {
  background: rgba(203, 166, 247, 0.25);
}

.track-item-highlight.selected {
  background: rgba(203, 166, 247, 0.35);
  border-color: var(--highlight);
  box-shadow: 0 -4px 8px rgba(203, 166, 247, 0.3), 0 4px 8px rgba(203, 166, 247, 0.3);
}

.track-item-highlight .hl-handle {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 6px;
  cursor: ew-resize;
  z-index: 5;
}

.track-item-highlight .hl-handle-left {
  left: -3px;
  border-left: 2px solid var(--highlight);
  border-radius: 2px 0 0 2px;
}

.track-item-highlight .hl-handle-right {
  right: -3px;
  border-right: 2px solid var(--highlight);
  border-radius: 0 2px 2px 0;
}

.track-item-highlight .hl-handle:hover,
.track-item-highlight .hl-handle.active {
  background: rgba(203, 166, 247, 0.4);
}

.track-item-highlight .hl-handle.selected {
  top: -14px;
  bottom: -14px;
  width: 4px;
  background: none;
  z-index: 20;
}

.track-item-highlight .hl-handle-left.selected {
  left: -2px;
  border-left: 3px solid var(--highlight);
  box-shadow: -2px 0 8px rgba(203, 166, 247, 0.7);
}

.track-item-highlight .hl-handle-right.selected {
  right: -2px;
  border-right: 3px solid var(--highlight);
  box-shadow: 2px 0 8px rgba(203, 166, 247, 0.7);
}

#track-highlights {
  cursor: crosshair;
}

/* Per-style highlight colors in timeline */
.track-item-highlight.hl-style-box {
  background: rgba(139, 233, 253, 0.15);
  border-color: rgba(139, 233, 253, 0.6);
}
.track-item-highlight.hl-style-box:hover { background: rgba(139, 233, 253, 0.25); }
.track-item-highlight.hl-style-box.selected {
  background: rgba(139, 233, 253, 0.35);
  border-color: #8be9fd;
  box-shadow: 0 -4px 8px rgba(139, 233, 253, 0.3), 0 4px 8px rgba(139, 233, 253, 0.3);
}
.track-item-highlight.hl-style-box .hl-text { color: #8be9fd; }

.track-item-highlight.hl-style-underline {
  background: rgba(80, 250, 123, 0.15);
  border-color: rgba(80, 250, 123, 0.6);
}
.track-item-highlight.hl-style-underline:hover { background: rgba(80, 250, 123, 0.25); }
.track-item-highlight.hl-style-underline.selected {
  background: rgba(80, 250, 123, 0.35);
  border-color: #50fa7b;
  box-shadow: 0 -4px 8px rgba(80, 250, 123, 0.3), 0 4px 8px rgba(80, 250, 123, 0.3);
}
.track-item-highlight.hl-style-underline .hl-text { color: #50fa7b; }

.track-item-highlight.hl-style-background {
  background: rgba(241, 250, 140, 0.15);
  border-color: rgba(241, 250, 140, 0.6);
}
.track-item-highlight.hl-style-background:hover { background: rgba(241, 250, 140, 0.25); }
.track-item-highlight.hl-style-background.selected {
  background: rgba(241, 250, 140, 0.35);
  border-color: #f1fa8c;
  box-shadow: 0 -4px 8px rgba(241, 250, 140, 0.3), 0 4px 8px rgba(241, 250, 140, 0.3);
}
.track-item-highlight.hl-style-background .hl-text { color: #f1fa8c; }

.track-item-highlight.hl-style-spotlight {
  background: rgba(255, 184, 108, 0.15);
  border-color: rgba(255, 184, 108, 0.6);
}
.track-item-highlight.hl-style-spotlight:hover { background: rgba(255, 184, 108, 0.25); }
.track-item-highlight.hl-style-spotlight.selected {
  background: rgba(255, 184, 108, 0.35);
  border-color: #ffb86c;
  box-shadow: 0 -4px 8px rgba(255, 184, 108, 0.3), 0 4px 8px rgba(255, 184, 108, 0.3);
}
.track-item-highlight.hl-style-spotlight .hl-text { color: #ffb86c; }

.track-item-highlight.hl-style-badge {
  background: rgba(255, 121, 198, 0.15);
  border-color: rgba(255, 121, 198, 0.6);
}
.track-item-highlight.hl-style-badge:hover { background: rgba(255, 121, 198, 0.25); }
.track-item-highlight.hl-style-badge.selected {
  background: rgba(255, 121, 198, 0.35);
  border-color: #ff79c6;
  box-shadow: 0 -4px 8px rgba(255, 121, 198, 0.3), 0 4px 8px rgba(255, 121, 198, 0.3);
}
.track-item-highlight.hl-style-badge .hl-text { color: #ff79c6; }

.track-item-highlight.hl-style-bracket {
  background: rgba(189, 147, 249, 0.15);
  border-color: rgba(189, 147, 249, 0.6);
}
.track-item-highlight.hl-style-bracket:hover { background: rgba(189, 147, 249, 0.25); }
.track-item-highlight.hl-style-bracket.selected {
  background: rgba(189, 147, 249, 0.35);
  border-color: #bd93f9;
  box-shadow: 0 -4px 8px rgba(189, 147, 249, 0.3), 0 4px 8px rgba(189, 147, 249, 0.3);
}
.track-item-highlight.hl-style-bracket .hl-text { color: #bd93f9; }

/* Playhead — single line spanning ruler + 5 tracks */
.playhead {
  position: absolute;
  top: 0;
  left: 0;
  height: 213px; /* ruler 29px + 5 tracks × 36px + 4px overshoot */
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

/* No-color indicator for fill picker */
.fill-picker-wrap {
  position: relative;
  width: 26px; height: 26px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid var(--border);
}
.fill-picker-wrap input[type="color"] {
  width: 100%; height: 100%;
  padding: 0; border: none;
  cursor: pointer; background: none;
}
.fill-picker-wrap.no-color {
  background: #000;
}
.fill-picker-wrap.no-color input[type="color"] {
  opacity: 0;
}
.fill-picker-wrap.no-color::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to top right, transparent calc(50% - 1px), #e55 calc(50% - 1px), #e55 calc(50% + 1px), transparent calc(50% + 1px));
  pointer-events: none;
}

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
  padding-bottom: 1em;
  padding-top: 0.75em;
  padding-left: 2em;
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

.inspector-panel {
  position: absolute;
  top: 12px;
  left: 48px;
  z-index: 20;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 11px;
  min-width: 180px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  transition: opacity 0.15s, transform 0.15s;
}

.inspector-panel.hidden {
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
}

/* Settings panel (gear icon) */
.btn-settings-circle {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text-dim);
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
  flex-shrink: 0;
}
.btn-settings-circle:hover {
  background: var(--border);
  color: var(--text);
}
.btn-settings-circle.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

/* Preview overlay toggle buttons */
.btn-overlay-circle {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text-dim);
  font-size: 11px;
  font-weight: 700;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
  flex-shrink: 0;
}
.btn-overlay-circle:hover {
  background: var(--border);
  color: var(--text);
}
.btn-overlay-circle.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

/* Preview toolbar (left side) */
.preview-toolbar {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 19;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Viewport toolbar (hugs preview window, outside left edge) */
.viewport-toolbar {
  position: absolute;
  top: 6px;
  right: calc(100% + 6px);
  z-index: 5;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transform: scale(var(--btn-counter-scale, 1));
  transform-origin: top right;
}

/* Grid overlay */
.grid-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 2;
  overflow: hidden;
}
.grid-overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

/* Line/column numbers overlay */
.nums-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 3;
  overflow: hidden;
}
.nums-overlay .row-num {
  position: absolute;
  left: 2px;
  font-size: 8px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  color: rgba(137, 180, 250, 0.7);
  line-height: 1;
  pointer-events: none;
}
.nums-overlay .col-num {
  position: absolute;
  top: 2px;
  font-size: 8px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  color: rgba(137, 180, 250, 0.7);
  line-height: 1;
  pointer-events: none;
}

.settings-panel {
  position: absolute;
  top: 12px;
  left: 48px;
  z-index: 21;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px;
  font-size: 11px;
  min-width: 250px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  transition: opacity 0.15s, transform 0.15s;
}
.settings-panel.hidden {
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
}
.settings-panel .settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.settings-panel .settings-title {
  font-weight: 600;
  font-size: 12px;
  color: var(--text);
}
.settings-panel .settings-close {
  background: none;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 16px;
  padding: 0 2px;
}
.settings-panel .settings-close:hover { color: var(--text); }
.settings-panel .setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 8px;
}
.settings-panel .setting-label {
  color: var(--text-dim);
  font-size: 11px;
  white-space: nowrap;
}
.settings-panel input[type="text"],
.settings-panel input[type="number"] {
  width: 100%;
  padding: 5px 8px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', Menlo, monospace;
  outline: none;
  flex: 1;
}
.settings-panel input[type="number"]::-webkit-inner-spin-button,
.settings-panel input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  appearance: none;
}
.settings-panel input[type="number"] {
  -moz-appearance: textfield;
  padding-right: 32px;
}
.settings-panel .number-wrap {
  position: relative;
  flex: 1;
}
.settings-panel input:focus { border-color: var(--accent); }
.settings-panel select {
  width: 100%;
  padding: 5px 8px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 12px;
  outline: none;
  flex: 1;
}
.settings-panel select:focus { border-color: var(--accent); }
.settings-panel .setting-divider {
  border-top: 1px solid var(--border);
  margin: 8px 0;
}
.settings-panel .prompt-presets {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 4px;
  margin-bottom: 10px;
}
.settings-panel .prompt-preset {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 12px;
  padding: 3px 8px;
  cursor: pointer;
  transition: all 0.1s;
}
.settings-panel .prompt-preset:hover {
  background: var(--border);
}
.settings-panel .prompt-preset.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

.inspector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.inspector-header .inspector-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-dim);
  margin: 0;
}

.inspector-close {
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  color: var(--text-dim);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.inspector-close:hover {
  background: var(--border);
  color: var(--text);
}

.btn-info-circle {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text-dim);
  font-family: Georgia, 'Times New Roman', serif;
  font-style: italic;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
  flex-shrink: 0;
}

.btn-info-circle:hover {
  background: var(--border);
  color: var(--text);
}

.btn-info-circle.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

.inspector-panel .stat-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}

.inspector-panel .stat-label {
  color: var(--text-dim);
}

.inspector-panel .stat-value {
  color: var(--text);
  font-weight: 500;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.inspector-panel .stat-divider {
  border-top: 1px solid var(--border);
  margin: 5px 0;
}

.layout-presets {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-left: 8px;
}

.layout-presets button {
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 500;
  border: none;
  border-right: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text-dim);
  cursor: pointer;
  transition: all 0.15s;
}

.layout-presets button:last-child {
  border-right: none;
}

.layout-presets button:hover {
  background: var(--border);
  color: var(--text);
}

.layout-presets button.active {
  background: var(--accent);
  color: #000;
  font-weight: 600;
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
    <button class="btn" id="btn-add-snippet" title="Add snippet at playhead (D)"> + Snippet</button>
    <div class="layout-presets" id="layout-presets" style="margin-left: 8px;">
      <button data-split="75" title="Maximize preview">Preview</button>
      <button data-split="50" class="active" title="Equal split">Balanced</button>
      <button data-split="25" title="Maximize timeline">Timeline</button>
    </div>
    <button class="btn" id="btn-view-yaml" title="View YAML (Y)" style="margin-left: 8px;">YAML</button>
    <button class="btn btn-primary" id="btn-save" title="Save (Cmd+S)">Save</button>
  </div>
</div>

<div class="editor-main">
  <div class="preview-area">
    <div class="preview-toolbar">
      <button class="btn-info-circle" id="btn-inspector" title="Toggle info (I)">i</button>
      <button class="btn-settings-circle" id="btn-settings" title="Settings (G)">&#x2699;</button>
    </div>
    <div class="inspector-panel hidden" id="inspector-panel"></div>
    <div class="settings-panel hidden" id="settings-panel">
      <div class="settings-header">
        <span class="settings-title">Global Settings</span>
        <button class="settings-close" id="settings-close">&times;</button>
      </div>
      <div class="setting-row">
        <span class="setting-label">Default speed</span>
        <select id="setting-speed">
          <option value="0.5">0.5×</option>
          <option value="1" selected>1×</option>
          <option value="1.5">1.5×</option>
          <option value="2">2×</option>
          <option value="3">3×</option>
        </select>
      </div>
      <div class="setting-row">
        <span class="setting-label">Idle limit (s)</span>
        <input type="number" id="setting-idle" min="0" step="0.1" placeholder="none">
      </div>
      <div class="setting-row">
        <span class="setting-label">Chrome</span>
        <select id="setting-chrome">
          <option value="colorful">colorful</option>
          <option value="simple">simple</option>
          <option value="none">none</option>
        </select>
      </div>
      <div class="setting-row">
        <span class="setting-label">Font family</span>
        <input type="text" id="setting-font-family" placeholder="Font1, Font2, monospace">
      </div>
      <div class="setting-divider"></div>
      <div class="setting-row">
        <span class="setting-label">Prompt</span>
        <input type="text" id="setting-prompt" placeholder="e.g. $">
      </div>
      <div class="prompt-presets">
        <button class="prompt-preset" data-prompt="$">$</button>
        <button class="prompt-preset" data-prompt="%">%</button>
        <button class="prompt-preset" data-prompt="#">#</button>
        <button class="prompt-preset" data-prompt="&gt;">&gt;</button>
        <button class="prompt-preset" data-prompt="&#x276F;">&#x276F;</button>
        <button class="prompt-preset" data-prompt="&#x2192;">&#x2192;</button>
      </div>
      <div class="setting-row">
        <span class="setting-label">Pattern</span>
        <input type="text" id="setting-prompt-pattern" placeholder="regex (optional)">
      </div>
    </div>
    <div class="preview-wrapper">
      <div class="viewport-toolbar" id="viewport-toolbar">
        <button class="btn-overlay-circle" id="btn-grid-overlay" title="Toggle grid overlay">&#x23F9;</button>
        <button class="btn-overlay-circle" id="btn-nums-overlay" title="Toggle line/column numbers">#</button>
      </div>
      <div id="chapter-title-overlay" class="chapter-title-overlay"></div>
      <div id="snippet-preview" class="snippet-preview"></div>
      <div class="preview-viewport">
        <div id="highlight-underlay" class="highlight-overlay"></div>
        <pre id="terminal-output"></pre>
        <div id="grid-overlay" class="grid-overlay" style="display:none;"><canvas class="grid-overlay-canvas"></canvas></div>
        <div id="nums-overlay" class="nums-overlay" style="display:none;"></div>
        <div id="highlight-overlay" class="highlight-overlay"></div>
        <div id="annotation-overlay" class="annotation-overlay"></div>
        <div id="cut-indicator" class="cut-indicator">&#x22ef;</div>
      </div>
    </div>
  </div>

  <div class="resize-handle" id="resize-handle"></div>

  <div class="transport">
    <span class="transport-spacer"></span>
    <div class="transport-controls">
      <button class="transport-btn" id="btn-rewind" title="Rewind to start"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5"/></svg></button>
      <button class="transport-btn" id="btn-prev-chapter" title="Previous chapter ([)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="4"/><polygon points="14 20 4 12 14 4"/></svg></button>
      <button class="transport-btn" id="btn-play" title="Play/Pause (Space)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg></button>
      <button class="transport-btn" id="btn-next-chapter" title="Next chapter (])"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="4" x2="6" y2="20"/><polygon points="10 4 20 12 10 20"/></svg></button>
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
    <div class="timeline-track">
      <div class="track-label" style="color: var(--snippet);">Snippets</div>
      <div class="track-content" id="track-snippets"></div>
    </div>
    <div class="timeline-track">
      <div class="track-label" style="color: var(--highlight);">HLGTS.</div>
      <div class="track-content" id="track-highlights"></div>
    </div>
  </div>
</div>

<div class="shortcuts">
  <span><kbd>Space</kbd> Play/Pause</span>
  <span><kbd>C</kbd> Add chapter</span>
  <span><kbd>A</kbd> Add annotation</span>
  <span><kbd>X</kbd> Mark cut</span>
  <span><kbd>D</kbd> Add snippet</span>
  <span><kbd>H</kbd> Add highlight</span>
  <span><kbd>&larr;</kbd><kbd>&rarr;</kbd> Seek</span>
  <span><kbd>[</kbd><kbd>]</kbd> Prev/Next chapter</span>
  <span><kbd>I</kbd> Show Info</span>
  <span><kbd>G</kbd> Settings</span>
  <span><kbd>Y</kbd> View YAML</span>
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
  const trackSnippets = document.getElementById('track-snippets');
  const trackHighlights = document.getElementById('track-highlights');
  const highlightOverlay = document.getElementById('highlight-overlay');
  const highlightUnderlay = document.getElementById('highlight-underlay');
  const propsPanel = document.getElementById('properties-panel');
  const toast = document.getElementById('toast');
  const btnPlay = document.getElementById('btn-play');
  const fileName = document.getElementById('file-name');
  let _hlEls = null;

  // --- Load data ---
  fetch('/api/data')
    .then(r => r.json())
    .then(d => { data = d; init(); })
    .catch(e => showToast('Failed to load: ' + e.message));

  function init() {
    fileName.textContent = data.source_file || data.recording.title || 'Untitled';
    durationDisplay.textContent = formatTimePrecise(data.recording.duration);
    // Ensure snippets array exists
    if (!data.script.snippets) data.script.snippets = [];
    // Ensure highlights array exists
    if (!data.script.highlights) data.script.highlights = [];
    renderStats();

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

  // --- Recording Stats ---
  function renderStats() {
    const panel = document.getElementById('inspector-panel');
    const rec = data.recording;
    const events = rec.events;
    const outputEvents = events.filter(e => e.code === 'o');
    const cols = rec.term.cols;
    const rows = rec.term.rows;
    const script = data.script;

    // Effective duration accounting for cuts
    // Jump cuts remove time entirely; ellipsis cuts replace with a brief indicator (~1s)
    const ELLIPSIS_DUR = 1.0;
    const cutTime = (script.cuts || []).reduce((s, c) => {
      const span = c.end - c.start;
      return s + span - (c.type === 'ellipsis' ? ELLIPSIS_DUR : 0);
    }, 0);
    const effectiveDuration = Math.max(0, rec.duration - cutTime);

    // Estimate rendered size: each keyframe SVG is roughly
    // (cols * rows * 30) bytes for a full-text frame + overhead
    const avgSvgBytes = (cols * rows * 30) + 800;
    const estKeyframes = outputEvents.length + Math.ceil(effectiveDuration / 2.0);
    const estTotalBytes = avgSvgBytes * estKeyframes;

    // Source file size (actual from server, or estimated)
    const sourceBytes = data.source_bytes ||
      events.reduce((sum, e) => sum + JSON.stringify(e).length + 1, 0) + 200;

    function fmtSize(bytes) {
      if (bytes < 1024) return bytes + ' B';
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    const chapters = (script.chapters || []).length;
    const annotations = (script.annotations || []).length;
    const cuts = (script.cuts || []).length;
    const snippets = (script.snippets || []).length;
    const highlights = (script.highlights || []).length;

    panel.innerHTML =
      '<div class="inspector-header"><span class="inspector-title">Info</span><button class="inspector-close" id="inspector-close" title="Close">&times;</button></div>' +
      statRow('Terminal', cols + ' \u00d7 ' + rows) +
      statRow('Duration', rec.duration.toFixed(1) + 's') +
      (cutTime > 0 ? statRow('Effective', effectiveDuration.toFixed(1) + 's') : '') +
      statRow('Events', events.length + ' total') +
      statRow('Output', outputEvents.length + ' events') +
      '<div class="stat-divider"></div>' +
      statRow('Chapters', String(chapters)) +
      statRow('Annotations', String(annotations)) +
      statRow('Cuts', String(cuts)) +
      statRow('Snippets', String(snippets)) +
      statRow('Highlights', String(highlights)) +
      '<div class="stat-divider"></div>' +
      statRow('Source', fmtSize(sourceBytes)) +
      statRow('Keyframes', '~' + estKeyframes) +
      statRow('Rendered (est.)', fmtSize(estTotalBytes));
  }

  function statRow(label, value) {
    return '<div class="stat-row"><span class="stat-label">' + label +
      '</span><span class="stat-value">' + value + '</span></div>';
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

    // Snippets
    trackSnippets.innerHTML = '';

    (data.script.snippets || []).forEach((cmd, i) => {
      const el = document.createElement('div');
      el.className = 'track-item-snippet';
      el.style.left = timeToPct(cmd.time);
      el.style.width = durationToPct(cmd.duration);
      const textSpan = document.createElement('span');
      textSpan.className = 'cmd-text';
      textSpan.textContent = cmd.text;
      el.appendChild(textSpan);
      el.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('cmd-handle')) return;
        e.stopPropagation();
        startBoxDrag('snippet', i, e);
      });

      // Left handle
      const lh = document.createElement('div');
      lh.className = 'cmd-handle cmd-handle-left';
      lh.addEventListener('mousedown', (e) => { e.stopPropagation(); startSnippetHandleDrag(i, 'start', e); });
      el.appendChild(lh);

      // Right handle
      const rh = document.createElement('div');
      rh.className = 'cmd-handle cmd-handle-right';
      rh.addEventListener('mousedown', (e) => { e.stopPropagation(); startSnippetHandleDrag(i, 'end', e); });
      el.appendChild(rh);

      trackSnippets.appendChild(el);
    });

    // Highlights
    trackHighlights.innerHTML = '';

    (data.script.highlights || []).forEach((hl, i) => {
      const el = document.createElement('div');
      const baseStyle = (hl.style || 'box').replace(/-.*/, '');
      el.className = 'track-item-highlight hl-style-' + baseStyle;
      el.style.left = timeToPct(hl.time);
      el.style.width = durationToPct(hl.duration);
      const textSpan = document.createElement('span');
      textSpan.className = 'hl-text';
      textSpan.textContent = hl.style || 'outline';
      el.appendChild(textSpan);
      el.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('hl-handle')) return;
        e.stopPropagation();
        startBoxDrag('highlight', i, e);
      });

      // Left handle
      const lh = document.createElement('div');
      lh.className = 'hl-handle hl-handle-left';
      lh.addEventListener('mousedown', (e) => { e.stopPropagation(); startHighlightHandleDrag(i, 'start', e); });
      el.appendChild(lh);

      // Right handle
      const rh = document.createElement('div');
      rh.className = 'hl-handle hl-handle-right';
      rh.addEventListener('mousedown', (e) => { e.stopPropagation(); startHighlightHandleDrag(i, 'end', e); });
      el.appendChild(rh);

      trackHighlights.appendChild(el);
    });

    renderStats();
    // Invalidate highlight overlay so elements are recreated for new data
    _hlEls = null;
    renderPreviewHighlights();
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

    function charWidth(cp) {
      if (cp <= 0x7E) return 1;
      if ((cp >= 0x0300 && cp <= 0x036F) || (cp >= 0x1AB0 && cp <= 0x1AFF) ||
          (cp >= 0x1DC0 && cp <= 0x1DFF) || (cp >= 0x20D0 && cp <= 0x20FF) ||
          (cp >= 0xFE00 && cp <= 0xFE0F) || (cp >= 0xE0100 && cp <= 0xE01EF) ||
          cp === 0x200B || cp === 0x200C || cp === 0x200D || cp === 0xFEFF) return 0;
      if ((cp >= 0x1100 && cp <= 0x115F) || cp === 0x2329 || cp === 0x232A ||
          (cp >= 0x2E80 && cp <= 0x303E) || (cp >= 0x3040 && cp <= 0x33FF) ||
          (cp >= 0x3400 && cp <= 0x4DBF) || (cp >= 0x4E00 && cp <= 0xA4CF) ||
          (cp >= 0xA960 && cp <= 0xA97F) || (cp >= 0xAC00 && cp <= 0xD7FF) ||
          (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0xFE10 && cp <= 0xFE19) ||
          (cp >= 0xFE30 && cp <= 0xFE6F) || (cp >= 0xFF01 && cp <= 0xFF60) ||
          (cp >= 0xFFE0 && cp <= 0xFFE6) || (cp >= 0x20000 && cp <= 0x3FFFF) ||
          (cp >= 0x1F000 && cp <= 0x1FAFF)) return 2;
      return 1;
    }

    function scrollUp() {
      grid.shift();
      const row = [];
      for (let c2 = 0; c2 < cols; c2++) row.push({...EMPTY});
      grid.push(row);
    }

    function clearCell(r, c2) { grid[r][c2] = {...EMPTY}; }

    function feedChar(ch, w) {
      if (curRow >= rows) { curRow = rows - 1; scrollUp(); }
      if (w === 0) {
        if (curCol > 0) grid[curRow][curCol - 1].char += ch;
        return;
      }
      if (curCol >= cols) return;
      if (w === 2) {
        if (curCol + 1 >= cols) return;
        grid[curRow][curCol] = {char: ch, fg: curFg, bg: curBg, bold: curBold, wide: true};
        grid[curRow][curCol + 1] = {...EMPTY, cont: true};
        curCol += 2;
      } else {
        grid[curRow][curCol] = {char: ch, fg: curFg, bg: curBg, bold: curBold};
        curCol++;
      }
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

    // Track prompt positions via input events
    const promptRows = new Set(); // rows where prompts were detected
    let lastOutputRow = -1;

    for (const ev of data.recording.events) {
      if (ev.time > currentTime) break;
      if (ev.code === 'i') {
        // Input event: current row has a prompt (text before cursor)
        promptRows.add(curRow);
        continue;
      }
      if (ev.code !== 'o') continue;
      lastOutputRow = curRow;
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
        let ch = c, cp = code;
        if (cp >= 0xD800 && cp <= 0xDBFF && i + 1 < s.length) {
          const lo = s[i + 1].charCodeAt(0);
          if (lo >= 0xDC00 && lo <= 0xDFFF) {
            ch = c + s[i + 1]; cp = ((cp - 0xD800) << 10) + (lo - 0xDC00) + 0x10000; i++;
          }
        }
        feedChar(ch, charWidth(cp));
        i++;
      }
    }

    // --- Prompt substitution ---
    const promptSetting = data.script.settings.prompt;
    const promptPattern = data.script.settings.prompt_pattern;
    if (promptSetting) {
      const PROMPT_CHARS = ['$', '%', '#', '>', '\u276f', '\u2192', '\u25b6', '\u27e9', '\u03bb'];
      if (promptRows.size > 0) {
        // Structural detection: substitute prompt char on identified rows
        for (const r of promptRows) {
          if (r >= rows) continue;
          for (let c2 = 0; c2 < cols; c2++) {
            const ch = grid[r][c2].char;
            if (PROMPT_CHARS.includes(ch)) {
              grid[r][c2] = {...grid[r][c2], char: promptSetting};
              break;
            }
            if (ch !== ' ' && !PROMPT_CHARS.includes(ch)) break;
          }
        }
      } else if (promptPattern) {
        // Regex fallback for recordings without input events
        try {
          const re = new RegExp(promptPattern);
          for (let r = 0; r < rows; r++) {
            const rowText = grid[r].map(c2 => c2.char).join('');
            if (re.test(rowText)) {
              for (let c2 = 0; c2 < cols; c2++) {
                const ch = grid[r][c2].char;
                if (PROMPT_CHARS.includes(ch)) {
                  grid[r][c2] = {...grid[r][c2], char: promptSetting};
                  break;
                }
                if (ch !== ' ' && !PROMPT_CHARS.includes(ch)) break;
              }
            }
          }
        } catch(e) { /* invalid regex, skip */ }
      } else {
        // Heuristic fallback: scan all rows for a leading prompt char
        // (used when no input events and no prompt_pattern)
        for (let r = 0; r < rows; r++) {
          for (let c2 = 0; c2 < cols; c2++) {
            const ch = grid[r][c2].char;
            if (ch === ' ') continue; // skip leading whitespace
            if (PROMPT_CHARS.includes(ch)) {
              // Verify it looks like a prompt: char followed by a space
              if (c2 + 1 < cols && grid[r][c2 + 1].char === ' ') {
                grid[r][c2] = {...grid[r][c2], char: promptSetting};
              }
            }
            break; // only check the first non-space char per row
          }
        }
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
        if (cell.cont) continue;
        const ch = cell.char;
        const cp = ch.codePointAt(0) || 0;
        if (cp > 0x7E && !cell.wide) {
          // Narrow non-ASCII: force exact 1ch to prevent glyph overflow
          if (spanOpen) { line += '</span>'; spanOpen = false; }
          let st = 'display:inline-block;width:1ch;';
          if (cell.fg) st += 'color:' + cell.fg + ';';
          if (cell.bg) st += 'background:' + cell.bg + ';';
          if (cell.bold) st += 'font-weight:bold;';
          line += '<span style="' + st + '">' + ch + '</span>';
          prevFg = null; prevBg = null; prevBold = false;
        } else {
          // ASCII or wide chars: render naturally (wide chars already ~2ch in browser)
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
          if (ch === '<') line += '&lt;';
          else if (ch === '>') line += '&gt;';
          else if (ch === '&') line += '&amp;';
          else line += ch;
        }
      }
      if (spanOpen) line += '</span>';
      htmlLines.push(line.trimEnd());
    }
    while (htmlLines.length > 0 && htmlLines[htmlLines.length - 1] === '') htmlLines.pop();
    termOutput.innerHTML = htmlLines.join('\\n');
    renderAnnotations();
    renderChapterTitle();
    renderSnippetPreview();
    renderPreviewHighlights();
  }

  function renderSnippetPreview() {
    const el = document.getElementById('snippet-preview');
    const snips = data.script.snippets || [];
    // Find first active snippet at current time
    let active = null;
    for (const s of snips) {
      if (currentTime >= s.time && currentTime <= s.time + s.duration) { active = s; break; }
    }
    if (active) {
      const label = active.label || active.text || active.match || 'Copy';
      el.innerHTML = '<span class="snippet-preview-btn">' +
        '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>' +
        '<span>' + escHtml(label) + '</span></span>';
      el.classList.add('visible');
    } else {
      el.classList.remove('visible');
    }
  }

  // --- Highlight preview overlay ---

  function measureCellSize() {
    if (highlightOverlay._measure) return;
    const pre = document.getElementById('terminal-output');
    const preStyle = getComputedStyle(pre);
    const probe = document.createElement('span');
    probe.style.cssText = 'position:absolute;top:0;left:0;visibility:hidden;font:inherit;white-space:pre;';
    // Use multiple lines to get accurate line height
    probe.textContent = '0\\n0\\n0\\n0\\n0\\n0\\n0\\n0\\n0\\n0';
    pre.appendChild(probe);
    const rect = probe.getBoundingClientRect();
    highlightOverlay._cellW = rect.width; // width of single '0' char
    highlightOverlay._cellH = rect.height / 10; // average height per line over 10 lines
    pre.removeChild(probe);
    highlightOverlay._measure = true;
    // Redraw grid/nums overlays if visible
    if (_gridVisible && !_gridDrawn) drawGrid();
    if (_numsVisible && !_numsDrawn) drawNums();
  }

  function renderPreviewHighlights() {
    const highlights = data.script.highlights || [];
    measureCellSize();
    if (highlights.length === 0) {
      if (_hlEls) _hlEls.forEach(el => el.style.opacity = '0');
      return;
    }

    // Pre-create elements once (recreate if count changed)
    if (!_hlEls || _hlEls.length !== highlights.length) {
      highlightOverlay.innerHTML = '';
      highlightUnderlay.innerHTML = '';
      _hlEls = [];
      for (const hl of highlights) {
        const el = document.createElement('div');
        el.className = 'hl-el hl-' + hl.style;
        el.style.opacity = '0';
        if (hl.glow) el.classList.add('hl-glow');
        if (hl.color) el.style.setProperty('--hl-color', hl.color);
        if (hl.fill_color) {
          const fo = hl.fill_opacity != null ? hl.fill_opacity : 0.3;
          el.style.setProperty('--hl-fill', hl.fill_color + Math.round(fo * 255).toString(16).padStart(2, '0'));
        }
        if (hl.pulse) el.classList.add('hl-pulse');
        if ((hl.style === 'badge-before' || hl.style === 'badge-after') && (hl.badge_text || hl.badge_icon)) {
          const badge = document.createElement('span');
          badge.className = 'hl-badge-label';
          badge.textContent = (hl.badge_icon || '') + (hl.badge_text || '');
          el.appendChild(badge);
        }
        // Background style goes in underlay (behind text), others in overlay
        if (hl.style === 'background') {
          highlightUnderlay.appendChild(el);
        } else {
          highlightOverlay.appendChild(el);
        }
        _hlEls.push(el);
      }
    }

    const pre = document.getElementById('terminal-output');
    const preStyle = getComputedStyle(pre);
    const paddingLeft = parseFloat(preStyle.paddingLeft) || 12;
    const paddingTop = parseFloat(preStyle.paddingTop) || 12;
    const cellW = highlightOverlay._cellW;
    const cellH = highlightOverlay._cellH;

    for (let k = 0; k < highlights.length; k++) {
      const hl = highlights[k];
      const node = _hlEls[k];

      // Update color in case it was edited
      if (hl.color) node.style.setProperty('--hl-color', hl.color);
      node.classList.toggle('hl-glow', !!hl.glow);
      if (hl.fill_color) {
        const fo = hl.fill_opacity != null ? hl.fill_opacity : 0.3;
        const alphaHex = Math.round(fo * 255).toString(16).padStart(2, '0');
        node.style.setProperty('--hl-fill', hl.fill_color + alphaHex);
      } else {
        node.style.setProperty('--hl-fill', 'transparent');
      }

      if (currentTime >= hl.time && currentTime <= hl.time + hl.duration) {
        // Compute fade
        const elapsed = currentTime - hl.time;
        const fadeInDur = hl.fade_in != null ? hl.fade_in : 0.3;
        const fadeOutDur = hl.fade_out != null ? hl.fade_out : 0.3;
        const fadeIn = fadeInDur > 0 ? Math.min(1, elapsed / fadeInDur) : 1;
        const fadeOut = fadeOutDur > 0 ? Math.min(1, (hl.duration - elapsed) / fadeOutDur) : 1;
        const baseOpacity = hl.opacity != null ? hl.opacity : 1;
        node.style.opacity = String(Math.min(fadeIn, fadeOut) * baseOpacity);

        // Position based on target (match takes priority over region)
        const target = hl.target || {};
        if (target.match) {
          // Match-based: search terminal buffer for pattern
          const matchPos = findMatchInTerminal(target.match);
          if (matchPos) {
            node.style.left = (paddingLeft + matchPos.col * cellW) + 'px';
            node.style.top = (paddingTop + matchPos.row * cellH) + 'px';
            node.style.width = (matchPos.length * cellW) + 'px';
            node.style.height = cellH + 'px';
          } else {
            node.style.opacity = '0';
          }
        } else if (target.region) {
          const r = target.region;
          node.style.left = (paddingLeft + (r.col || 0) * cellW) + 'px';
          node.style.top = (paddingTop + (r.row || 0) * cellH) + 'px';
          node.style.width = ((r.width || 10) * cellW) + 'px';
          node.style.height = ((r.height || 1) * cellH) + 'px';
        } else if (target.lines) {
          const lines = target.lines;
          const minLine = Math.min(...lines);
          const maxLine = Math.max(...lines);
          node.style.left = paddingLeft + 'px';
          node.style.top = (paddingTop + minLine * cellH) + 'px';
          node.style.width = 'calc(100% - ' + (paddingLeft * 2) + 'px)';
          node.style.height = ((maxLine - minLine + 1) * cellH) + 'px';
        } else {
          // No target — hide
          node.style.opacity = '0';
        }
      } else {
        if (node.style.opacity !== '0') node.style.opacity = '0';
      }
    }
  }

  // Search the current terminal text buffer for a regex match
  function findMatchInTerminal(pattern) {
    try {
      const pre = document.getElementById('terminal-output');
      // Get plain text lines from the rendered terminal
      const text = pre.textContent || '';
      const lines = text.split('\\n');
      const re = new RegExp(pattern);
      for (let row = 0; row < lines.length; row++) {
        const m = re.exec(lines[row]);
        if (m) {
          return { row: row, col: m.index, length: m[0].length };
        }
      }
    } catch (e) {
      // Invalid regex — ignore
    }
    return null;
  }

  // Invalidate measure cache on resize
  function invalidateHighlightMeasure() {
    if (highlightOverlay) highlightOverlay._measure = false;
    _gridDrawn = false;
    _numsDrawn = false;
  }

  // --- Grid overlay ---
  let _gridVisible = false;
  let _gridDrawn = false;

  function toggleGridOverlay() {
    _gridVisible = !_gridVisible;
    const btn = document.getElementById('btn-grid-overlay');
    const el = document.getElementById('grid-overlay');
    btn.classList.toggle('active', _gridVisible);
    el.style.display = _gridVisible ? '' : 'none';
    if (_gridVisible && !_gridDrawn) drawGrid();
  }

  function drawGrid() {
    if (!highlightOverlay._measure) return;
    const cellW = highlightOverlay._cellW;
    const cellH = highlightOverlay._cellH;
    const pre = document.getElementById('terminal-output');
    const preStyle = getComputedStyle(pre);
    const padL = parseFloat(preStyle.paddingLeft) || 12;
    const padT = parseFloat(preStyle.paddingTop) || 12;
    const cols = data.recording.term.cols;
    const rows = data.recording.term.rows;

    const canvas = document.querySelector('#grid-overlay .grid-overlay-canvas');
    const w = pre.offsetWidth;
    const h = pre.offsetHeight;
    canvas.width = w * 2;
    canvas.height = h * 2;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(2, 2);
    ctx.strokeStyle = 'rgba(137, 180, 250, 0.15)';
    ctx.lineWidth = 0.5;

    // Vertical lines (columns)
    for (let c = 0; c <= cols; c++) {
      const x = padL + c * cellW;
      ctx.beginPath();
      ctx.moveTo(x, padT);
      ctx.lineTo(x, padT + rows * cellH);
      ctx.stroke();
    }
    // Horizontal lines (rows)
    for (let r = 0; r <= rows; r++) {
      const y = padT + r * cellH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + cols * cellW, y);
      ctx.stroke();
    }
    _gridDrawn = true;
  }

  // --- Line/column numbers overlay ---
  let _numsVisible = false;
  let _numsDrawn = false;

  function toggleNumsOverlay() {
    _numsVisible = !_numsVisible;
    const btn = document.getElementById('btn-nums-overlay');
    const el = document.getElementById('nums-overlay');
    btn.classList.toggle('active', _numsVisible);
    el.style.display = _numsVisible ? '' : 'none';
    if (_numsVisible && !_numsDrawn) drawNums();
  }

  function drawNums() {
    if (!highlightOverlay._measure) return;
    const cellW = highlightOverlay._cellW;
    const cellH = highlightOverlay._cellH;
    const pre = document.getElementById('terminal-output');
    const preStyle = getComputedStyle(pre);
    const padL = parseFloat(preStyle.paddingLeft) || 12;
    const padT = parseFloat(preStyle.paddingTop) || 12;
    const cols = data.recording.term.cols;
    const rows = data.recording.term.rows;

    const container = document.getElementById('nums-overlay');
    container.innerHTML = '';

    // Row numbers (1-based, shown at start of each row)
    for (let r = 0; r < rows; r++) {
      const el = document.createElement('span');
      el.className = 'row-num';
      el.style.top = (padT + r * cellH + cellH * 0.3) + 'px';
      el.style.left = '2px';
      el.textContent = String(r + 1);
      container.appendChild(el);
    }
    // Column numbers (1-based, shown every 5 cols at top)
    for (let c = 0; c < cols; c += 5) {
      const el = document.createElement('span');
      el.className = 'col-num';
      el.style.left = (padL + c * cellW) + 'px';
      el.style.top = '2px';
      el.textContent = String(c + 1);
      container.appendChild(el);
    }
    _numsDrawn = true;
  }

  document.getElementById('btn-grid-overlay').addEventListener('click', toggleGridOverlay);
  document.getElementById('btn-nums-overlay').addEventListener('click', toggleNumsOverlay);

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
        + ' pos-' + (ann.position || 'top-right')
        + ' width-' + (ann.width || 'medium');
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
    const availW = area.clientWidth - 32 - 36;  // padding + toolbar overflow
    const availH = area.clientHeight - 32;
    const natW = wrapper.offsetWidth;
    const natH = wrapper.offsetHeight;
    if (natW <= 0 || natH <= 0) return;
    const scale = Math.min(availW / natW, availH / natH);
    wrapper.style.setProperty('--viewport-scale', scale.toFixed(4));
    // Counter-scale viewport toolbar buttons so they stay fixed size
    const vt = document.getElementById('viewport-toolbar');
    if (vt) vt.style.setProperty('--btn-counter-scale', (1 / scale).toFixed(4));
  }

  window.addEventListener('resize', () => {
    invalidatePlayheadCache();
    invalidateHighlightMeasure();
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
    if (!ann.width) ann.width = 'medium';
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
          <option value="top" ${ann.position==='top'?'selected':''}>Top</option>
          <option value="bottom" ${ann.position==='bottom'?'selected':''}>Bottom</option>
          <option value="left" ${ann.position==='left'?'selected':''}>Left</option>
          <option value="right" ${ann.position==='right'?'selected':''}>Right</option>
          <option value="top-left" ${ann.position==='top-left'?'selected':''}>Top Left</option>
          <option value="top-right" ${ann.position==='top-right'?'selected':''}>Top Right</option>
          <option value="bottom-left" ${ann.position==='bottom-left'?'selected':''}>Bottom Left</option>
          <option value="bottom-right" ${ann.position==='bottom-right'?'selected':''}>Bottom Right</option>
        </select>
      </div>
      <div class="prop-field">
        <div class="prop-label">Width</div>
        <select class="prop-select" id="prop-width">
          <option value="small" ${ann.width==='small'?'selected':''}>Small</option>
          <option value="medium" ${ann.width==='medium'?'selected':''}>Medium</option>
          <option value="large" ${ann.width==='large'?'selected':''}>Large</option>
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

  function selectSnippet(idx) {
    selectedItem = { type: 'snippet', index: idx };
    clearAllHighlights();
    const cmdEls = trackSnippets.querySelectorAll('.track-item-snippet');
    if (cmdEls[idx]) cmdEls[idx].classList.add('selected');
    const cmd = (data.script.snippets || [])[idx];
    propsPanel.innerHTML = `
      <div class="prop-title">Snippet</div>
      <div class="prop-field">
        <div class="prop-label">Time (s)</div>
        <input class="prop-input" type="number" step="0.01" value="${cmd.time.toFixed(2)}" id="prop-time">
      </div>
      <div class="prop-field">
        <div class="prop-label">Duration (s)</div>
        <input class="prop-input" type="number" step="0.1" value="${cmd.duration.toFixed(2)}" id="prop-duration">
      </div>
      <div class="prop-field">
        <div class="prop-label">Text</div>
        <input class="prop-input" type="text" value="${escAttr(cmd.text)}" id="prop-text" placeholder="Literal text to copy">
      </div>
      <div class="prop-field">
        <div class="prop-label">Match (regex)</div>
        <input class="prop-input" type="text" value="${escAttr(cmd.match || '')}" id="prop-match" placeholder="Regex pattern against terminal buffer">
      </div>
      <div class="prop-field">
        <div class="prop-label">Label (optional)</div>
        <input class="prop-input" type="text" value="${escAttr(cmd.label || '')}" id="prop-label">
      </div>
      <div class="prop-actions">
        <button class="btn" onclick="undoSelected()">Undo</button>
        <button class="btn" style="color:var(--cut)" onclick="deleteSelected()">Delete</button>
      </div>
    `;
    propsPanel.classList.add('open');
    attachLiveListeners();
  }

  function selectHighlight(idx) {
    selectedItem = { type: 'highlight', index: idx };
    clearAllHighlights();
    const hlEls = trackHighlights.querySelectorAll('.track-item-highlight');
    if (hlEls[idx]) hlEls[idx].classList.add('selected');
    const hl = (data.script.highlights || [])[idx];
    const target = hl.target || {};
    const regionRow = target.region ? (target.region.row || 0) + 1 : '';
    const regionCol = target.region ? (target.region.col || 0) + 1 : '';
    const regionW = target.region ? (target.region.width || 10) : '';
    const regionH = target.region ? (target.region.height || 1) : '';

    // Normalize merged styles for UI
    const isUnderline = hl.style === 'underline' || hl.style === 'underline-wavy';
    const isBadge = hl.style === 'badge-before' || hl.style === 'badge-after';
    const isBox = hl.style === 'box' || hl.style === 'outline';
    const uiStyle = isUnderline ? 'underline' : isBadge ? 'badge' : isBox ? 'box' : hl.style;
    const hasGlow = !!hl.glow;
    const underlineType = hl.style === 'underline-wavy' ? 'wavy' : 'solid';
    const badgePosition = hl.style === 'badge-after' ? 'after' : 'before';

    // Build style-specific options
    let styleOptions = '';

    if (isUnderline) {
      styleOptions += `
      <div class="prop-field">
        <div class="prop-label">Type</div>
        <select class="prop-select" id="prop-hl-subtype">
          <option value="solid" ${underlineType==='solid'?'selected':''}>Solid</option>
          <option value="wavy" ${underlineType==='wavy'?'selected':''}>Wavy</option>
        </select>
      </div>`;
    }

    if (isBadge) {
      styleOptions += `
      <div class="prop-field">
        <div class="prop-label">Position</div>
        <select class="prop-select" id="prop-hl-badge-pos">
          <option value="before" ${badgePosition==='before'?'selected':''}>Before (above)</option>
          <option value="after" ${badgePosition==='after'?'selected':''}>After (below)</option>
        </select>
      </div>
      <div class="prop-field">
        <div class="prop-label">Badge text</div>
        <input class="prop-input" type="text" value="${escAttr(hl.badge_text || '')}" id="prop-hl-badge">
      </div>`;
    }

    const termCols = data.recording.term.cols;
    const termRows = data.recording.term.rows;

    styleOptions += `
      <div class="prop-field">
        <div style="display:flex; gap:4px; align-items:flex-end;">
          <div style="display:flex;flex-direction:column;gap:2px;flex:1;">
            <label style="font-size:9px;color:var(--text-dim);">${isBox ? 'Border Color' : 'Color'}</label>
            <div style="display:flex; gap:4px; align-items:center;">
              <input type="color" value="${escAttr(hl.color || '#f1fa8c')}" id="prop-hl-color-picker" style="width:26px;height:26px;padding:0;border:1px solid var(--border);border-radius:4px;cursor:pointer;background:none;flex-shrink:0;">
              <input class="prop-input" type="text" value="${escAttr((hl.color || '#f1fa8c').toUpperCase())}" id="prop-hl-color" placeholder="#hex" style="flex:1;font-family:'SF Mono',Menlo,Consolas,monospace;text-transform:uppercase;">
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:2px;">
            <label style="font-size:9px;color:var(--text-dim);">Opacity</label>
            <input class="prop-input" type="number" step="0.05" min="0" max="1" value="${hl.opacity != null ? hl.opacity : 1}" id="prop-hl-opacity" style="width:76px;">
          </div>
        </div>
      </div>`;

    if (isBox) {
      styleOptions += `
      <div class="prop-field">
        <div style="display:flex; gap:4px; align-items:flex-end;">
          <div style="display:flex;flex-direction:column;gap:2px;flex:1;">
            <label style="font-size:9px;color:var(--text-dim);">Fill Color</label>
            <div style="display:flex; gap:4px; align-items:center;">
              <div class="fill-picker-wrap${hl.fill_color ? '' : ' no-color'}">
                <input type="color" value="${escAttr(hl.fill_color || '#000000')}" id="prop-hl-fill-picker">
              </div>
              <input class="prop-input" type="text" value="${escAttr((hl.fill_color || '').toUpperCase())}" id="prop-hl-fill" placeholder="none" style="flex:1;font-family:'SF Mono',Menlo,Consolas,monospace;text-transform:uppercase;">
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:2px;">
            <label style="font-size:9px;color:var(--text-dim);">Fill Opacity</label>
            <input class="prop-input" type="number" step="0.05" min="0" max="1" value="${hl.fill_opacity != null ? hl.fill_opacity : 0.3}" id="prop-hl-fill-opacity" style="width:76px;">
          </div>
        </div>
      </div>
      <div class="prop-field">
        <div class="prop-label">Glow</div>
        <select class="prop-select" id="prop-hl-glow">
          <option value="false" ${!hasGlow?'selected':''}>Off</option>
          <option value="true" ${hasGlow?'selected':''}>On</option>
        </select>
      </div>`;
    }
    styleOptions += `
      <div class="prop-field">
        <div style="display:flex; gap:4px;">
          <div style="display:flex;flex-direction:column;gap:2px;flex:1;">
            <label style="font-size:9px;color:var(--text-dim);">Row</label>
            <input class="prop-input" type="number" step="1" min="1" max="${termRows}" value="${regionRow}" id="prop-hl-row" placeholder="row">
          </div>
          <div style="display:flex;flex-direction:column;gap:2px;flex:1;">
            <label style="font-size:9px;color:var(--text-dim);">Column</label>
            <input class="prop-input" type="number" step="1" min="1" max="${termCols}" value="${regionCol}" id="prop-hl-col" placeholder="col">
          </div>
        </div>
      </div>
      <div class="prop-field">
        <div style="display:flex; gap:4px;">
          <div style="display:flex;flex-direction:column;gap:2px;flex:1;">
            <label style="font-size:9px;color:var(--text-dim);">Width</label>
            <input class="prop-input" type="number" step="1" min="1" max="${termCols}" value="${regionW}" id="prop-hl-width" placeholder="w">
          </div>
          <div style="display:flex;flex-direction:column;gap:2px;flex:1;">
            <label style="font-size:9px;color:var(--text-dim);">Height</label>
            <input class="prop-input" type="number" step="1" min="1" max="${termRows}" value="${regionH}" id="prop-hl-height" placeholder="h">
          </div>
        </div>
      </div>
      <div class="prop-field">
        <div class="prop-label">Matching Regex</div>
        <input class="prop-input" type="text" value="${escAttr(target.match || '')}" id="prop-hl-match" placeholder="Pattern target">
      </div>
      <div class="prop-field">
        <div class="prop-label">Pulse</div>
        <select class="prop-select" id="prop-hl-pulse">
          <option value="false" ${!hl.pulse?'selected':''}>No</option>
          <option value="true" ${hl.pulse?'selected':''}>Yes</option>
        </select>
      </div>`;

    propsPanel.innerHTML = `
      <div class="prop-title">Highlight</div>
      <div class="prop-field">
        <div class="prop-label">Time (s)</div>
        <input class="prop-input" type="number" step="0.01" value="${hl.time.toFixed(2)}" id="prop-time">
      </div>
      <div class="prop-field">
        <div class="prop-label">Duration (s)</div>
        <input class="prop-input" type="number" step="0.1" value="${hl.duration.toFixed(2)}" id="prop-duration">
      </div>
      <div class="prop-field">
        <div class="prop-label">Style</div>
        <select class="prop-select" id="prop-hl-style">
          <option value="box" ${uiStyle==='box'?'selected':''}>Box</option>
          <option value="underline" ${uiStyle==='underline'?'selected':''}>Underline</option>
          <option value="background" ${uiStyle==='background'?'selected':''}>Background</option>
          <option value="spotlight" ${uiStyle==='spotlight'?'selected':''}>Spotlight</option>
          <option value="badge" ${uiStyle==='badge'?'selected':''}>Badge</option>
          <option value="bracket" ${uiStyle==='bracket'?'selected':''}>Bracket</option>
        </select>
      </div>
      <hr style="border:none; border-top:1px solid var(--border); margin:12px 0;">
      ${styleOptions}
      <div class="prop-actions">
        <button class="btn" onclick="undoSelected()">Undo</button>
        <button class="btn" style="color:var(--cut)" onclick="deleteSelected()">Delete</button>
      </div>
    `;
    propsPanel.classList.add('open');
    attachLiveListeners();

    // Re-draw inspector when style changes
    document.getElementById('prop-hl-style').addEventListener('change', () => {
      liveApplyHighlightStyle(idx);
      selectHighlight(idx);
    });
  }

  // Apply just the style change before re-rendering inspector
  function liveApplyHighlightStyle(idx) {
    const hl = data.script.highlights[idx];
    const uiVal = document.getElementById('prop-hl-style').value;
    // Map merged UI values back to internal style
    if (uiVal === 'underline') {
      hl.style = 'underline';
    } else if (uiVal === 'badge') {
      hl.style = 'badge-before';
    } else {
      hl.style = uiVal;
    }
    // Also persist time/duration from current inputs
    hl.time = parseFloat(document.getElementById('prop-time').value) || 0;
    hl.duration = parseFloat(document.getElementById('prop-duration').value) || 1;
    markDirty();
    renderTracks();
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
      else if (type === 'snippet') undoSnapshot = { ...(data.script.snippets || [])[index] };
      else if (type === 'highlight') undoSnapshot = JSON.parse(JSON.stringify((data.script.highlights || [])[index]));
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
    // Sync color picker <-> hex text field
    const colorPicker = propsPanel.querySelector('#prop-hl-color-picker');
    const colorHex = propsPanel.querySelector('#prop-hl-color');
    if (colorPicker && colorHex) {
      colorPicker.addEventListener('input', () => {
        colorHex.value = colorPicker.value.toUpperCase();
        liveApply();
      });
      colorHex.addEventListener('input', () => {
        colorHex.value = colorHex.value.toUpperCase();
        if (/^#[0-9A-F]{6}$/.test(colorHex.value)) {
          colorPicker.value = colorHex.value;
        }
      });
    }
    // Sync fill color picker <-> hex field
    const fillPicker = propsPanel.querySelector('#prop-hl-fill-picker');
    const fillHex = propsPanel.querySelector('#prop-hl-fill');
    const fillWrap = propsPanel.querySelector('.fill-picker-wrap');
    if (fillPicker && fillHex) {
      fillPicker.addEventListener('input', () => {
        fillHex.value = fillPicker.value.toUpperCase();
        if (fillWrap) fillWrap.classList.remove('no-color');
        liveApply();
      });
      fillHex.addEventListener('input', () => {
        fillHex.value = fillHex.value.toUpperCase();
        if (/^#[0-9A-F]{6}$/.test(fillHex.value)) {
          fillPicker.value = fillHex.value;
          if (fillWrap) fillWrap.classList.remove('no-color');
        } else if (fillHex.value.trim() === '') {
          if (fillWrap) fillWrap.classList.add('no-color');
        }
      });
    }
    // Disable region fields when match regex has a value
    const matchInput = propsPanel.querySelector('#prop-hl-match');
    const regionFields = ['#prop-hl-row', '#prop-hl-col', '#prop-hl-width', '#prop-hl-height'];
    function syncRegionDisabled() {
      const hasMatch = matchInput && matchInput.value.trim() !== '';
      regionFields.forEach(sel => {
        const el = propsPanel.querySelector(sel);
        if (el) {
          el.disabled = hasMatch;
          el.style.opacity = hasMatch ? '0.4' : '1';
        }
      });
    }
    if (matchInput) {
      matchInput.addEventListener('input', syncRegionDisabled);
      syncRegionDisabled();
    }
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
      data.script.annotations[index].width = document.getElementById('prop-width').value;
      data.script.annotations[index].style = document.getElementById('prop-style').value;
    } else if (type === 'cut') {
      data.script.cuts[index].start = parseFloat(document.getElementById('prop-start').value) || 0;
      data.script.cuts[index].end = parseFloat(document.getElementById('prop-end').value) || 0;
      data.script.cuts[index].type = document.getElementById('prop-type').value;
    } else if (type === 'snippet') {
      data.script.snippets[index].time = parseFloat(document.getElementById('prop-time').value) || 0;
      data.script.snippets[index].duration = parseFloat(document.getElementById('prop-duration').value) || 1;
      data.script.snippets[index].text = document.getElementById('prop-text').value;
      data.script.snippets[index].match = document.getElementById('prop-match').value;
      data.script.snippets[index].label = document.getElementById('prop-label').value;
    } else if (type === 'highlight') {
      const hl = data.script.highlights[index];
      hl.time = parseFloat(document.getElementById('prop-time').value) || 0;
      hl.duration = parseFloat(document.getElementById('prop-duration').value) || 1;
      // Resolve merged style values
      const uiStyle = document.getElementById('prop-hl-style').value;
      if (uiStyle === 'underline') {
        const subEl = document.getElementById('prop-hl-subtype');
        hl.style = subEl && subEl.value === 'wavy' ? 'underline-wavy' : 'underline';
      } else if (uiStyle === 'badge') {
        const posEl = document.getElementById('prop-hl-badge-pos');
        hl.style = posEl && posEl.value === 'after' ? 'badge-after' : 'badge-before';
      } else {
        hl.style = uiStyle;
      }
      hl.color = document.getElementById('prop-hl-color').value || '#f1fa8c';
      const opVal = parseFloat(document.getElementById('prop-hl-opacity').value);
      hl.opacity = isNaN(opVal) ? 1 : Math.max(0, Math.min(1, opVal));
      const fillEl = document.getElementById('prop-hl-fill');
      if (fillEl) {
        hl.fill_color = fillEl.value || '';
        const fillOpVal = parseFloat(document.getElementById('prop-hl-fill-opacity').value);
        hl.fill_opacity = isNaN(fillOpVal) ? 0.3 : Math.max(0, Math.min(1, fillOpVal));
      }
      const badgeEl = document.getElementById('prop-hl-badge');
      hl.badge_text = badgeEl ? badgeEl.value : (hl.badge_text || '');
      const glowEl = document.getElementById('prop-hl-glow');
      hl.glow = glowEl ? glowEl.value === 'true' : !!hl.glow;
      hl.pulse = document.getElementById('prop-hl-pulse').value === 'true';
      // Update match target
      const matchVal = document.getElementById('prop-hl-match').value;
      // Update region from fields (sanitize to integers, clamp to terminal bounds)
      const maxCols = data.recording.term.cols;
      const maxRows = data.recording.term.rows;
      const rowEl = document.getElementById('prop-hl-row');
      const colEl = document.getElementById('prop-hl-col');
      const wEl = document.getElementById('prop-hl-width');
      const hEl = document.getElementById('prop-hl-height');
      const rowStr = rowEl.value;
      const colStr = colEl.value;
      const wStr = wEl.value;
      const hStr = hEl.value;
      let row = Math.round(parseFloat(rowStr));
      let col = Math.round(parseFloat(colStr));
      let w = Math.round(parseFloat(wStr));
      let h = Math.round(parseFloat(hStr));
      const hasRegion = rowStr !== '' || colStr !== '' || wStr !== '' || hStr !== '';

      // Clamp values (1-based UI)
      if (!isNaN(row)) { row = Math.max(1, Math.min(row, maxRows)); rowEl.value = row; }
      if (!isNaN(col)) { col = Math.max(1, Math.min(col, maxCols)); colEl.value = col; }
      if (!isNaN(w)) { w = Math.max(1, Math.min(w, maxCols)); wEl.value = w; }
      if (!isNaN(h)) { h = Math.max(1, Math.min(h, maxRows)); hEl.value = h; }

      if (!hl.target) hl.target = {};
      // Match takes priority — if set, remove region so it doesn't override
      if (matchVal) {
        hl.target.match = matchVal;
        delete hl.target.region;
      } else {
        delete hl.target.match;
        // Only set region if user provided values (convert 1-based UI to 0-based internal)
        if (hasRegion && !isNaN(row) && !isNaN(col) && !isNaN(w) && !isNaN(h)) {
          hl.target.region = { row: row - 1, col: col - 1, width: w, height: h };
        }
      }
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
    else if (type === 'snippet') data.script.snippets[index] = { ...undoSnapshot };
    else if (type === 'highlight') data.script.highlights[index] = JSON.parse(JSON.stringify(undoSnapshot));
    renderTracks();
    updatePlayhead();
    // Re-open panel with restored values
    if (type === 'chapter') selectChapter(index);
    else if (type === 'annotation') selectAnnotation(index);
    else if (type === 'cut') selectCut(index);
    else if (type === 'snippet') selectSnippet(index);
    else if (type === 'highlight') selectHighlight(index);
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
    else if (type === 'snippet') data.script.snippets.splice(index, 1);
    else if (type === 'highlight') data.script.highlights.splice(index, 1);

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

  // --- Double-click on chapters track to create ---
  trackChapters.addEventListener('dblclick', (e) => {
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
    let dragStarted = false;

    function onMove(ev) {
      if (!dragStarted) {
        if (Math.abs(ev.clientX - startX) < 4) return;
        // Threshold exceeded — create the item and start drag
        dragStarted = true;
        const tempIdx = data.script.cuts.length;
        data.script.cuts.push({ start: startTime, end: startTime, type: 'jump' });
        cutDragState = { index: tempIdx, startTime: startTime };
        renderTracks();
        updatePlayhead();
      }
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
      if (!dragStarted) return; // No drag — let dblclick handle it
      const cut = data.script.cuts[cutDragState.index];
      if (cut.end - cut.start < 0.15) {
        data.script.cuts.splice(cutDragState.index, 1);
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

  // Double-click on cuts track to create a 2s cut
  trackCuts.addEventListener('dblclick', (e) => {
    if (e.target !== trackCuts) return;
    e.preventDefault();
    const rect = trackCuts.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const clickTime = roundTime(ratio * data.recording.duration);
    const start = clickTime;
    const end = roundTime(Math.min(clickTime + 2, data.recording.duration));
    if (end > start) {
      data.script.cuts.push({ start: start, end: end, type: 'jump' });
      renderTracks();
      updatePlayhead();
      markDirty();
      selectCut(data.script.cuts.length - 1);
      showToast('Cut added (2s) — drag edges to adjust');
    }
  });

  // --- Snippet add/drag/double-click ---
  function addSnippet() {
    addSnippetAt(currentTime);
  }

  // Check if a time range overlaps any existing snippet (excluding skipIdx)
  function snippetOverlapsAny(start, end, skipIdx) {
    const snips = data.script.snippets || [];
    for (let i = 0; i < snips.length; i++) {
      if (i === skipIdx) continue;
      const s = snips[i];
      if (start < s.time + s.duration && end > s.time) return true;
    }
    return false;
  }

  function addSnippetAt(time) {
    if (!data.script.snippets) data.script.snippets = [];
    const start = roundTime(time);
    const dur = roundTime(Math.min(5, data.recording.duration - start));
    if (dur <= 0) return;
    // Prevent overlapping snippets
    if (snippetOverlapsAny(start, start + dur, -1)) {
      showToast('Cannot add snippet — overlaps an existing one');
      return;
    }
    data.script.snippets.push({ time: start, duration: dur, text: '# enter text here', match: '', label: '' });
    renderTracks();
    updatePlayhead();
    markDirty();
    const idx = data.script.snippets.length - 1;
    selectSnippet(idx);
    showToast('Snippet added — edit the text in properties');
  }

  function addHighlight() {
    if (!data.script.highlights) data.script.highlights = [];
    const start = roundTime(currentTime);
    const dur = roundTime(Math.min(3, data.recording.duration - start));
    if (dur <= 0) return;
    data.script.highlights.push({ time: start, duration: dur, target: { region: { row: 0, col: 0, width: 10, height: 1 } }, style: 'box', color: '#f1fa8c', opacity: 1, badge_text: '', badge_icon: '', fade_in: 0.3, fade_out: 0.3, pulse: false });
    renderTracks();
    updatePlayhead();
    markDirty();
    const idx = data.script.highlights.length - 1;
    selectHighlight(idx);
    showToast('Highlight added — configure target and style in properties');
  }

  // Snippet handle drag (resize edges)
  function startSnippetHandleDrag(cmdIdx, edge, e) {
    e.preventDefault();
    const rect = trackSnippets.getBoundingClientRect();
    const duration = data.recording.duration;
    selectSnippet(cmdIdx);
    selectedItem = { type: 'snippet', index: cmdIdx, edge: edge };
    // Highlight the edge handle
    const cmdEls = trackSnippets.querySelectorAll('.track-item-snippet');
    if (cmdEls[cmdIdx]) {
      const handle = cmdEls[cmdIdx].querySelector('.cmd-handle-' + (edge === 'start' ? 'left' : 'right'));
      if (handle) handle.classList.add('selected');
    }
    // Seek playhead to the edge position
    const cmd = data.script.snippets[cmdIdx];
    seek(edge === 'start' ? cmd.time : cmd.time + cmd.duration);

    function onMove(ev) {
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * duration, duration)));
      const cmd = data.script.snippets[cmdIdx];
      if (edge === 'start') {
        const newStart = Math.min(t, cmd.time + cmd.duration - 0.1);
        const newDur = cmd.duration + (cmd.time - newStart);
        if (!snippetOverlapsAny(newStart, newStart + newDur, cmdIdx)) {
          cmd.time = newStart;
          cmd.duration = newDur;
        }
      } else {
        const newEnd = Math.max(t, cmd.time + 0.1);
        const newDur = roundTime(newEnd - cmd.time);
        if (!snippetOverlapsAny(cmd.time, cmd.time + newDur, cmdIdx)) {
          cmd.duration = newDur;
        }
      }
      renderTracks();
      updatePlayhead();
      const cmEls = trackSnippets.querySelectorAll('.track-item-snippet');
      if (cmEls[cmdIdx]) {
        cmEls[cmdIdx].classList.add('selected');
        const h = cmEls[cmdIdx].querySelector('.cmd-handle-' + (edge === 'start' ? 'left' : 'right'));
        if (h) h.classList.add('selected');
      }
      // Update inspector live
      const timeInput = document.getElementById('prop-time');
      const durInput = document.getElementById('prop-duration');
      if (timeInput) timeInput.value = cmd.time.toFixed(2);
      if (durInput) durInput.value = cmd.duration.toFixed(2);
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      markDirty();
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // Snippet drag-to-create on track
  trackSnippets.addEventListener('mousedown', (e) => {
    if (e.target !== trackSnippets) return;
    e.preventDefault();
    if (!data.script.snippets) data.script.snippets = [];
    const rect = trackSnippets.getBoundingClientRect();
    const startX = e.clientX;
    const startRatio = (startX - rect.left) / rect.width;
    const startTime = roundTime(startRatio * data.recording.duration);
    let dragStarted = false;
    let cmdDragIdx = null;

    function onMove(ev) {
      if (!dragStarted) {
        if (Math.abs(ev.clientX - startX) < 4) return;
        dragStarted = true;
        cmdDragIdx = data.script.snippets.length;
        data.script.snippets.push({ time: startTime, duration: 0, text: '# enter text here', match: '', label: '' });
        renderTracks();
        updatePlayhead();
      }
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * data.recording.duration, data.recording.duration)));
      const cmd = data.script.snippets[cmdDragIdx];
      let newStart, newDur;
      if (t < startTime) {
        newStart = t;
        newDur = roundTime(startTime - t);
      } else {
        newStart = startTime;
        newDur = roundTime(t - startTime);
      }
      if (!snippetOverlapsAny(newStart, newStart + newDur, cmdDragIdx)) {
        cmd.time = newStart;
        cmd.duration = newDur;
      }
      renderTracks();
      updatePlayhead();
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (!dragStarted) return;
      const cmd = data.script.snippets[cmdDragIdx];
      if (cmd.duration < 0.15) {
        data.script.snippets.splice(cmdDragIdx, 1);
      } else {
        selectSnippet(cmdDragIdx);
        markDirty();
        showToast('Snippet: ' + formatTimePrecise(cmd.time) + ' → ' + formatTimePrecise(cmd.time + cmd.duration));
      }
      renderTracks();
      updatePlayhead();
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  // Double-click on snippets track to create a 5s command
  trackSnippets.addEventListener('dblclick', (e) => {
    if (e.target !== trackSnippets) return;
    e.preventDefault();
    if (!data.script.snippets) data.script.snippets = [];
    const rect = trackSnippets.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const clickTime = roundTime(ratio * data.recording.duration);
    const start = clickTime;
    const dur = roundTime(Math.min(5, data.recording.duration - clickTime));
    if (dur > 0) {
      data.script.snippets.push({ time: start, duration: dur, text: '# enter text here', match: '', label: '' });
      renderTracks();
      updatePlayhead();
      markDirty();
      selectSnippet(data.script.snippets.length - 1);
      showToast('Snippet added (5s) — drag edges to adjust');
    }
  });

  // --- Highlight handle drag-to-resize ---
  function startHighlightHandleDrag(hlIdx, edge, e) {
    e.preventDefault();
    const rect = trackHighlights.getBoundingClientRect();
    const duration = data.recording.duration;
    selectHighlight(hlIdx);
    selectedItem = { type: 'highlight', index: hlIdx, edge: edge };
    const hlEls = trackHighlights.querySelectorAll('.track-item-highlight');
    if (hlEls[hlIdx]) {
      const handle = hlEls[hlIdx].querySelector('.hl-handle-' + (edge === 'start' ? 'left' : 'right'));
      if (handle) handle.classList.add('selected');
    }
    const hl = data.script.highlights[hlIdx];
    seek(edge === 'start' ? hl.time : hl.time + hl.duration);

    function onMove(ev) {
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * duration, duration)));
      const hl = data.script.highlights[hlIdx];
      if (edge === 'start') {
        const newStart = Math.min(t, hl.time + hl.duration - 0.1);
        hl.duration = roundTime(hl.duration + (hl.time - newStart));
        hl.time = newStart;
      } else {
        const newEnd = Math.max(t, hl.time + 0.1);
        hl.duration = roundTime(newEnd - hl.time);
      }
      renderTracks();
      updatePlayhead();
      const els = trackHighlights.querySelectorAll('.track-item-highlight');
      if (els[hlIdx]) {
        els[hlIdx].classList.add('selected');
        const h = els[hlIdx].querySelector('.hl-handle-' + (edge === 'start' ? 'left' : 'right'));
        if (h) h.classList.add('selected');
      }
      const timeInput = document.getElementById('prop-time');
      const durInput = document.getElementById('prop-duration');
      if (timeInput) timeInput.value = hl.time.toFixed(2);
      if (durInput) durInput.value = hl.duration.toFixed(2);
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      markDirty();
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // Highlight drag-to-create on track
  trackHighlights.addEventListener('mousedown', (e) => {
    if (e.target !== trackHighlights) return;
    e.preventDefault();
    if (!data.script.highlights) data.script.highlights = [];
    const rect = trackHighlights.getBoundingClientRect();
    const startX = e.clientX;
    const startRatio = (startX - rect.left) / rect.width;
    const startTime = roundTime(startRatio * data.recording.duration);
    let dragStarted = false;
    let hlDragIdx = null;

    function onMove(ev) {
      if (!dragStarted) {
        if (Math.abs(ev.clientX - startX) < 4) return;
        dragStarted = true;
        hlDragIdx = data.script.highlights.length;
        data.script.highlights.push({ time: startTime, duration: 0, target: { region: { row: 0, col: 0, width: 10, height: 1 } }, style: 'box', color: '#f1fa8c', opacity: 1, badge_text: '', badge_icon: '', fade_in: 0.3, fade_out: 0.3, pulse: false });
        renderTracks();
        updatePlayhead();
      }
      const ratio = (ev.clientX - rect.left) / rect.width;
      const t = roundTime(Math.max(0, Math.min(ratio * data.recording.duration, data.recording.duration)));
      const hl = data.script.highlights[hlDragIdx];
      if (t < startTime) {
        hl.time = t;
        hl.duration = roundTime(startTime - t);
      } else {
        hl.time = startTime;
        hl.duration = roundTime(t - startTime);
      }
      renderTracks();
      updatePlayhead();
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (!dragStarted) {
        seek(startTime);
        return;
      }
      const hl = data.script.highlights[hlDragIdx];
      if (hl.duration < 0.15) {
        data.script.highlights.splice(hlDragIdx, 1);
      } else {
        selectHighlight(hlDragIdx);
        markDirty();
        showToast('Highlight: ' + formatTimePrecise(hl.time) + ' → ' + formatTimePrecise(hl.time + hl.duration));
      }
      renderTracks();
      updatePlayhead();
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  // Double-click on highlights track to create a 3s highlight
  trackHighlights.addEventListener('dblclick', (e) => {
    if (e.target !== trackHighlights) return;
    e.preventDefault();
    if (!data.script.highlights) data.script.highlights = [];
    const rect = trackHighlights.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const clickTime = roundTime(ratio * data.recording.duration);
    const dur = roundTime(Math.min(3, data.recording.duration - clickTime));
    if (dur > 0) {
      data.script.highlights.push({ time: clickTime, duration: dur, target: { region: { row: 0, col: 0, width: 10, height: 1 } }, style: 'box', color: '#f1fa8c', opacity: 1, badge_text: '', badge_icon: '', fade_in: 0.3, fade_out: 0.3, pulse: false });
      renderTracks();
      updatePlayhead();
      markDirty();
      selectHighlight(data.script.highlights.length - 1);
      showToast('Highlight added (3s) — configure in properties');
    }
  });

  // --- Box drag-to-reposition (annotations, cuts, snippets, and highlights) ---
  function startBoxDrag(type, index, e) {
    e.preventDefault();
    const startX = e.clientX;
    const track = type === 'annotation' ? trackAnnotations : type === 'snippet' ? trackSnippets : type === 'highlight' ? trackHighlights : trackCuts;
    const rect = track.getBoundingClientRect();
    const duration = data.recording.duration;
    let dragged = false;

    let item, itemStart, itemDuration;
    if (type === 'annotation') {
      item = data.script.annotations[index];
      itemStart = item.time;
      itemDuration = item.duration;
    } else if (type === 'snippet') {
      item = (data.script.snippets || [])[index];
      itemStart = item.time;
      itemDuration = item.duration;
    } else if (type === 'highlight') {
      item = (data.script.highlights || [])[index];
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
      if (type === 'annotation' || type === 'snippet' || type === 'highlight') {
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
      else if (type === 'snippet') selectSnippet(index);
      else if (type === 'highlight') selectHighlight(index);
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

  // --- Snippet edge nudge via keyboard ---
  function highlightSnippet(idx, edge) {
    trackSnippets.querySelectorAll('.track-item-snippet.selected').forEach(el => el.classList.remove('selected'));
    trackSnippets.querySelectorAll('.cmd-handle.selected').forEach(el => el.classList.remove('selected'));
    const cmdEls = trackSnippets.querySelectorAll('.track-item-snippet');
    if (cmdEls[idx]) {
      cmdEls[idx].classList.add('selected');
      if (edge) {
        const handle = cmdEls[idx].querySelector('.cmd-handle-' + (edge === 'start' ? 'left' : 'right'));
        if (handle) handle.classList.add('selected');
      }
    }
  }

  function nudgeSnippetEdge(cmdIdx, edge, delta) {
    const cmd = data.script.snippets[cmdIdx];
    if (!cmd) return;
    const end = cmd.time + cmd.duration;
    if (edge === 'start') {
      const newStart = roundTime(Math.max(0, Math.min(cmd.time + delta, end - 0.1)));
      const newDur = roundTime(end - newStart);
      if (!snippetOverlapsAny(newStart, newStart + newDur, cmdIdx)) {
        cmd.duration = newDur;
        cmd.time = newStart;
      }
      seek(cmd.time);
    } else {
      const newEnd = roundTime(Math.max(cmd.time + 0.1, Math.min(end + delta, data.recording.duration)));
      const newDur = roundTime(newEnd - cmd.time);
      if (!snippetOverlapsAny(cmd.time, cmd.time + newDur, cmdIdx)) {
        cmd.duration = newDur;
      }
      seek(cmd.time + cmd.duration);
    }
    renderTracks();
    updatePlayhead();
    highlightSnippet(cmdIdx, edge);
    const timeInput = document.getElementById('prop-time');
    const durInput = document.getElementById('prop-duration');
    if (timeInput) timeInput.value = cmd.time.toFixed(2);
    if (durInput) durInput.value = cmd.duration.toFixed(2);
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
    let dragStarted = false;

    function onMove(ev) {
      if (!dragStarted) {
        if (Math.abs(ev.clientX - startX) < 4) return;
        // Threshold exceeded — create the item and start drag
        dragStarted = true;
        const tempIdx = data.script.annotations.length;
        data.script.annotations.push({ time: startTime, duration: 0, text: 'Annotation', position: 'top-right', style: 'callout' });
        annDragState = { index: tempIdx, startTime: startTime };
        renderTracks();
        updatePlayhead();
      }
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
      if (!dragStarted) return; // No drag — let dblclick handle it
      const ann = data.script.annotations[annDragState.index];
      if (ann.duration < 0.15) {
        data.script.annotations.splice(annDragState.index, 1);
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

  // Double-click on annotations track to create a 2s annotation
  trackAnnotations.addEventListener('dblclick', (e) => {
    if (e.target !== trackAnnotations) return;
    e.preventDefault();
    const rect = trackAnnotations.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const clickTime = roundTime(ratio * data.recording.duration);
    const start = clickTime;
    const dur = roundTime(Math.min(2, data.recording.duration - clickTime));
    if (dur > 0) {
      data.script.annotations.push({ time: start, duration: dur, text: 'Annotation', position: 'top-right', style: 'callout' });
      renderTracks();
      updatePlayhead();
      markDirty();
      selectAnnotation(data.script.annotations.length - 1);
      showToast('Annotation added (2s) — drag edges to adjust');
    }
  });

  function addAnnotationAt(time) {
    const start = roundTime(time);
    const end = roundTime(Math.min(time + 1, data.recording.duration));
    if (end > start) {
      data.script.annotations.push({ time: start, duration: roundTime(end - start), text: 'Annotation', position: 'top-right', width: 'medium', style: 'callout' });
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

  // --- Inspector toggle ---
  const inspectorPanel = document.getElementById('inspector-panel');
  const btnInspector = document.getElementById('btn-inspector');
  btnInspector.addEventListener('click', toggleInspector);

  // Delegate close button click (re-rendered each time)
  inspectorPanel.addEventListener('click', (e) => {
    if (e.target.closest('.inspector-close')) {
      hideInspector();
    }
  });

  function toggleInspector() {
    if (inspectorPanel.classList.contains('hidden')) {
      showInspector();
    } else {
      hideInspector();
    }
  }

  function showInspector() {
    inspectorPanel.classList.remove('hidden');
    btnInspector.classList.add('active');
  }

  function hideInspector() {
    inspectorPanel.classList.add('hidden');
    btnInspector.classList.remove('active');
  }

  // --- Settings panel ---
  const settingsPanel = document.getElementById('settings-panel');
  const btnSettings = document.getElementById('btn-settings');
  const settingSpeed = document.getElementById('setting-speed');
  const settingIdle = document.getElementById('setting-idle');
  const settingChrome = document.getElementById('setting-chrome');
  const settingFontFamily = document.getElementById('setting-font-family');
  const settingPrompt = document.getElementById('setting-prompt');
  const settingPromptPattern = document.getElementById('setting-prompt-pattern');

  btnSettings.addEventListener('click', toggleSettings);
  document.getElementById('settings-close').addEventListener('click', hideSettings);

  // Add custom number spinner buttons to settings number inputs (same as properties panel)
  settingsPanel.querySelectorAll('input[type="number"]').forEach(input => {
    const wrap = document.createElement('div');
    wrap.className = 'number-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const step = parseFloat(input.step) || 1;
    const btnUp = document.createElement('button');
    btnUp.type = 'button';
    btnUp.className = 'num-btn num-btn-up';
    btnUp.innerHTML = '&#x25B4;';
    btnUp.addEventListener('click', () => { input.value = (parseFloat(input.value || 0) + step).toFixed(2); input.dispatchEvent(new Event('input')); });
    const btnDown = document.createElement('button');
    btnDown.type = 'button';
    btnDown.className = 'num-btn num-btn-down';
    btnDown.innerHTML = '&#x25BE;';
    btnDown.addEventListener('click', () => { input.value = (parseFloat(input.value || 0) - step).toFixed(2); input.dispatchEvent(new Event('input')); });
    wrap.appendChild(btnUp);
    wrap.appendChild(btnDown);
  });

  function toggleSettings() {
    if (settingsPanel.classList.contains('hidden')) {
      showSettings();
    } else {
      hideSettings();
    }
  }

  function showSettings() {
    // Populate from current data
    const s = data.script.settings;
    settingSpeed.value = s.speed != null ? s.speed : 1.0;
    settingIdle.value = s.idle_time_limit != null ? s.idle_time_limit : '';
    settingChrome.value = s.window_chrome || 'colorful';
    settingFontFamily.value = s.font_family || '';
    settingPrompt.value = s.prompt || '';
    settingPromptPattern.value = s.prompt_pattern || '';
    updatePromptPresets();
    settingsPanel.classList.remove('hidden');
    btnSettings.classList.add('active');
    // Hide inspector if open
    hideInspector();
  }

  function hideSettings() {
    settingsPanel.classList.add('hidden');
    btnSettings.classList.remove('active');
  }

  function updatePromptPresets() {
    const current = settingPrompt.value;
    settingsPanel.querySelectorAll('.prompt-preset').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.prompt === current);
    });
  }

  settingSpeed.addEventListener('change', () => {
    data.script.settings.speed = parseFloat(settingSpeed.value);
    markDirty();
    applySettingsPreview();
  });

  settingIdle.addEventListener('input', () => {
    const v = parseFloat(settingIdle.value);
    if (settingIdle.value === '' || settingIdle.value == null) {
      data.script.settings.idle_time_limit = null;
    } else if (!isNaN(v) && v >= 0) {
      data.script.settings.idle_time_limit = v;
    }
    markDirty();
    applySettingsPreview();
  });

  settingChrome.addEventListener('change', () => {
    data.script.settings.window_chrome = settingChrome.value;
    markDirty();
    applySettingsPreview();
  });

  settingFontFamily.addEventListener('input', () => {
    const v = settingFontFamily.value.trim();
    data.script.settings.font_family = v || null;
    markDirty();
    applySettingsPreview();
  });

  settingPrompt.addEventListener('input', () => {
    const v = settingPrompt.value.trim();
    data.script.settings.prompt = v || null;
    updatePromptPresets();
    markDirty();
    applySettingsPreview();
  });

  settingPromptPattern.addEventListener('input', () => {
    const v = settingPromptPattern.value.trim();
    data.script.settings.prompt_pattern = v || null;
    markDirty();
    applySettingsPreview();
  });

  // Prompt preset clicks
  settingsPanel.addEventListener('click', (e) => {
    const preset = e.target.closest('.prompt-preset');
    if (!preset) return;
    const val = preset.dataset.prompt;
    settingPrompt.value = val;
    data.script.settings.prompt = val;
    updatePromptPresets();
    markDirty();
    applySettingsPreview();
  });

  // Reset playhead and re-render when global settings change
  function applySettingsPreview() {
    seek(0);
  }

  // --- Resize handle (preview ↔ transport/timeline) ---
  (function() {
    const handle = document.getElementById('resize-handle');
    const previewArea = document.querySelector('.preview-area');
    const editorMain = document.querySelector('.editor-main');
    const transport = document.querySelector('.transport');
    const timelinePanel = document.getElementById('timeline-panel');
    const MIN_PREVIEW_HEIGHT = 150;

    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      handle.classList.add('active');
      const startY = e.clientY;
      const startHeight = previewArea.offsetHeight;

      function onMove(ev) {
        const delta = ev.clientY - startY;
        const mainRect = editorMain.getBoundingClientRect();
        const transportH = transport.offsetHeight;
        const handleH = handle.offsetHeight;
        // Min height for timeline area (ruler + 3 tracks)
        const minTimelineH = 120;
        const maxPreviewH = mainRect.height - transportH - handleH - minTimelineH;
        const newHeight = Math.max(MIN_PREVIEW_HEIGHT, Math.min(startHeight + delta, maxPreviewH));
        previewArea.style.height = newHeight + 'px';
        fitViewport();
      }

      function onUp() {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        handle.classList.remove('active');
        // Clear preset active state since user manually adjusted
        document.querySelectorAll('#layout-presets button').forEach(b => b.classList.remove('active'));
        // Refresh playhead cache after resize
        invalidatePlayheadCache();
      }

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  })();

  // --- Layout presets ---
  (function() {
    const presets = document.getElementById('layout-presets');
    const previewArea = document.querySelector('.preview-area');
    const editorMain = document.querySelector('.editor-main');
    const transport = document.querySelector('.transport');
    const handle = document.getElementById('resize-handle');

    presets.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-split]');
      if (!btn) return;
      const split = parseInt(btn.dataset.split, 10);
      presets.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const mainH = editorMain.clientHeight;
      const transportH = transport.offsetHeight;
      const handleH = handle.offsetHeight;
      const available = mainH - transportH - handleH;
      const newHeight = Math.round(available * split / 100);
      previewArea.style.height = newHeight + 'px';
      fitViewport();
      invalidatePlayheadCache();
    });
  })();

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

  [trackChapters, trackAnnotations, trackCuts, trackSnippets].forEach(track => {
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
  document.getElementById('btn-add-snippet').addEventListener('click', addSnippet);
  document.getElementById('btn-save').addEventListener('click', save);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Don't capture when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === ' ') { e.preventDefault(); playing ? pause() : play(); }
    else if (e.key === 'c' || e.key === 'C') { addChapter(); }
    else if (e.key === 'a' && !e.metaKey) { addAnnotation(); }
    else if (e.key === 'x' || e.key === 'X') { addCut(); }
    else if (e.key === 'd' || e.key === 'D') { addSnippet(); }
    else if (e.key === 'h' || e.key === 'H') { addHighlight(); }
    else if (e.key === 'ArrowRight') {
      e.preventDefault();
      if (selectedItem && selectedItem.type === 'cut' && selectedItem.edge) {
        nudgeCutEdge(selectedItem.index, selectedItem.edge, 0.01);
      } else if (selectedItem && selectedItem.type === 'annotation' && selectedItem.edge) {
        nudgeAnnotationEdge(selectedItem.index, selectedItem.edge, 0.01);
      } else if (selectedItem && selectedItem.type === 'snippet' && selectedItem.edge) {
        nudgeSnippetEdge(selectedItem.index, selectedItem.edge, 0.01);
      } else { seek(currentTime + 1); }
    }
    else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      if (selectedItem && selectedItem.type === 'cut' && selectedItem.edge) {
        nudgeCutEdge(selectedItem.index, selectedItem.edge, -0.01);
      } else if (selectedItem && selectedItem.type === 'annotation' && selectedItem.edge) {
        nudgeAnnotationEdge(selectedItem.index, selectedItem.edge, -0.01);
      } else if (selectedItem && selectedItem.type === 'snippet' && selectedItem.edge) {
        nudgeSnippetEdge(selectedItem.index, selectedItem.edge, -0.01);
      } else { seek(currentTime - 1); }
    }
    else if (e.key === ']') { nextChapter(); }
    else if (e.key === '[') { prevChapter(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { window.deleteSelected(); }
    else if (e.key === 'Escape') {
      if (yamlBackdrop.classList.contains('visible')) { hideYamlPreview(); }
      else if (!settingsPanel.classList.contains('hidden')) { hideSettings(); }
      else { propsPanel.classList.remove('open'); selectedItem = null; clearCutHighlights(); }
    }
    else if (e.key === 's' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
    else if (e.key === 'y' || e.key === 'Y') { showYamlPreview(); }
    else if (e.key === 'i' || e.key === 'I') { toggleInspector(); }
    else if (e.key === 'g' || e.key === 'G') { toggleSettings(); }
  });

  // Close panel on click outside
  document.addEventListener('click', (e) => {
    if (!propsPanel.contains(e.target) && !e.target.closest('.track-item-chapter, .track-item-annotation, .track-item-cut, .track-item-snippet, .track-item-highlight')) {
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
    trackSnippets.querySelectorAll('.track-item-snippet.selected').forEach(el => el.classList.remove('selected'));
    trackSnippets.querySelectorAll('.cmd-handle.selected').forEach(el => el.classList.remove('selected'));
    trackHighlights.querySelectorAll('.track-item-highlight.selected').forEach(el => el.classList.remove('selected'));
    trackHighlights.querySelectorAll('.hl-handle.selected').forEach(el => el.classList.remove('selected'));
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
