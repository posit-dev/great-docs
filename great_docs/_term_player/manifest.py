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


