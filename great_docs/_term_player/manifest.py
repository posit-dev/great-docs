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


