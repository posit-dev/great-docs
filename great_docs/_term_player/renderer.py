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


# A rendered row: background spans `(col, length, color)` and text spans
# `(col, text, color, css_classes)`, with colors already resolved through the theme.
# Rows are hashable so identical rows can be shared between frames.
BgSpan = tuple[int, int, str]
TextSpan = tuple[int, str, str, str]
Line = tuple[tuple[BgSpan, ...], tuple[TextSpan, ...]]


def line_model(row: list[Cell], theme: Theme) -> Line:
    """Resolve one row of terminal cells into its background and text spans."""
    return (tuple(_collect_bg_spans(row, theme)), tuple(_collect_text_spans(row, theme)))


def render_frame(
    state: ScreenState,
    theme: Theme | None = None,
    *,
    font_family: str = DEFAULT_FONT_FAMILY,
    font_size: int = DEFAULT_FONT_SIZE,
    line_height: float = DEFAULT_LINE_HEIGHT,
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
    line_height
        Line height multiplier. Lower values (e.g. 1.2) make box-drawing
        characters connect vertically.
    show_cursor
        Whether to render the cursor block.
    window_chrome
        Window decoration style: "none", "minimal", or "colorful". Chrome is
        drawn by the player as a CSS overlay, so this is accepted for API
        compatibility only.

    Returns
    -------
    str
        A complete SVG document as a string.
    """
    if theme is None:
        theme = Theme()

    lines = [line_model(state.cells[r], theme) for r in range(state.rows)]
    cursor = (state.cursor_row, state.cursor_col) if show_cursor and state.cursor_visible else None

    return render_svg(
        lines,
        cols=state.cols,
        cursor=cursor,
        theme=theme,
        font_family=font_family,
        font_size=font_size,
        line_height=line_height,
    )


def render_svg(
    lines: list[Line],
    *,
    cols: int,
    cursor: tuple[int, int] | None,
    theme: Theme,
    font_family: str = DEFAULT_FONT_FAMILY,
    font_size: int = DEFAULT_FONT_SIZE,
    line_height: float = DEFAULT_LINE_HEIGHT,
) -> str:
    """Render resolved rows (see `line_model`) as an SVG document.

    The player's `renderFrameSvg()` in `termshow.js` mirrors this function so
    that frames drawn in the browser from a v2 manifest match the SVG files
    written at render time. Keep the two in sync.
    """
    cell_w = font_size * 0.6  # Monospace character width approximation
    cell_h = font_size * line_height

    pad = DEFAULT_PADDING
    svg_w = cols * cell_w + pad * 2
    svg_h = len(lines) * cell_h + pad * 2

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

    # Terminal content group
    parts.append(f'<g transform="translate({pad},{pad})">')

    for row_idx, (bg_spans, text_spans) in enumerate(lines):
        y = row_idx * cell_h

        # Colored backgrounds
        for span_col, span_len, bg_color in bg_spans:
            x = span_col * cell_w
            w = span_len * cell_w
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" '
                f'width="{w:.1f}" height="{cell_h:.1f}" fill="{bg_color}"/>'
            )

        # Text runs (grouped by style)
        for span_col, text, fg_color, classes in text_spans:
            x = span_col * cell_w
            cls_attr = f' class="gd-tp-text {classes}"' if classes else ' class="gd-tp-text"'
            parts.append(
                f'<text x="{x:.1f}" y="{y:.1f}"{cls_attr} fill="{fg_color}">'
                f"{xml_escape(text)}</text>"
            )

    # Cursor
    if cursor is not None:
        cx = cursor[1] * cell_w
        cy = cursor[0] * cell_h
        parts.append(
            f'<rect x="{cx:.1f}" y="{cy:.1f}" '
            f'width="{cell_w:.1f}" height="{cell_h:.1f}" '
            f'fill="{theme.cursor or theme.fg}" opacity="0.7" class="gd-tp-cursor"/>'
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


def _chrome_height(style: str) -> float:
    """Height of window chrome decoration in pixels."""
    if style == "none":
        return 0.0
    return 36.0  # Space for traffic lights / title


def _render_chrome(style: str, width: float, theme: Theme) -> str:
    """Render window chrome decorations."""
    parts: list[str] = []

    if style == "minimal":
        # Simple dark bar with three dots
        parts.append(f'<rect width="{width:.1f}" height="36" fill="{theme.bg}" rx="8" ry="8"/>')
        parts.append(f'<rect y="28" width="{width:.1f}" height="8" fill="{theme.bg}"/>')
        # Dots
        parts.append('<circle cx="24" cy="18" r="5" fill="#585b70"/>')
        parts.append('<circle cx="44" cy="18" r="5" fill="#585b70"/>')
        parts.append('<circle cx="64" cy="18" r="5" fill="#585b70"/>')
    elif style == "colorful":
        # macOS-style colored traffic lights
        parts.append(f'<rect width="{width:.1f}" height="36" fill="{theme.bg}" rx="8" ry="8"/>')
        parts.append(f'<rect y="28" width="{width:.1f}" height="8" fill="{theme.bg}"/>')
        parts.append('<circle cx="24" cy="18" r="6" fill="#f38ba8"/>')  # Close
        parts.append('<circle cx="44" cy="18" r="6" fill="#f9e2af"/>')  # Minimize
        parts.append('<circle cx="64" cy="18" r="6" fill="#a6e3a1"/>')  # Maximize

    return "\n".join(parts)


def _collect_bg_spans(row: list[Cell], theme: Theme) -> list[tuple[int, int, str]]:
    """Collect contiguous background color spans from a row.

    Returns list of (start_col, length, bg_color).
    Only returns spans where bg differs from the terminal background.
    """
    spans: list[tuple[int, int, str]] = []
    current_bg: str | None = None
    start = 0
    length = 0

    for col, cell in enumerate(row):
        bg = _resolve_bg(cell, theme)
        if bg == current_bg:
            length += 1
        else:
            if current_bg is not None:
                spans.append((start, length, current_bg))
            current_bg = bg
            start = col
            length = 1

    if current_bg is not None:
        spans.append((start, length, current_bg))

    return spans


def _collect_text_spans(row: list[Cell], theme: Theme) -> list[tuple[int, str, str, str]]:
    """Collect contiguous text spans with the same style.

    Returns list of (start_col, text, fg_color, css_classes).
    Skips trailing spaces for efficiency.

    A span ends after a wide character. The font draws it at its own width,
    which needn't be two cells, so the text after it starts a new span at
    its own column.
    """
    spans: list[tuple[int, str, str, str]] = []

    # Find the last non-space character
    last_nonspace = -1
    for i in range(len(row) - 1, -1, -1):
        if row[i].char != " " or row[i].style.bg is not None:
            last_nonspace = i
            break

    if last_nonspace < 0:
        return spans

    current_fg: str | None = None
    current_classes = ""
    start = 0
    text_parts: list[str] = []
    after_wide = False

    for col in range(last_nonspace + 1):
        cell = row[col]
        if cell.char == "":
            # The second cell of a wide character
            after_wide = True
            continue
        fg = _resolve_fg(cell, theme)
        classes = _style_classes(cell.style)

        if fg == current_fg and classes == current_classes and not after_wide:
            text_parts.append(cell.char)
        else:
            after_wide = False
            if text_parts:
                spans.append((start, "".join(text_parts), current_fg or theme.fg, current_classes))
            current_fg = fg
            current_classes = classes
            start = col
            text_parts = [cell.char]

    if text_parts:
        spans.append((start, "".join(text_parts), current_fg or theme.fg, current_classes))

    return spans


def _resolve_fg(cell: Cell, theme: Theme) -> str:
    """Resolve the effective foreground color for a cell."""
    style = cell.style

    if style.inverse:
        # Inverse swaps fg/bg
        if style.bg is not None:
            return _index_to_color(style.bg, theme)
        return theme.bg

    if style.fg is not None:
        color = _index_to_color(style.fg, theme)
        # Bold + standard color → bright variant
        if style.bold and style.fg.isdigit():
            idx = int(style.fg)
            if idx < 8:
                return _index_to_color(str(idx + 8), theme)
        return color

    return theme.fg


def _resolve_bg(cell: Cell, theme: Theme) -> str | None:
    """Resolve the effective background color for a cell.

    Returns None if the background is the same as the terminal default.
    """
    style = cell.style

    if style.inverse:
        if style.fg is not None:
            color = _index_to_color(style.fg, theme)
            if color != theme.bg:
                return color
        elif theme.fg != theme.bg:
            return theme.fg
        return None

    if style.bg is not None:
        color = _index_to_color(style.bg, theme)
        if color != theme.bg:
            return color

    return None


def _index_to_color(color_ref: str, theme: Theme) -> str:
    """Convert a color reference (index or hex) to a hex color."""
    # Already a hex color?
    if color_ref.startswith("#"):
        return color_ref

    # Numeric index into palette
    try:
        idx = int(color_ref)
    except ValueError:
        return theme.fg

    if idx < len(theme.palette):
        return theme.palette[idx]
    elif idx < 16:
        return ANSI_COLORS_16[idx]

    return theme.fg


def _style_classes(style) -> str:
    """Build CSS class string for a cell style."""
    parts: list[str] = []
    if style.bold:
        parts.append("gd-tp-bold")
    if style.italic:
        parts.append("gd-tp-italic")
    if style.underline:
        parts.append("gd-tp-underline")
    if style.strikethrough:
        parts.append("gd-tp-strikethrough")
    if style.dim:
        parts.append("gd-tp-dim")
    return " ".join(parts)
