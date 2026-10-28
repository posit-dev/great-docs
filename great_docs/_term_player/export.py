"""Animated SVG export: one self-contained SVG file that plays a recording.

The SVG animates with CSS alone, so it plays where scripts can't run, such as
an `<img>` in a GitHub or GitLab README. It's built from a version 2 manifest:

- each unique row is defined once and reused with `<use>`
- the unique screens are stacked into a vertical strip behind the terminal
  window, and one `@keyframes` rule moves the strip so the right screen shows
  at each moment
- annotations, the window chrome, chapter labels, and (optionally) chapter
  title cards are drawn over it and faded in and out with their own keyframes

Highlights and copy buttons need the player, so they aren't exported.
"""

from __future__ import annotations

import base64
import html
import math
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .manifest import Manifest
from .renderer import Line

# Past this size, README viewers can play an animated SVG slowly or not at all
SIZE_WARNING_BYTES = 2 * 1024 * 1024
# Seconds the last screen stays up before the animation loops
DEFAULT_END_PAUSE = 2.0
# Seconds each chapter title card is shown (playback pauses meanwhile)
CHAPTER_CARD_SECONDS = 1.5

_BAR_HEIGHT = 36.0
_UI_FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
_EMBEDDED_FONT = "termshow-export"
_FONT_FORMATS = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}

# Short class names for the styles a text span can carry (the file repeats them a lot)
_CLASSES = {
    "gd-tp-bold": "b",
    "gd-tp-italic": "i",
    "gd-tp-underline": "u",
    "gd-tp-strikethrough": "s",
    "gd-tp-dim": "d",
}

# Annotation layout, following the player's CSS
_ANN_FONT_SIZE = {"callout": 13, "subtle": 12, "highlight": 13}
_ANN_MAX_WIDTH = {"small": 0.25, "medium": 0.5, "large": 0.75}
_ANN_MARGIN = 12.0
_ANN_PAD_X = 12.0
_ANN_PAD_Y = 7.0
_ANN_LINE_HEIGHT = 1.4
# Average glyph width of the UI font, in ems, erring wide so text stays inside its box
_UI_CHAR_WIDTH = 0.56
_FADE = 0.3
_CARD_FADE = 0.2


