"""Execute notebooks to static HTML for capture.

marimo notebooks are run and exported with ``marimo export html`` (which
executes the notebook and emits a self-contained HTML snapshot). The capture
driver then opens that HTML in Chrome and grabs keyframes. Jupyter support is a
future addition.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .capture import CaptureError


def export_notebook_html(
    notebook_path: str | Path,
    out_html: str | Path,
    *,
    runtime: str = "marimo",
    timeout: float = 180.0,
) -> Path:
    """Run a notebook and export it to a static HTML file."""
    notebook_path = Path(notebook_path)
    if not notebook_path.exists():
        raise CaptureError(f"notebook not found: {notebook_path}")
    if runtime != "marimo":
        raise CaptureError(f"notebook runtime {runtime!r} is not supported yet (use marimo)")
    try:
        import marimo  # noqa: F401
    except Exception as exc:  # pragma: no cover - optional dep
        raise CaptureError(f"marimo is required for notebook scenes: {exc}") from exc

    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "marimo", "export", "html",
        str(notebook_path), "-o", str(out_html), "--no-watch",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover
        raise CaptureError(f"marimo export timed out after {timeout}s") from exc
    if proc.returncode != 0 or not out_html.exists():
        raise CaptureError(
            "marimo export failed:\n" + proc.stderr.decode("utf-8", "replace")[-800:]
        )
    return out_html
