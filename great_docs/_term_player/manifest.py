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
        return json.dumps(data, indent=2)