def export_svg(
    manifest: Manifest,
    *,
    dark: bool = False,
    loop: bool = True,
    end_pause: float = DEFAULT_END_PAUSE,
    chapter_cards: bool = False,
    annotations: bool = True,
    font_file: str | Path | None = None,
) -> str:
    """Draw a rendered recording as one animated SVG document.

    Parameters
    ----------
    manifest
        A version 2 manifest from `generate_manifest()`.
    dark
        Draw the dark side of a light/dark theme pair. Ignored when the
        manifest has a single theme.
    loop
        Repeat forever. Otherwise the animation stops on the last screen.
    end_pause
        Seconds to hold the last screen before looping (or stopping).
    chapter_cards
        Pause at each chapter to show its label as a full-screen title card
        for `CHAPTER_CARD_SECONDS`.
    annotations
        Draw the script's annotations.
    font_file
        A `.woff2`, `.woff`, `.ttf`, or `.otf` file to embed and use for the
        terminal text. An SVG shown as an image can't load fonts, so without
        one the viewer's own monospace font is used.

    Returns
    -------
    str
        The SVG document.

    Raises
    ------
    ValueError
        If the manifest has no cell grid (it isn't version 2), or the font
        file's type isn't supported.
    """
    screen = manifest.screen
    if screen is None or not manifest.frames:
        raise ValueError("animated SVG export needs a version 2 manifest")

    side = manifest.dark if dark else None
    fg, bg = (side.fg, side.bg) if side else (screen.fg, screen.bg)
    cursor_color = (side.cursor if side else screen.cursor) or fg
    rows_by_id = side.lines if side else manifest.lines

    # Geometry: every screen gets a slot the size of the largest one
    cell_w = screen.font_size * 0.6
    cell_h = screen.font_size * screen.line_height
    pad = screen.padding
    cols = max(fr.size[0] if fr.size else manifest.cols for fr in manifest.frames)
    rows = max(len(fr.lines) for fr in manifest.frames)
    term_w = cols * cell_w + pad * 2
    term_h = rows * cell_h + pad * 2
    bar_h = _BAR_HEIGHT if manifest.window_chrome != "none" or manifest.chapters else 0.0
    width = term_w
    height = bar_h + term_h

    # Timeline. Title cards push everything after each chapter back by the card's length.
    card = CHAPTER_CARD_SECONDS if chapter_cards and manifest.chapters else 0.0
    shift = _timeline_shift([ch.time for ch in manifest.chapters], card)
    total = shift(manifest.duration) + max(0.0, end_pause)
    animated = total > 0

    def pct(t: float) -> str:
        return _fmt_pct(min(100.0, max(0.0, t / total * 100))) if animated else "0"

    iteration = "infinite" if loop else "1 forwards"

    def animation(name: str, timing: str) -> str:
        return f"animation:{name} {total:.3f}s {timing} {iteration}" if animated else ""

    # Collapse runs of keyframes that show the same screen
    steps: list[tuple[float, int]] = []
    for kf in manifest.keyframes:
        if kf.frame is None:
            continue
        if not steps or steps[-1][1] != kf.frame:
            steps.append((shift(kf.time), kf.frame))
    last_offset = steps[-1][1] * term_h if steps else 0.0

    styles: list[str] = []
    body: list[str] = []

    font_family = screen.font_family
    if font_file is not None:
        styles.append(_font_face(Path(font_file)))
        font_family = f'"{_EMBEDDED_FONT}", {font_family}'
    styles.append(
        _text_styles(font_family, screen.font_size)
        + "@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}"
        ".cur{animation:blink 1s step-end infinite}"
    )

    # Rows, each defined once
    used = sorted({i for fr in manifest.frames for i in fr.lines if _has_content(rows_by_id[i])})
    defs = [_row_def(i, rows_by_id[i], cell_w, cell_h) for i in used]

    # The strip of screens, moved by one animation. Its `transform` attribute
    # shows the last screen where CSS animation doesn't run.
    strip_stops = {"0": "transform:translateY(0px)"}
    strip_stops.update(
        {pct(t): f"transform:translateY({-slot * term_h:.1f}px)" for t, slot in steps}
    )
    if steps:
        strip_stops["100"] = f"transform:translateY({-last_offset:.1f}px)"
    styles.append(_keyframes("strip", strip_stops))
    body.append(
        f'<svg y="{bar_h:.1f}" width="{term_w:.1f}" height="{term_h:.1f}" '
        f'viewBox="0 0 {term_w:.1f} {term_h:.1f}">'
    )
    body.append(
        f'<g transform="translate(0,{-last_offset:.1f})" style="{animation("strip", "step-end")}">'
    )
    for slot, frame in enumerate(manifest.frames):
        body.append(f'<g transform="translate({pad},{slot * term_h + pad:.1f})">')
        for row_idx, line_id in enumerate(frame.lines):
            if _has_content(rows_by_id[line_id]):
                body.append(f'<use href="#l{line_id}" y="{row_idx * cell_h:.1f}"/>')
        if frame.cursor is not None:
            body.append(
                f'<rect x="{frame.cursor[1] * cell_w:.1f}" y="{frame.cursor[0] * cell_h:.1f}" '
                f'width="{cell_w:.1f}" height="{cell_h:.1f}" fill="{cursor_color}" '
                f'opacity="0.7" class="cur"/>'
            )
        body.append("</g>")
    body.append("</g>")
    body.append("</svg>")

    # Annotations, faded in and out over the terminal
    if annotations:
        for n, ann in enumerate(manifest.annotations):
            start, end = shift(ann.time), min(total, shift(ann.time + ann.duration))
            if not animated or start >= total or end <= start:
                continue
            fade = min(_FADE, (end - start) / 2)
            name = f"a{n}"
            styles.append(
                _keyframes(
                    name,
                    {
                        "0": "opacity:0",
                        pct(start): "opacity:0",
                        pct(start + fade): "opacity:1",
                        pct(end - fade): "opacity:1",
                        pct(end): "opacity:0",
                        "100": "opacity:0",
                    },
                )
            )
            body.append(
                _annotation(
                    ann.text, ann.position, ann.style, ann.width, term_w, term_h, bar_h, fg, bg
                ).replace("<g ", f'<g style="{animation(name, "linear")}" ', 1)
            )

    # Chapter title cards, over the terminal while playback waits
    if card and animated:
        for n, ch in enumerate(manifest.chapters):
            end = shift(ch.time)
            start = end - card
            name = f"k{n}"
            styles.append(
                _keyframes(
                    name,
                    {
                        "0": "opacity:0",
                        pct(start): "opacity:0",
                        pct(start + _CARD_FADE): "opacity:1",
                        pct(end - _CARD_FADE): "opacity:1",
                        pct(end): "opacity:0",
                        "100": "opacity:0",
                    },
                )
            )
            body.append(
                f'<g opacity="0" style="{animation(name, "linear")}">'
                f'<rect y="{bar_h:.1f}" width="{term_w:.1f}" height="{term_h:.1f}" fill="{bg}"/>'
                f'<text x="{term_w / 2:.1f}" y="{bar_h + term_h / 2:.1f}" class="ui" '
                f'font-size="20" font-weight="600" text-anchor="middle" '
                f'dominant-baseline="central" fill="{fg}">{xml_escape(ch.label)}</text></g>'
            )

    # Title bar: window chrome and the current chapter's label
    bar: list[str] = []
    if bar_h:
        bar.append(
            f'<line x1="0" y1="{bar_h:.1f}" x2="{width:.1f}" y2="{bar_h:.1f}" '
            f'stroke="{fg}" stroke-opacity="0.12"/>'
        )
        if manifest.window_chrome == "colorful":
            dots = ["#f38ba8", "#f9e2af", "#a6e3a1"]
            bar.extend(_dots(dots, bar_h, 1.0))
        elif manifest.window_chrome == "minimal":
            bar.extend(_dots([fg] * 3, bar_h, 0.35))
        chapters = manifest.chapters
        for n, ch in enumerate(chapters):
            start = shift(ch.time) - card
            end = shift(chapters[n + 1].time) - card if n + 1 < len(chapters) else total
            is_last = n == len(chapters) - 1
            name = f"c{n}"
            styles.append(
                _keyframes(
                    name,
                    {"0": "opacity:0", pct(start): "opacity:1", pct(end): "opacity:0"}
                    if not is_last
                    else {"0": "opacity:0", pct(start): "opacity:1", "100": "opacity:1"},
                )
            )
            bar.append(
                f'<text x="{width / 2:.1f}" y="{bar_h / 2:.1f}" class="ui" font-size="13" '
                f'font-weight="500" text-anchor="middle" dominant-baseline="central" '
                f'fill="{fg}" fill-opacity="0.85" opacity="{1 if is_last else 0}" '
                f'style="{animation(name, "step-end")}">{xml_escape(ch.label)}</text>'
            )

    # Without motion, everything falls back to its attributes: the last screen
    styles.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}}")

    title = manifest.title or "Terminal recording"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" '
        f'width="{width:.1f}" height="{height:.1f}" role="img" '
        f'aria-label="{html.escape(title, quote=True)}">',
        f"<title>{xml_escape(title)}</title>",
        "<style>" + "".join(styles) + "</style>",
        "<defs>",
        f'<clipPath id="win"><rect width="{width:.1f}" height="{height:.1f}" rx="8" ry="8"/>'
        "</clipPath>",
        *defs,
        "</defs>",
        '<g clip-path="url(#win)">',
        f'<rect width="{width:.1f}" height="{height:.1f}" fill="{bg}"/>',
        *bar,
        *body,
        "</g>",
        f'<rect x="0.5" y="0.5" width="{width - 1:.1f}" height="{height - 1:.1f}" rx="8" ry="8" '
        f'fill="none" stroke="{fg}" stroke-opacity="0.12"/>',
        "</svg>",
    ]
    return "\n".join(parts)


