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

