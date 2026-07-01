"""Preview HTML generation and a tiny local server for the showreel player.

The preview page inlines the player CSS/JS and the manifest, but references
``audio/``, ``media/`` and ``captions/`` files relatively — so the bundle is
served from the output directory as a static site.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import socket
import threading
import webbrowser
from pathlib import Path

from .manifest import Manifest

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _asset(name: str) -> str:
    path = ASSETS_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def render_preview_html(manifest: Manifest) -> str:
    """Return a self-contained HTML page that plays ``manifest``."""
    css = _asset("showreel.css")
    js = _asset("showreel.js")
    manifest_json = manifest.to_json()
    theme_attr = "" if manifest.theme == "auto" else f' data-theme="{manifest.theme}"'
    return f"""<!doctype html>
<html lang="en"{theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{manifest.title} — showreel</title>
<style>{css}</style>
</head>
<body class="gd-showreel-preview">
<div class="gd-showreel" data-aspect="{manifest.aspect}"></div>
<script type="application/json" id="gd-showreel-manifest">{manifest_json}</script>
<script>{js}</script>
<script>
  (function () {{
    var el = document.querySelector('.gd-showreel');
    var data = JSON.parse(document.getElementById('gd-showreel-manifest').textContent);
    window.GreatShowreel.mount(el, data, {{ base: '.' }});
  }})();
</script>
</body>
</html>
"""


def write_preview(out_dir: Path, manifest: Manifest) -> Path:
    """Write ``index.html`` into the build output directory."""
    html = render_preview_html(manifest)
    index = out_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    return index


def _find_free_port(preferred: int) -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):  # noqa: D401 - silence request logging
        pass


def serve_preview(
    out_dir: str | Path, *, port: int = 8771, open_browser: bool = True
) -> None:
    """Serve a built showreel bundle and (optionally) open it in a browser."""
    out_dir = Path(out_dir)
    port = _find_free_port(port)
    handler_cls = functools.partial(_QuietHandler, directory=str(out_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    url = f"http://127.0.0.1:{port}/index.html"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"  Showreel preview at {url}  (Ctrl+C to stop)")
    if open_browser:
        with contextlib.suppress(Exception):
            webbrowser.open(url)
    try:
        thread.join()
    except KeyboardInterrupt:
        print("\n  Stopping preview server.")
        server.shutdown()
