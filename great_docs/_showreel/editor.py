"""Showreel Studio — a browser-based scene editor with an agent-drivable API.

`great-docs showreel edit <name>` serves a local editor: a scene list, a live
preview (the real player), and a properties panel. It edits the raw
``.showreel.yml`` document and can rebuild the reel on demand.

Two ways an agent can drive it:

* **Programmatic** — call ``window.__studio.apply(ops)`` / ``snapshot()`` over
  CDP (how an automated agent drives the browser directly).
* **File-based** — edit ``name.showreel.yml`` directly; the editor polls
  ``/api/mtime`` and hot-reloads (the realistic path for a human's local
  Claude Code session).

A **copilot** toggle gates agent-originated changes so a human can take over in
non-copilot phases.
"""

from __future__ import annotations

import functools
import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .builder import build_showreel

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _asset(name: str) -> str:
    path = ASSETS_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_spec_doc(spec_path: Path) -> dict[str, Any]:
    """Load the raw YAML document the editor manipulates."""
    import yaml

    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_spec_doc(spec_path: Path, doc: dict[str, Any]) -> None:
    """Write the edited document back to the spec file."""
    import yaml

    spec_path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def _editor_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Showreel Studio</title>
<style>{_asset("showreel.css")}</style>
<style>{_asset("showreel-editor.css")}</style>
</head>
<body>
<div id="gd-studio"></div>
<script>{_asset("showreel.js")}</script>
<script>{_asset("showreel-editor.js")}</script>
<script>window.GreatStudio.mount(document.getElementById('gd-studio'));</script>
</body>
</html>
"""


class StudioHandler(SimpleHTTPRequestHandler):
    """Serves the editor app, the spec/manifest API, and the built assets."""

    spec_path: Path
    build_dir: Path

    def log_message(self, *args: Any) -> None:  # noqa: D401 - quiet
        pass

    # --- helpers ---
    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _manifest(self) -> dict[str, Any]:
        mpath = self.build_dir / "manifest.json"
        return json.loads(mpath.read_text()) if mpath.exists() else {}

    # --- routes ---
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._html(_editor_html())
        elif self.path == "/api/spec":
            self._json(
                {
                    "spec": load_spec_doc(self.spec_path),
                    "manifest": self._manifest(),
                    "mtime": self.spec_path.stat().st_mtime,
                    "name": self.spec_path.name,
                }
            )
        elif self.path == "/api/mtime":
            self._json({"mtime": self.spec_path.stat().st_mtime})
        else:
            super().do_GET()  # static asset from build_dir (media/audio/manifest)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/save":
            try:
                save_spec_doc(self.spec_path, self._read_body()["spec"])
                self._json({"ok": True, "mtime": self.spec_path.stat().st_mtime})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, status=400)
        elif self.path == "/api/rebuild":
            try:
                body = self._read_body()
                if body.get("spec") is not None:
                    save_spec_doc(self.spec_path, body["spec"])
                build_showreel(self.spec_path, self.build_dir)
                self._json({"ok": True, "manifest": self._manifest()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, status=500)
        else:
            self.send_error(404)


def serve_editor(
    spec_path: str | Path,
    *,
    build_dir: str | Path | None = None,
    port: int = 8770,
    no_browser: bool = False,
) -> None:
    """Build the reel (for preview) and serve the Studio editor."""
    spec_path = Path(spec_path).resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec not found: {spec_path}")

    if build_dir:
        build_dir = Path(build_dir).resolve()
    else:
        name = spec_path.name
        for suffix in (".showreel.yml", ".showreel.yaml", ".yml", ".yaml"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        build_dir = spec_path.parent / ".showreel-edit" / name
    build_showreel(spec_path, build_dir)  # initial build so the preview has a manifest

    StudioHandler.spec_path = spec_path
    StudioHandler.build_dir = build_dir
    handler = functools.partial(StudioHandler, directory=str(build_dir))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)

    url = f"http://127.0.0.1:{port}"
    print(f"✦ Showreel Studio at {url}")
    print(f"  Spec:  {spec_path.name}")
    print(f"  Build: {build_dir}")
    print("  Press Ctrl+C to stop\n")
    if not no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping Studio.")
        server.shutdown()
