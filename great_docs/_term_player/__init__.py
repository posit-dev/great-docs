"""Terminal Player: record, render, and play terminal sessions as SVG sequences."""

from __future__ import annotations

from .emulator import TerminalEmulator
from .manifest import Manifest, generate_manifest
from .parser import Recording, parse_asciicast, parse_termshow
from .renderer import render_frame, render_frames
from .script import Script, apply_script

__all__ = [
    "Manifest",
    "Recording",
    "Script",
    "TerminalEmulator",
    "apply_script",
    "generate_manifest",
    "parse_asciicast",
    "parse_termshow",
    "render_frame",
    "render_frames",
]
