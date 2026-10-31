"""
A local web server for a built site
"""

from __future__ import annotations

import functools
import http.server
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["ServeError", "site"]


class ServeError(OSError):
    """An error serving a site with no home page or an unavailable port"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    """A static file handler that drops idle connections"""

    # Reap half-open sockets (e.g. Safari's idle speculative connections) so a stalled
    # connection cannot tie up a worker thread indefinitely.
    timeout = 10


def site(
    site_dir: str | Path,
    port: int = 3000,
    *,
    open_path: str = "",
    open_browser: bool = True,
    report: Callable[[str], None],
) -> None:
    """
    Serve a built site on `localhost` until interrupted

    It returns, instead of raising `KeyboardInterrupt`, when the user presses Ctrl+C.

    Parameters
    ----------
    site_dir
        The built site, which must contain `index.html`.
    port
        The port to listen on.
    open_path
        A page to open instead of the home page, relative to the site, such as
        `reference/index.html`. If the page is missing, the home page opens instead.
    open_browser
        Whether to open the page in the default browser.
    report
        A callback that receives each line for the user: the address, the site directory,
        the page to open, how to stop the server, and a warning for a missing page.

    Raises
    ------
    ServeError
        If `site_dir` has no `index.html`, or the server cannot listen on `port`.
    """
    site_path = Path(site_dir)
    if not (site_path / "index.html").exists():
        raise ServeError(f"No index.html found in {site_path}")

    page = open_path.strip().lstrip("/")
    if page and not (site_path / page).is_file():
        report(f"⚠️  Page '{page}' not found in the site; opening the home page instead.")
        page = ""

    handler = functools.partial(_Handler, directory=str(site_path))
    try:
        # A threading server keeps one idle or speculative connection (notably from Safari)
        # from blocking the whole preview. See issue #219.
        server = http.server.ThreadingHTTPServer(("", port), handler)
    except OSError as error:
        raise ServeError(f"Port {port} is already in use. Try a different port.") from error

    base_url = f"http://localhost:{port}/"
    url = base_url + page
    report(f"\n🌐 Serving site at {base_url}")
    report(f"   Site directory: {site_path}")
    if page:
        report(f"   Opening: {url}")
    report("   Press Ctrl+C to stop\n")

    if open_browser:
        # Open the browser after a short delay so the server is ready
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
