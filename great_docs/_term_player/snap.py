"""Screenshots: one moment of a recording as a still SVG or PNG.

The SVG is drawn like a frame of the animated export (the same rows, window
chrome, chapter label, and annotations), without any animation, so it works
as a poster image or a social card. A PNG is made from the SVG by an external
rasterizer, `rsvg-convert` or `resvg`, whichever is installed.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .export import (
    _BAR_HEIGHT,
    _EMBEDDED_FONT,
    _annotation,
    _dots,
    _font_face,
    _has_content,
    _row_def,
    _text_styles,
)
from .manifest import FrameEntry, Manifest

# Tried in this order
RASTERIZERS = ("rsvg-convert", "resvg")


class SnapError(Exception):
    """The moment asked for isn't in the recording, or a PNG can't be made."""


def snap_time(manifest: Manifest, *, at: float | None = None, chapter: str | None = None) -> float:
    """The playback time to take a screenshot at.

    Parameters
    ----------
    manifest
        The rendered recording.
    at
        A playback time, in seconds (after cuts and speed changes).
    chapter
        A chapter's label. The screenshot is the chapter's last screen, just before the next
        chapter starts (or the end of the recording, for the last chapter). Labels are matched
        exactly first, then ignoring case.

    Returns
    -------
    float
        `at`, the chapter's last moment, or the end of the recording when neither is given.

    Raises
    ------
    SnapError
        If `at` is negative or past the end, or no chapter has that label.
    """
    if at is not None:
        if at < 0:
            raise SnapError(f"--at can't be negative, got {at:g}")
        if at > manifest.duration + 1e-9:
            raise SnapError(
                f"--at {at:g}s is past the end of the recording ({manifest.duration:g}s)"
            )
        return at
    if chapter is not None:
        chapters = sorted(manifest.chapters, key=lambda c: c.time)
        n = next((i for i, c in enumerate(chapters) if c.label == chapter), None)
        if n is None:
            folded = chapter.casefold()
            n = next((i for i, c in enumerate(chapters) if c.label.casefold() == folded), None)
        if n is None:
            labels = ", ".join(repr(c.label) for c in chapters) or "none"
            raise SnapError(f"no chapter is labeled {chapter!r} (the chapters are: {labels})")
        if n + 1 == len(chapters):
            return manifest.duration
        # The last keyframe before the next chapter starts
        end = chapters[n + 1].time
        times = [k.time for k in manifest.keyframes if chapters[n].time <= k.time < end]
        return max(times, default=chapters[n].time)
    return manifest.duration


def frame_at(manifest: Manifest, time: float) -> FrameEntry:
    """The screen showing at a playback time: the last keyframe at or before it."""
    frame = None
    for kf in manifest.keyframes:
        if kf.time > time + 1e-9:
            break
        if kf.frame is not None:
            frame = kf.frame
    if frame is None:
        if not manifest.frames:
            raise SnapError("the recording has no screens to take a screenshot of")
        frame = 0
    return manifest.frames[frame]


def snap_svg(
    manifest: Manifest,
    time: float,
    *,
    dark: bool = False,
    annotations: bool = False,
    font_file: str | Path | None = None,
    cells: tuple[int, int] | None = None,
) -> str:
    """Draw the screen at one moment as a still SVG.

    Parameters
    ----------
    manifest
        A version 2 manifest from `generate_manifest()`.
    time
        The playback time (see `snap_time()`).
    dark
        Draw the dark side of a light/dark theme pair. Ignored when the manifest has a single
        theme.
    annotations
        Draw the annotations showing at that time.
    font_file
        A `.woff2`, `.woff`, `.ttf`, or `.otf` file to embed and use for the terminal text.
    cells
        The terminal's size as `(cols, rows)`, instead of the screen's own size, so screens of
        different sizes can be drawn in one size of window (as a video's frames must be).

    Returns
    -------
    str
        The SVG document.

    Raises
    ------
    ValueError
        If the manifest has no cell grid (it isn't version 2), or the font file's type isn't
        supported.
    """
    screen = manifest.screen
    if screen is None or not manifest.frames:
        raise ValueError("a screenshot needs a version 2 manifest")
    frame = frame_at(manifest, time)

    side = manifest.dark if dark else None
    fg, bg = (side.fg, side.bg) if side else (screen.fg, screen.bg)
    cursor_color = (side.cursor if side else screen.cursor) or fg
    rows_by_id = side.lines if side else manifest.lines

    cell_w = screen.font_size * 0.6
    cell_h = screen.font_size * screen.line_height
    pad = screen.padding
    cols, rows = cells or (frame.size[0] if frame.size else manifest.cols, len(frame.lines))
    term_w = cols * cell_w + pad * 2
    term_h = rows * cell_h + pad * 2
    chapter = _chapter_at(manifest, time)
    # The same title bar as the animated export, so stills match it
    bar_h = _BAR_HEIGHT if manifest.window_chrome != "none" or manifest.chapters else 0.0
    width, height = term_w, bar_h + term_h

    font_family = screen.font_family
    styles = []
    if font_file is not None:
        styles.append(_font_face(Path(font_file)))
        font_family = f'"{_EMBEDDED_FONT}", {font_family}'
    styles.append(_text_styles(font_family, screen.font_size))

    used = sorted({i for i in frame.lines if _has_content(rows_by_id[i])})
    defs = [_row_def(i, rows_by_id[i], cell_w, cell_h) for i in used]

    body = [f'<g transform="translate({pad},{bar_h + pad:.1f})">']
    for row_idx, line_id in enumerate(frame.lines):
        if _has_content(rows_by_id[line_id]):
            body.append(f'<use href="#l{line_id}" y="{row_idx * cell_h:.1f}"/>')
    if frame.cursor is not None:
        body.append(
            f'<rect x="{frame.cursor[1] * cell_w:.1f}" y="{frame.cursor[0] * cell_h:.1f}" '
            f'width="{cell_w:.1f}" height="{cell_h:.1f}" fill="{cursor_color}" opacity="0.7"/>'
        )
    body.append("</g>")

    if annotations:
        for ann in manifest.annotations:
            if ann.time <= time < ann.time + ann.duration:
                box = _annotation(
                    ann.text, ann.position, ann.style, ann.width, term_w, term_h, bar_h, fg, bg
                )
                body.append(box.replace('<g opacity="0" ', "<g ", 1))

    bar = []
    if bar_h:
        bar.append(
            f'<line x1="0" y1="{bar_h:.1f}" x2="{width:.1f}" y2="{bar_h:.1f}" '
            f'stroke="{fg}" stroke-opacity="0.12"/>'
        )
        if manifest.window_chrome == "colorful":
            bar.extend(_dots(["#f38ba8", "#f9e2af", "#a6e3a1"], bar_h, 1.0))
        elif manifest.window_chrome == "minimal":
            bar.extend(_dots([fg] * 3, bar_h, 0.35))
        if chapter:
            bar.append(
                f'<text x="{width / 2:.1f}" y="{bar_h / 2:.1f}" class="ui" font-size="13" '
                f'font-weight="500" text-anchor="middle" dominant-baseline="central" '
                f'fill="{fg}" fill-opacity="0.85">{xml_escape(chapter)}</text>'
            )

    title = manifest.title or "Terminal recording"
    # `xml:space` keeps leading and repeated spaces in rasterizers that ignore `white-space:pre`
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" '
        f'width="{width:.1f}" height="{height:.1f}" xml:space="preserve" role="img" '
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


def _chapter_at(manifest: Manifest, time: float) -> str:
    """The label of the chapter playing at `time`, or "" before the first one."""
    label = ""
    for ch in sorted(manifest.chapters, key=lambda c: c.time):
        if ch.time > time + 1e-9:
            break
        label = ch.label
    return label


def find_rasterizer() -> str | None:
    """The first of `RASTERIZERS` that's installed, as a path."""
    for name in RASTERIZERS:
        path = shutil.which(name)
        if path:
            return path
    return None


def rasterize(
    svg: str, output: str | Path, *, scale: float = 1.0, background: str | None = None
) -> None:
    """Write an SVG document as a PNG file.

    Parameters
    ----------
    svg
        The SVG document.
    output
        The PNG file to write.
    scale
        How many pixels each SVG unit becomes; `2` suits high-density screens.
    background
        A color to fill the transparent parts with (the window's rounded corners).

    Raises
    ------
    SnapError
        If no rasterizer is installed, or the one found fails.
    """
    tool = find_rasterizer()
    if tool is None:
        raise SnapError(
            "PNG output needs rsvg-convert or resvg. Install one (for example "
            "`brew install librsvg`, `apt install librsvg2-bin`, or `cargo install resvg`), "
            "or write an SVG instead"
        )
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "snap.svg"
        source.write_text(svg, encoding="utf-8")
        if Path(tool).name.startswith("rsvg-convert"):
            argv = [tool, "--zoom", f"{scale:g}", "--output", str(output), str(source)]
            fill = ["--background-color", background]
        else:
            argv = [tool, "--zoom", f"{scale:g}", str(source), str(output)]
            fill = ["--background", background]
        if background:
            argv[1:1] = fill
        result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or f"exit status {result.returncode}"
        raise SnapError(f"{Path(tool).name} couldn't make the PNG: {message}")
