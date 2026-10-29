"""Manifest generator: orchestrates rendering and produces the frame manifest."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .emulator import ScreenState, TerminalEmulator
from .parser import Recording, Theme
from .renderer import (
    DEFAULT_FONT_SIZE,
    DEFAULT_LINE_HEIGHT,
    DEFAULT_PADDING,
    Line,
    line_model,
    render_svg,
)
from .script import Annotation, Chapter, Highlight, Script, Snippet

MANIFEST_VERSION = 2


@dataclass
class KeyframeEntry:
    """A keyframe in the manifest: the screen shown from `time` onward."""

    time: float
    file: str
    # Index into `Manifest.frames` (v2); identical screens share one frame
    frame: int | None = None


@dataclass
class FrameEntry:
    """A unique screen, stored as indices into `Manifest.lines` (one per row)."""

    lines: list[int]
    cursor: tuple[int, int] | None = None
    # Only set when a resize gave this frame a different size from `Manifest.cols/rows`
    size: tuple[int, int] | None = None


@dataclass
class ScreenSettings:
    """Render settings the player needs to draw frames as SVG."""

    font_family: str
    font_size: int = DEFAULT_FONT_SIZE
    line_height: float = DEFAULT_LINE_HEIGHT
    padding: int = DEFAULT_PADDING
    fg: str = Theme().fg
    bg: str = Theme().bg
    # Only set when the theme has its own cursor color (otherwise it's `fg`)
    cursor: str | None = None


@dataclass
class DarkVariant:
    """The dark side of a light/dark theme pair.

    `lines` runs parallel to `Manifest.lines`: entry *i* is row *i* drawn in
    the dark theme, so frames can index either list.
    """

    fg: str
    bg: str
    cursor: str | None = None
    lines: list[Line] = field(default_factory=list)


@dataclass
class ManifestStats:
    """Size information about a render (not serialized)."""

    keyframes: int = 0
    frames: int = 0
    lines: int = 0
    # Bytes of the manifest, which is all a page inlines
    manifest_bytes: int = 0


@dataclass
class Manifest:
    """The complete manifest describing a rendered termshow recording."""

    version: int = MANIFEST_VERSION
    title: str = ""
    duration: float = 0.0
    cols: int = 80
    rows: int = 24
    theme: str = "default"
    chapters: list[Chapter] = field(default_factory=list)
    keyframes: list[KeyframeEntry] = field(default_factory=list)
    screen: ScreenSettings | None = None
    lines: list[Line] = field(default_factory=list)
    frames: list[FrameEntry] = field(default_factory=list)
    dark: DarkVariant | None = None
    annotations: list[Annotation] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)
    snippets: list[Snippet] = field(default_factory=list)
    window_chrome: str = "none"
    stats: ManifestStats = field(default_factory=ManifestStats)

    def to_json(self, *, files: bool = True, transcript: str = "") -> str:
        """Serialize manifest to a compact JSON string.

        The output is safe to embed in an HTML `<script>` element: `</` is
        written as `<\\/` so terminal text can't close the element early.

        Parameters
        ----------
        files
            Give each keyframe the name of its SVG file. A bundle, which comes
            without the files, leaves them out.
        transcript
            The recording's text as Markdown, added as `transcript` when given.
        """
        data = {
            "version": self.version,
            "title": self.title,
            "duration": round(self.duration, 3),
            "term": {"cols": self.cols, "rows": self.rows},
            "theme": self.theme,
            "chapters": [{"time": round(ch.time, 3), "label": ch.label} for ch in self.chapters],
            "keyframes": [_serialize_keyframe(kf, files) for kf in self.keyframes],
            "annotations": [
                {
                    "time": round(a.time, 3),
                    "duration": round(a.duration, 3),
                    "text": a.text,
                    "position": a.position,
                    "style": a.style,
                    "width": a.width,
                }
                for a in self.annotations
            ],
            "highlights": [self._serialize_highlight(h) for h in self.highlights],
            "snippets": [
                {
                    "time": round(c.time, 3),
                    "duration": round(c.duration, 3),
                    "text": c.text,
                    "match": c.match,
                    "label": c.label,
                }
                for c in self.snippets
            ],
        }
        if self.window_chrome != "none":
            data["window_chrome"] = self.window_chrome
        if self.screen is not None:
            data["screen"] = {
                "font_family": self.screen.font_family,
                "font_size": self.screen.font_size,
                "line_height": self.screen.line_height,
                "padding": self.screen.padding,
                "fg": self.screen.fg,
                "bg": self.screen.bg,
            }
            if self.screen.cursor:
                data["screen"]["cursor"] = self.screen.cursor
            data["lines"] = [_serialize_line(line) for line in self.lines]
            data["frames"] = [_serialize_frame(fr) for fr in self.frames]
            if self.dark is not None:
                dark: dict = {"fg": self.dark.fg, "bg": self.dark.bg}
                if self.dark.cursor:
                    dark["cursor"] = self.dark.cursor
                dark["lines"] = [_serialize_line(line) for line in self.dark.lines]
                data["dark"] = dark
        if transcript:
            data["transcript"] = transcript
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return text.replace("</", "<\\/")

    @staticmethod
    def _serialize_highlight(h: Highlight) -> dict:
        """Serialize a Highlight to a manifest-compatible dict."""
        target: dict = {}
        if h.target.region:
            target["region"] = h.target.region
        if h.target.match:
            target["match"] = h.target.match
            if h.target.group:
                target["group"] = h.target.group
        if h.target.lines:
            target["lines"] = h.target.lines
        if h.target.track_scroll:
            target["track_scroll"] = True

        result: dict = {
            "time": round(h.time, 3),
            "duration": round(h.duration, 3),
            "target": target,
            "style": h.style,
            "color": h.color,
        }
        # Optional badge fields
        if h.badge_text:
            result["badge_text"] = h.badge_text
        if h.badge_icon:
            result["badge_icon"] = h.badge_icon
        # Animation
        if h.fade_in != 0.3:
            result["fade_in"] = round(h.fade_in, 3)
        if h.fade_out != 0.3:
            result["fade_out"] = round(h.fade_out, 3)
        if h.pulse:
            result["pulse"] = True
        return result


def generate_manifest(
    recording: Recording,
    script: Script | None = None,
    *,
    output_dir: str | Path | None = None,
    keyframe_interval: float = 2.0,
    prefix: str = "frame",
) -> Manifest:
    """Generate a manifest and render SVG keyframes from a recording.

    Parameters
    ----------
    recording
        The (optionally script-processed) recording to render.
    script
        Optional script for annotations, chapters, and render settings.
    output_dir
        Directory to write SVG files to. If None, frames are not written to disk.
    keyframe_interval
        Seconds between keyframe snapshots.
    prefix
        Filename prefix for frame SVGs.

    Returns
    -------
    Manifest
        The generated manifest with keyframe/delta information.
    """
    out_path = Path(output_dir) if output_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)
        # Frames are numbered by unique screen, so a re-render can produce
        # fewer files than last time; clear the old ones
        for stale in out_path.glob(f"{prefix}-[0-9][0-9][0-9]*.svg"):
            stale.unlink()

    # Set up emulator
    emu = TerminalEmulator(cols=recording.term.cols, rows=recording.term.rows)

    # Determine render settings from script
    theme = recording.term.theme
    dark_theme: Theme | None = None
    font_family = "JetBrains Mono, Fira Code, SF Mono, Menlo, Consolas, monospace"
    line_height: float | None = None
    show_cursor = True
    window_chrome = "none"

    if script:
        if script.theme:
            theme = script.theme
            dark_theme = script.dark_theme
        if script.font_family:
            font_family = script.font_family
        if script.line_height is not None:
            line_height = script.line_height
        show_cursor = script.show_cursor
        window_chrome = script.window_chrome

    # Collect chapters
    chapters: list[Chapter] = []
    if script and script.chapters:
        chapters = list(script.chapters)
    else:
        # Use markers from recording as chapters
        for event in recording.events:
            if event.code == "m":
                chapters.append(Chapter(time=event.time, label=event.data))

    # Detect prompt prefix for substitution (if prompt setting is configured)
    prompt_prefix: str | None = None
    prompt_replacement: str | None = None
    prompt_pattern: str | None = None

    if script and script.prompt:
        prompt_replacement = script.prompt
        prompt_pattern = script.prompt_pattern
        # Run a pre-pass to detect the prompt from input events
        prompt_prefix = _detect_prompt_prefix(recording)

    screen = ScreenSettings(
        font_family=font_family,
        line_height=line_height if line_height is not None else DEFAULT_LINE_HEIGHT,
        fg=theme.fg,
        bg=theme.bg,
        cursor=theme.cursor,
    )
    # With a light/dark pair, every row is also drawn in the dark theme
    dark = (
        DarkVariant(fg=dark_theme.fg, bg=dark_theme.bg, cursor=dark_theme.cursor)
        if dark_theme
        else None
    )

    # Determine keyframe times
    keyframe_times = _compute_keyframe_times(recording.duration, keyframe_interval, chapters)

    # Add a keyframe at every output event to guarantee full fidelity
    for event in recording.events:
        if event.code == "o":
            keyframe_times.append(round(event.time, 3))
    keyframe_times = sorted(set(keyframe_times))

    # Process events and capture keyframes. Rows and whole screens are
    # deduplicated: each unique row becomes one entry in `lines`, each unique
    # screen one entry in `frames` (and one SVG file), and keyframes point at
    # frames by index. With a theme pair, rows are deduplicated by their
    # (light, dark) pair, since two rows can look the same in one theme only.
    keyframes: list[KeyframeEntry] = []
    lines: list[Line] = []
    line_ids: dict[Line | tuple[Line, Line], int] = {}
    frames: list[FrameEntry] = []
    frame_ids: dict[tuple, int] = {}
    stats = ManifestStats()

    event_idx = 0

    # Always capture initial state (time 0)
    if 0.0 not in keyframe_times:  # pragma: no cover
        keyframe_times = [0.0] + keyframe_times

    for target_time in sorted(keyframe_times):
        # Feed events up to this keyframe time
        while event_idx < len(recording.events):
            event = recording.events[event_idx]
            # Keyframe times are rounded, so compare at the same precision (accumulated
            # delays like 1.1400000000000001 must still count as at-or-before 1.14)
            if round(event.time, 3) > target_time:
                break

            if event.code == "o":
                emu.feed(event.data)
            elif event.code == "r":
                parts = event.data.split("x")
                if len(parts) == 2:
                    try:
                        emu.resize(int(parts[0]), int(parts[1]))
                    except ValueError:
                        pass

            event_idx += 1

        # Capture keyframe
        state = emu.screen

        # Apply prompt substitution if configured
        if prompt_replacement:
            if prompt_prefix:
                state = _apply_prompt_substitution(
                    state, prompt_prefix, prompt_replacement, prompt_pattern
                )
            elif prompt_pattern:
                state = _apply_prompt_pattern_substitution(
                    state, prompt_pattern, prompt_replacement
                )

        row_ids: list[int] = []
        for r in range(state.rows):
            line = line_model(state.cells[r], theme)
            if dark is not None:
                dark_line = line_model(state.cells[r], dark_theme)
                key = (line, dark_line)
            else:
                key = line
            if key not in line_ids:
                line_ids[key] = len(lines)
                lines.append(line)
                if dark is not None:
                    dark.lines.append(dark_line)
            row_ids.append(line_ids[key])
        cursor = (
            (state.cursor_row, state.cursor_col) if show_cursor and state.cursor_visible else None
        )
        size = (state.cols, state.rows)
        frame_key = (size, tuple(row_ids), cursor)

        frame_idx = frame_ids.get(frame_key)
        if frame_idx is None:
            frame_idx = len(frames)
            frame_ids[frame_key] = frame_idx
            frames.append(
                FrameEntry(
                    lines=row_ids,
                    cursor=cursor,
                    size=None if size == (recording.term.cols, recording.term.rows) else size,
                )
            )
            svg = render_svg(
                [lines[i] for i in row_ids],
                cols=state.cols,
                cursor=cursor,
                theme=theme,
                font_family=font_family,
                line_height=screen.line_height,
            )
            if out_path:
                (out_path / f"{prefix}-{frame_idx:03d}.svg").write_text(svg, encoding="utf-8")

        keyframes.append(
            KeyframeEntry(time=target_time, file=f"{prefix}-{frame_idx:03d}.svg", frame=frame_idx)
        )

    # Build manifest
    manifest = Manifest(
        version=MANIFEST_VERSION,
        title=recording.title,
        duration=recording.duration,
        cols=recording.term.cols,
        rows=recording.term.rows,
        theme=script.theme_name if script and script.theme_name else "default",
        chapters=chapters,
        keyframes=keyframes,
        screen=screen,
        lines=lines,
        frames=frames,
        dark=dark,
        annotations=script.annotations if script else [],
        highlights=script.highlights if script else [],
        snippets=script.snippets if script else [],
        window_chrome=window_chrome,
        stats=stats,
    )

    manifest_json = manifest.to_json()
    stats.keyframes = len(keyframes)
    stats.frames = len(frames)
    stats.lines = len(lines)
    stats.manifest_bytes = len(manifest_json.encode("utf-8"))

    if out_path:
        (out_path / "manifest.json").write_text(manifest_json, encoding="utf-8")

    return manifest


def _compute_keyframe_times(
    duration: float, interval: float, chapters: list[Chapter]
) -> list[float]:
    """Compute the set of times to capture keyframes.

    Includes:
    - Regular intervals
    - Chapter boundaries
    """
    times: set[float] = set()

    # Regular intervals
    t = 0.0
    while t <= duration:
        times.add(round(t, 3))
        t += interval

    # Chapter boundaries
    for ch in chapters:
        times.add(round(ch.time, 3))

    return sorted(times)


def _serialize_keyframe(kf: KeyframeEntry, files: bool = True) -> dict:
    d: dict = {"time": round(kf.time, 3)}
    if files:
        d["file"] = kf.file
    if kf.frame is not None:
        d["frame"] = kf.frame
    return d


def _serialize_line(line: Line) -> list:
    """Serialize a row as `[bg_spans, text_spans]`.

    Background spans are `[col, length, color]`; text spans are
    `[col, text, color]`, with a fourth CSS-classes item only when non-empty.
    """
    bg_spans, text_spans = line
    return [
        [list(span) for span in bg_spans],
        [
            [col, text, color, cls] if cls else [col, text, color]
            for col, text, color, cls in text_spans
        ],
    ]


def _serialize_frame(frame: FrameEntry) -> dict:
    d: dict = {"lines": frame.lines}
    if frame.cursor is not None:
        d["cursor"] = list(frame.cursor)
    if frame.size is not None:
        d["size"] = list(frame.size)
    return d


# ---------------------------------------------------------------------------
# Prompt substitution
# ---------------------------------------------------------------------------


def _detect_prompt_prefix(recording: Recording) -> str | None:
    """Detect the prompt prefix string by correlating input events with screen state.

    Runs through the recording events with an emulator. At each input ("i") event,
    captures the text on the cursor row from column 0 up to the cursor position.
    Returns the most common prompt prefix found, or None if no input events exist.
    """
    emu = TerminalEmulator(cols=recording.term.cols, rows=recording.term.rows)
    prompt_texts: list[str] = []

    for event in recording.events:
        if event.code == "o":
            emu.feed(event.data)
        elif event.code == "r":
            parts = event.data.split("x")
            if len(parts) == 2:
                try:
                    emu.resize(int(parts[0]), int(parts[1]))
                except ValueError:
                    pass
        elif event.code == "i":
            screen = emu.screen
            row = screen.cursor_row
            col = screen.cursor_col
            if col > 0:
                # Extract text on this row up to cursor position
                text = "".join(screen.cells[row][c].char for c in range(col))
                prompt_texts.append(text)

    if not prompt_texts:
        return None

    # Find the most common prompt prefix
    from collections import Counter

    counts = Counter(prompt_texts)
    most_common = counts.most_common(1)[0][0]
    return most_common


# Common prompt characters, ordered by specificity
_PROMPT_CHARS = ("❯", "➜", "→", "▶", "⟩", "λ", "%", "$", ">", "#")


def _find_prompt_char_in_prefix(prefix: str) -> tuple[int, str] | None:
    """Find the last prompt character in a detected prefix string.

    Returns (col_index, char) or None if no known prompt char is found.
    """
    # Search backwards for the last known prompt char
    for i in range(len(prefix) - 1, -1, -1):
        if prefix[i] in _PROMPT_CHARS:
            return (i, prefix[i])
    return None


def _apply_prompt_substitution(
    state: ScreenState,
    prompt_prefix: str,
    replacement: str,
    prompt_pattern: str | None = None,
) -> ScreenState:
    """Apply prompt character substitution to a screen state.

    Finds rows that start with the detected prompt prefix and replaces the
    prompt character with the configured replacement string.

    Parameters
    ----------
    state
        The terminal screen state to modify.
    prompt_prefix
        The detected prompt prefix (e.g., "$ " or "user@host:~ $ ").
    replacement
        The string to substitute for the prompt character.
    prompt_pattern
        Optional regex pattern for fallback prompt detection (used when
        no input events were available to detect the prefix).

    Returns
    -------
    ScreenState
        A copy of the state with prompt characters substituted.
    """
    # Find the prompt character position within the prefix
    char_info = _find_prompt_char_in_prefix(prompt_prefix)
    if char_info is None:
        return state

    prompt_col, original_char = char_info

    # Make a copy so we don't mutate the original
    new_state = state.copy()

    for row_idx in range(new_state.rows):
        # Extract the row text up to the prompt prefix length
        row_text = "".join(
            new_state.cells[row_idx][c].char for c in range(min(len(prompt_prefix), new_state.cols))
        )

        # Check if this row starts with the detected prompt prefix
        if row_text == prompt_prefix:
            # Substitute the prompt character cell
            new_state.cells[row_idx][prompt_col].char = replacement

    return new_state


def _apply_prompt_pattern_substitution(
    state: ScreenState,
    pattern: str,
    replacement: str,
) -> ScreenState:
    """Apply prompt substitution using a regex pattern (fallback mode).

    Used when no input events are available to detect prompts structurally.
    The pattern should match the prompt portion at the start of a line.

    Parameters
    ----------
    state
        The terminal screen state to modify.
    pattern
        Regex pattern that matches the prompt at line start. The last
        character of the match is replaced.
    replacement
        The string to substitute for the prompt character.

    Returns
    -------
    ScreenState
        A copy of the state with prompt characters substituted.
    """
    try:
        regex = re.compile(pattern)
    except re.error:
        return state

    new_state = state.copy()

    for row_idx in range(new_state.rows):
        # Extract full row text
        row_text = "".join(new_state.cells[row_idx][c].char for c in range(new_state.cols))

        m = regex.match(row_text)
        if m:
            # Find the prompt char — last non-space char in the match
            matched = m.group(0)
            for i in range(len(matched) - 1, -1, -1):  # pragma: no branch
                if matched[i].strip():
                    new_state.cells[row_idx][i].char = replacement
                    break

    return new_state