def picture_snippet(light_src: str, dark_src: str, alt: str) -> str:
    """HTML that shows `dark_src` to readers in dark mode and `light_src` otherwise.

    GitHub and GitLab honor `prefers-color-scheme` in a README's `<picture>`.
    """
    q = lambda s: html.escape(s, quote=True)  # noqa: E731
    return (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="{q(dark_src)}">\n'
        f'  <img src="{q(light_src)}" alt="{q(alt)}">\n'
        "</picture>"
    )


def _timeline_shift(chapter_times: list[float], card: float) -> Callable[[float], float]:
    """Map a playback time to export time, adding `card` seconds at each chapter."""
    times = sorted(chapter_times) if card else []

    def shift(t: float) -> float:
        return t + card * sum(1 for c in times if c <= t + 1e-9)

    return shift


def _fmt_pct(p: float) -> str:
    text = f"{p:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _keyframes(name: str, stops: dict[str, str]) -> str:
    """A `@keyframes` rule. Stops are in time order; a repeated percentage keeps its last value."""
    return f"@keyframes {name}{{" + "".join(f"{p}%{{{v}}}" for p, v in stops.items()) + "}"


def _text_styles(font_family: str, font_size: int) -> str:
    """The CSS for terminal text (class `t` and the short style classes) and UI text."""
    return (
        f".t{{font-family:{font_family};font-size:{font_size}px;"
        f"white-space:pre;dominant-baseline:text-before-edge}}"
        ".b{font-weight:700}.i{font-style:italic}.u{text-decoration:underline}"
        ".s{text-decoration:line-through}.d{opacity:0.6}"
        f".ui{{font-family:{_UI_FONT}}}"
    )


def _has_content(line: Line) -> bool:
    return bool(line[0] or line[1])


