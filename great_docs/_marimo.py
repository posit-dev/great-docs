"""Marimo notebook integration for Great Docs.

Provides utilities for generating marimo island HTML at build time
using MarimoIslandGenerator, and supporting the marimo Quarto shortcode.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

# Marimo islands CDN base
_ISLANDS_CDN = "https://cdn.jsdelivr.net/npm/@marimo-team/islands"
_DEFAULT_VERSION = "0.23.8"


def get_islands_head_html(version: str = _DEFAULT_VERSION) -> str:
    """Return the <script> and <link> tags needed in <head> for marimo islands."""
    return (
        f'<script type="module" src="{_ISLANDS_CDN}@{version}/dist/main.js"></script>\n'
        f'<link href="{_ISLANDS_CDN}@{version}/dist/style.css" '
        f'rel="stylesheet" crossorigin="anonymous"/>\n'
        '<link rel="preconnect" href="https://cdn.jsdelivr.net"/>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com"/>\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>'
    )


def generate_islands_html(
    notebook_path: Path,
    *,
    display_code: bool = True,
    reactive: bool = True,
    app_id: str | None = None,
) -> str:
    """Generate marimo island HTML from a notebook file.

    Uses MarimoIslandGenerator to produce correct island markup
    that the @marimo-team/islands runtime can activate.

    Parameters
    ----------
    notebook_path
        Path to the .py marimo notebook file.
    display_code
        Whether to show cell source code.
    reactive
        Whether cells should be reactive (run with Pyodide in browser).
    app_id
        Unique app identifier for namespacing islands on the same page.
        Defaults to the notebook stem name.

    Returns
    -------
    str
        HTML string containing <marimo-island> elements.
    """
    import io

    from marimo import MarimoIslandGenerator

    gen = MarimoIslandGenerator.from_file(str(notebook_path), display_code=display_code)

    # Build the app (runs cells to capture output; errors are non-fatal)
    # Redirect stdout/stderr during build to avoid marimo writing to
    # wrapped streams that might lack attributes
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(gen.build())
        finally:
            loop.close()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    # Render body HTML (the islands themselves)
    body_html = gen.render_body(
        include_init_island=False,
        max_width="100%",
    )

    # Ensure data-reactive matches the requested mode
    if not reactive:
        body_html = body_html.replace('data-reactive="true"', 'data-reactive="false"')

    # When hiding code, strip islands whose output is empty (utility cells)
    if not display_code:
        body_html = re.sub(
            r"<marimo-island[^>]*>\s*<marimo-cell-output>\s*<span></span>\s*"
            r"</marimo-cell-output>\s*(?:<marimo-cell-code[^>]*>.*?</marimo-cell-code>\s*)?"
            r"</marimo-island>\s*",
            "",
            body_html,
            flags=re.DOTALL,
        )

    # Namespace islands with a unique app_id (defaults to notebook stem)
    resolved_app_id = app_id or notebook_path.stem
    if resolved_app_id != "main":
        body_html = body_html.replace('data-app-id="main"', f'data-app-id="{resolved_app_id}"')

    return body_html


def generate_islands_for_build(
    notebook_path: Path,
    output_path: Path,
    *,
    display_code: bool = True,
    reactive: bool = True,
    app_id: str | None = None,
) -> None:
    """Pre-generate island HTML and save to a file for the Lua shortcode to read.

    Parameters
    ----------
    notebook_path
        Path to the .py marimo notebook.
    output_path
        Path to write the generated HTML fragment.
    display_code
        Whether to show cell source code.
    reactive
        Whether cells should be reactive.
    app_id
        Unique app identifier for namespacing islands on the same page.
        Defaults to the notebook stem name.
    """
    html = generate_islands_html(
        notebook_path,
        display_code=display_code,
        reactive=reactive,
        app_id=app_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def parse_marimo_source(source: str) -> list[dict[str, str]]:
    """Parse marimo notebook source text into cells (for fallback/testing)."""
    cells: list[dict[str, str]] = []

    cell_pattern = re.compile(
        r"@app\.cell(?:\([^)]*\))?\s*\n"
        r"def\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:->[^:]*)?:\s*\n"
        r"((?:(?:    .*)?\n)*)",
        re.MULTILINE,
    )

    for match in cell_pattern.finditer(source):
        name = match.group(1)
        body = match.group(2)

        lines = body.split("\n")
        dedented = []
        for line in lines:
            if line.startswith("    "):
                dedented.append(line[4:])
            elif line.strip() == "":
                dedented.append("")
            else:
                dedented.append(line)

        while dedented and dedented[-1].strip() == "":
            dedented.pop()
        if dedented and dedented[-1].strip().startswith("return"):
            dedented.pop()
        while dedented and dedented[-1].strip() == "":
            dedented.pop()

        code = "\n".join(dedented)
        if code.strip():
            cells.append({"code": code, "name": name})

    return cells


def notebook_source(path: Path) -> str:
    """Return raw notebook source for copy-to-clipboard."""
    return path.read_text(encoding="utf-8")
