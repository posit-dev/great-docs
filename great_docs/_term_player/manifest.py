"""Manifest generator: orchestrates rendering and produces the frame manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .emulator import TerminalEmulator
from .parser import Recording
from .renderer import render_frame
from .script import Annotation, Chapter, Highlight, Script


@dataclass
class KeyframeEntry:
    """A keyframe in the manifest."""

    time: float
    file: str


@dataclass
class DeltaChange:
    """A single cell change in a delta frame."""

    row: int
    col: int
    char: str
    fg: str | None = None
    bg: str | None = None
    bold: bool = False


@dataclass
class DeltaEntry:
    """A delta frame (incremental changes between keyframes)."""

    time: float
    changes: list[DeltaChange] = field(default_factory=list)


@dataclass
class Manifest:
    """The complete manifest describing a rendered termshow recording."""

    version: int = 1
    title: str = ""
    duration: float = 0.0
    cols: int = 80
    rows: int = 24
    theme: str = "default"
    chapters: list[Chapter] = field(default_factory=list)
    keyframes: list[KeyframeEntry] = field(default_factory=list)
    deltas: list[DeltaEntry] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)
    window_chrome: str = "none"

    def to_json(self) -> str:
        """Serialize manifest to JSON string."""
        data = {
            "version": self.version,
            "title": self.title,
            "duration": round(self.duration, 3),
            "term": {"cols": self.cols, "rows": self.rows},
            "theme": self.theme,
            "chapters": [{"time": round(ch.time, 3), "label": ch.label} for ch in self.chapters],
            "keyframes": [{"time": round(kf.time, 3), "file": kf.file} for kf in self.keyframes],
            "deltas": [
                {
                    "time": round(d.time, 3),
                    "changes": [_delta_change_to_dict(c) for c in d.changes],
                }
                for d in self.deltas
            ],
            "annotations": [
                {
                    "time": round(a.time, 3),
                    "duration": round(a.duration, 3),
                    "text": a.text,
                    "position": a.position,
                    "style": a.style,
                }
                for a in self.annotations
            ],
            "highlights": [
                {
                    "time": round(h.time, 3),
                    "duration": round(h.duration, 3),
                    "row": h.row,
                    "col": h.col,
                    "width": h.width,
                    "height": h.height,
                    "style": h.style,
                }
                for h in self.highlights
            ],
        }
        if self.window_chrome != "none":
            data["window_chrome"] = self.window_chrome
        return json.dumps(data, indent=2)


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

    # Set up emulator
    emu = TerminalEmulator(cols=recording.term.cols, rows=recording.term.rows)

    # Determine render settings from script
    theme = recording.term.theme
    font_family = "JetBrains Mono, Fira Code, SF Mono, Menlo, Consolas, monospace"
    show_cursor = True
    window_chrome = "none"

    if script:
        if script.theme:
            theme = script.theme
        if script.font_family:
            font_family = script.font_family
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

    # Determine keyframe times
    keyframe_times = _compute_keyframe_times(recording.duration, keyframe_interval, chapters)

    # Add a keyframe at every output event to guarantee full fidelity
    for event in recording.events:
        if event.code == "o":
            keyframe_times.append(round(event.time, 3))
    keyframe_times = sorted(set(keyframe_times))

    # Process events and capture keyframes + deltas
    keyframes: list[KeyframeEntry] = []
    deltas: list[DeltaEntry] = []

    event_idx = 0
    kf_idx = 0
    prev_state = None

    # Always capture initial state (time 0)
    if 0.0 not in keyframe_times:
        keyframe_times = [0.0] + keyframe_times

    for target_time in sorted(keyframe_times):
        # Feed events up to this keyframe time
        while event_idx < len(recording.events):
            event = recording.events[event_idx]
            if event.time > target_time:
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
        frame_num = len(keyframes)
        filename = f"{prefix}-{frame_num:03d}.svg"

        svg = render_frame(
            state,
            theme,
            font_family=font_family,
            show_cursor=show_cursor,
            window_chrome=window_chrome,
        )

        if out_path:
            (out_path / filename).write_text(svg, encoding="utf-8")

        keyframes.append(KeyframeEntry(time=target_time, file=filename))
        prev_state = state

    # Capture deltas between keyframes (character-level changes)
    # For Phase 1, we use keyframes only; deltas will come in Phase 2
    # This keeps things simple while still providing smooth chapter-based playback

    # Build manifest
    manifest = Manifest(
        version=1,
        title=recording.title,
        duration=recording.duration,
        cols=recording.term.cols,
        rows=recording.term.rows,
        theme=script.theme_name if script and script.theme_name else "default",
        chapters=chapters,
        keyframes=keyframes,
        deltas=deltas,
        annotations=script.annotations if script else [],
        highlights=script.highlights if script else [],
        window_chrome=window_chrome,
    )

    if out_path:
        (out_path / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

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


def _delta_change_to_dict(change: DeltaChange) -> dict:
    """Convert a DeltaChange to a JSON-serializable dict."""
    d: dict = {"row": change.row, "col": change.col, "char": change.char}
    if change.fg:
        d["fg"] = change.fg
    if change.bg:
        d["bg"] = change.bg
    if change.bold:
        d["bold"] = True
    return d