def _row_def(line_id: int, line: Line, cell_w: float, cell_h: float) -> str:
    """One row as a reusable group, drawn at y=0 (see `render_svg`)."""
    parts = [f'<g id="l{line_id}">']
    for col, length, color in line[0]:
        parts.append(
            f'<rect x="{col * cell_w:.1f}" width="{length * cell_w:.1f}" '
            f'height="{cell_h:.1f}" fill="{color}"/>'
        )
    for col, text, color, classes in line[1]:
        cls = " ".join(["t", *(_CLASSES.get(c, c) for c in classes.split())])
        parts.append(f'<text x="{col * cell_w:.1f}" class="{cls}" fill="{color}">')
        parts[-1] += f"{xml_escape(text)}</text>"
    parts.append("</g>")
    return "".join(parts)


def _dots(colors: list[str], bar_h: float, opacity: float) -> list[str]:
    return [
        f'<circle cx="{20 + 18 * i}" cy="{bar_h / 2:.1f}" r="6" fill="{color}" '
        f'fill-opacity="{opacity:g}"/>'
        for i, color in enumerate(colors)
    ]


def _annotation(
    text: str,
    position: str,
    style: str,
    width: str,
    term_w: float,
    term_h: float,
    top: float,
    fg: str,
    bg: str,
) -> str:
    """An annotation box, laid out like the player's (hidden until animated)."""
    font_size = _ANN_FONT_SIZE.get(style, 13)
    char_w = font_size * _UI_CHAR_WIDTH
    max_w = term_w * _ANN_MAX_WIDTH.get(width, 0.5)
    max_chars = max(1, math.floor((max_w - 2 * _ANN_PAD_X) / char_w))
    lines = _wrap(text, max_chars)
    line_h = font_size * _ANN_LINE_HEIGHT
    box_w = max(len(line) for line in lines) * char_w + 2 * _ANN_PAD_X
    box_h = len(lines) * line_h + 2 * _ANN_PAD_Y

    m = _ANN_MARGIN
    if position.endswith("left"):
        x = m
    elif position.endswith("right"):
        x = term_w - m - box_w
    else:
        x = (term_w - box_w) / 2
    if position.startswith("top"):
        y = m
    elif position.startswith("bottom"):
        y = term_h - m - box_h
    else:
        y = (term_h - box_h) / 2
    y += top

    dark_bg = _is_dark(bg)
    if style == "highlight":
        accent = "#f9e2af" if dark_bg else "#9a6700"
        box = (
            f'<rect width="{box_w:.1f}" height="{box_h:.1f}" rx="6" fill="{bg}" '
            f'fill-opacity="0.92"/><rect width="{box_w:.1f}" height="{box_h:.1f}" rx="6" '
            f'fill="{accent}" fill-opacity="0.15" stroke="{accent}" stroke-opacity="0.5"/>'
        )
        color = accent
    elif style == "subtle":
        box = (
            f'<rect width="{box_w:.1f}" height="{box_h:.1f}" rx="6" fill="{bg}" '
            f'fill-opacity="0.75"/>'
        )
        color = fg
    else:
        box = (
            f'<rect width="{box_w:.1f}" height="{box_h:.1f}" rx="6" fill="{bg}" '
            f'fill-opacity="0.92" stroke="{fg}" stroke-opacity="0.3"/>'
        )
        color = fg

    spans = "".join(
        f'<tspan x="{_ANN_PAD_X:.1f}" y="{_ANN_PAD_Y + i * line_h:.1f}">{xml_escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<g opacity="0" transform="translate({x:.1f},{y:.1f})">{box}'
        f'<text class="ui" font-size="{font_size}" fill="{color}" '
        f'dominant-baseline="text-before-edge">{spans}</text></g>'
    )


def _wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap, keeping explicit line breaks and splitting overlong words."""
    out: list[str] = []
    for paragraph in text.splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            while len(word) > max_chars:
                if line:
                    out.append(line)
                    line = ""
                out.append(word[:max_chars])
                word = word[max_chars:]
            if not line:
                line = word
            elif len(line) + 1 + len(word) <= max_chars:
                line += " " + word
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


def _is_dark(color: str) -> bool:
    """Whether a `#rgb` or `#rrggbb` color has relative luminance below 0.5."""
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return True
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 < 0.5


def _font_face(path: Path) -> str:
    fmt = _FONT_FORMATS.get(path.suffix.lower())
    if fmt is None:
        raise ValueError(
            f"Unsupported font file {path.name!r}: use one of {', '.join(_FONT_FORMATS)}"
        )
    mime = {"truetype": "font/ttf", "opentype": "font/otf"}.get(fmt, f"font/{fmt}")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f'@font-face{{font-family:"{_EMBEDDED_FONT}";'
        f'src:url(data:{mime};base64,{data}) format("{fmt}")}}'
    )
