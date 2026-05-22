"""SVG renderer: converts terminal screen states into SVG frames."""

from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape

from .emulator import ANSI_COLORS_16, Cell, ScreenState
from .parser import Theme

# Default rendering configuration
DEFAULT_FONT_FAMILY = "JetBrains Mono, Fira Code, SF Mono, Menlo, Consolas, monospace"
DEFAULT_FONT_SIZE = 14
DEFAULT_CELL_WIDTH = 8.4  # Approximate character width at 14px
DEFAULT_LINE_HEIGHT = 1.5  # Line height multiplier
DEFAULT_PADDING = 16  # Padding inside terminal frame


def render_frame(
    state: ScreenState,
    theme: Theme | None = None,
    *,
    font_family: str = DEFAULT_FONT_FAMILY,
    font_size: int = DEFAULT_FONT_SIZE,
    show_cursor: bool = True,
    window_chrome: str = "none",
) -> str:
    """Render a terminal screen state as an SVG string.

    Parameters
    ----------
    state
        The terminal screen state to render.
    theme
        Color theme. Uses default dark theme if not provided.
    font_family
        CSS font-family for terminal text.
    font_size
        Font size in pixels.
    show_cursor
        Whether to render the cursor block.
    window_chrome
        Window decoration style: "none", "minimal", or "colorful".

    Returns
    -------
    str
        A complete SVG document as a string.
    """
    if theme is None:
        theme = Theme()

    cell_w = font_size * 0.6  # Monospace character width approximation
    cell_h = font_size * DEFAULT_LINE_HEIGHT

    pad = DEFAULT_PADDING
    chrome_h = _chrome_height(window_chrome)

    content_w = state.cols * cell_w
    content_h = state.rows * cell_h
    svg_w = content_w + pad * 2
    svg_h = content_h + pad * 2 + chrome_h

    parts: list[str] = []

    # SVG header
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_w:.1f} {svg_h:.1f}" '
        f'width="{svg_w:.1f}" height="{svg_h:.1f}" '
        f'role="img" aria-label="Terminal recording frame">'
    )

    # Styles
    parts.append(
        f"<style>"
        f".gd-tp-text{{font-family:{font_family};font-size:{font_size}px;"
        f"white-space:pre;dominant-baseline:text-before-edge}}"
        f".gd-tp-bold{{font-weight:700}}"
        f".gd-tp-italic{{font-style:italic}}"
        f".gd-tp-underline{{text-decoration:underline}}"
        f".gd-tp-strikethrough{{text-decoration:line-through}}"
        f".gd-tp-dim{{opacity:0.6}}"
        f"@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:0}}}}"
        f".gd-tp-cursor{{animation:blink 1s step-end infinite}}"
        f"</style>"
    )

    # Background
    parts.append(
        f'<rect width="{svg_w:.1f}" height="{svg_h:.1f}" fill="{theme.bg}" rx="8" ry="8"/>'
    )

    # Window chrome
    if window_chrome != "none":
        parts.append(_render_chrome(window_chrome, svg_w, theme))

    # Terminal content group
    content_y = pad + chrome_h
    parts.append(f'<g transform="translate({pad},{content_y})">')

    # Render each row
    for row_idx in range(state.rows):
        row = state.cells[row_idx]
        y = row_idx * cell_h

        # Render background spans (colored backgrounds)
        bg_spans = _collect_bg_spans(row, theme)
        for span_col, span_len, bg_color in bg_spans:
            x = span_col * cell_w
            w = span_len * cell_w
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" '
                f'width="{w:.1f}" height="{cell_h:.1f}" fill="{bg_color}"/>'
            )

        # Render text spans (grouped by style for efficiency)
        text_spans = _collect_text_spans(row, theme)
        for span_col, text, fg_color, classes in text_spans:
            x = span_col * cell_w
            cls_attr = f' class="gd-tp-text {classes}"' if classes else ' class="gd-tp-text"'
            fill_attr = f' fill="{fg_color}"' if fg_color else f' fill="{theme.fg}"'
            parts.append(
                f'<text x="{x:.1f}" y="{y:.1f}"{cls_attr}{fill_attr}>{xml_escape(text)}</text>'
            )

    # Cursor
    if show_cursor and state.cursor_visible:
        cx = state.cursor_col * cell_w
        cy = state.cursor_row * cell_h
        parts.append(
            f'<rect x="{cx:.1f}" y="{cy:.1f}" '
            f'width="{cell_w:.1f}" height="{cell_h:.1f}" '
            f'fill="{theme.fg}" opacity="0.7" class="gd-tp-cursor"/>'
        )

    parts.append("</g>")
    parts.append("</svg>")

    return "\n".join(parts)


def render_frames(
    states: list[tuple[float, ScreenState]],
    theme: Theme | None = None,
    **kwargs,
) -> list[tuple[float, str]]:
    """Render multiple screen states as SVG frames.

    Parameters
    ----------
    states
        List of (time, screen_state) tuples.
    theme
        Color theme.
    **kwargs
        Additional arguments passed to render_frame.

    Returns
    -------
    list of (time, svg_string) tuples.
    """
    return [(time, render_frame(state, theme, **kwargs)) for time, state in states]


