"""Marimo notebook integration for Great Docs.

Provides utilities for generating marimo island HTML at build time using MarimoIslandGenerator, and
supporting the marimo Quarto shortcode.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

# Marimo islands CDN base
_ISLANDS_CDN = "https://cdn.jsdelivr.net/npm/@marimo-team/islands"

# Fallback used only when the installed marimo version can't be determined.
_FALLBACK_VERSION = "0.23.8"

# Google Fonts + KaTeX CSS that the islands runtime expects (kept in sync with
# marimo's own MarimoIslandGenerator.render_head).
_FONT_URL = (
    "https://fonts.googleapis.com/css2?family=Fira+Mono:wght@400;500;700"
    "&amp;family=Lora&amp;family=PT+Sans:wght@400;700&amp;display=swap"
)
_KATEX_CSS = "https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css"


def islands_runtime_version() -> str:
    """Return the @marimo-team/islands runtime version to load from the CDN.

    The browser runtime must match the marimo version that generated the island markup, so this
    defaults to the installed marimo package version. Falls back to a known-good pin if marimo can't
    be imported.
    """
    try:
        import marimo

        return str(marimo.__version__)
    except Exception:
        return _FALLBACK_VERSION


def get_islands_head_html(version: str | None = None) -> str:
    """Return the <script> and <link> tags needed in <head> for marimo islands.

    Includes the islands runtime JS/CSS, the fonts/KaTeX stylesheets the runtime expects, and the
    `<marimo-filename>` marker element that the runtime looks for when bootstrapping the Pyodide
    kernel.
    """
    if version is None:
        version = islands_runtime_version()
    return (
        f'<script type="module" src="{_ISLANDS_CDN}@{version}/dist/main.js"></script>\n'
        f'<link href="{_ISLANDS_CDN}@{version}/dist/style.css" '
        'rel="stylesheet" title="marimo-islands" crossorigin="anonymous"/>\n'
        '<link rel="preconnect" href="https://cdn.jsdelivr.net"/>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com"/>\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>\n'
        f'<link href="{_FONT_URL}" rel="stylesheet"/>\n'
        f'<link rel="stylesheet" href="{_KATEX_CSS}" crossorigin="anonymous"/>\n'
        "<marimo-filename hidden></marimo-filename>"
    )


def generate_islands_html(
    notebook_path: Path,
    *,
    display_code: bool = True,
    reactive: bool = True,
    app_id: str | None = None,
) -> str:
    """Generate marimo island HTML from a notebook file.

    Uses MarimoIslandGenerator to produce correct island markup that the @marimo-team/islands
    runtime can activate.

    Parameters
    ----------
    notebook_path
        Path to the .py marimo notebook file.
    display_code
        Whether to show cell source code.
    reactive
        Whether cells should be reactive (run with Pyodide in browser).
    app_id
        Unique app identifier for namespacing islands on the same page. Defaults to the notebook
        stem name.

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

    # Render body HTML (the islands themselves). The init island renders a
    # loading spinner and is what triggers the islands runtime to boot the
    # Pyodide kernel — without it the custom elements load but never hydrate,
    # so cells stay static and non-interactive.
    body_html = gen.render_body(
        include_init_island=True,
        max_width="100%",
    )

    # Ensure data-reactive matches the requested mode
    if not reactive:
        body_html = body_html.replace('data-reactive="true"', 'data-reactive="false"')

    # NOTE: We intentionally do NOT strip "empty output" islands (e.g. an `import marimo as mo`
    # cell) even when hiding code. Those cells are part of the reactive graph and removing their
    # island leaves the runtime unable to resolve `mo` and every dependent cell fails with a
    # NameError. With display_code=False the code editor isn't shown, and marimo's own
    # `empty:hidden` styling collapses the empty output, so the cell stays invisible while still
    # executing.

    # Tag the leading run of output-less "setup" cells (imports/utility) so the front-end can
    # collapse them behind a disclosure toggle. Only meaningful when code is shown and in no-code
    # mode these cells are hidden anyway. This is done at build time (where MarimoIslandGenerator
    # has actually run the notebook) so emptiness is authoritative and not subject to render races.
    if display_code:
        body_html = _tag_setup_islands(body_html)

    # Namespace islands with a unique app_id (defaults to notebook stem)
    resolved_app_id = app_id or notebook_path.stem
    if resolved_app_id != "main":
        body_html = body_html.replace('data-app-id="main"', f'data-app-id="{resolved_app_id}"')

    return body_html


# Matches a marimo cell whose output is empty (e.g. an `import` cell).
_EMPTY_OUTPUT_RE = re.compile(
    r"<marimo-cell-output>\s*<span>\s*</span>\s*</marimo-cell-output>", re.DOTALL
)
_ISLAND_RE = re.compile(r"<marimo-island\b.*?</marimo-island>", re.DOTALL)


def _tag_setup_islands(body_html: str) -> str:
    """Add `data-gd-setup="true"` to the leading run of empty-output cells.

    Walks islands in document order, skipping the non-reactive init/loader island, and marks each
    reactive cell whose output is empty until the first cell that produces output. Only the leading
    run is tagged, so a cell that renders anything is never collapsed.
    """
    out: list[str] = []
    pos = 0
    leading = True

    for match in _ISLAND_RE.finditer(body_html):
        out.append(body_html[pos : match.start()])
        pos = match.end()
        block = match.group(0)

        open_tag = block[: block.find(">") + 1]
        is_reactive = 'data-reactive="true"' in open_tag

        if is_reactive:
            if leading and _EMPTY_OUTPUT_RE.search(block):
                block = block.replace("<marimo-island", '<marimo-island data-gd-setup="true"', 1)
            else:
                # First reactive cell with real output ends the leading run.
                leading = False

        out.append(block)

    out.append(body_html[pos:])
    return "".join(out)


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
        Unique app identifier for namespacing islands on the same page. Defaults to the notebook
        stem name.
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
