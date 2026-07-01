"""Build-time syntax highlighting for ``code`` scenes.

Highlighting happens at build time with Pygments (already a Great Docs
dependency), so the player stays dependency-free and works offline. Each code
step becomes a self-contained ``<div class="gd-sr-code">`` and the token CSS is
emitted once per build.
"""

from __future__ import annotations

from .spec import Scene

# Pygments styles paired to the player's light/dark surface.
DARK_STYLE = "monokai"
LIGHT_STYLE = "friendly"


def render_code_scene(scene: Scene, *, dark: bool = True) -> str:
    """Highlight every step of ``scene`` in place; return the token CSS."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound

    try:
        lexer = get_lexer_by_name(scene.language)
    except ClassNotFound:
        lexer = get_lexer_by_name("text")

    style = DARK_STYLE if dark else LIGHT_STYLE
    css = ""
    for step in scene.code_steps:
        fmt = HtmlFormatter(style=style, cssclass="gd-sr-code", hl_lines=step.focus)
        step.html = highlight(step.code, lexer, fmt)
        if not css:
            css = fmt.get_style_defs(".gd-sr-code")
    return css
