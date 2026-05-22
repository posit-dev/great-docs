"""Parser for .termshow and asciicast v2/v3 recording formats."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Theme:
    """Terminal color theme."""

    fg: str = "#d0d0d0"
    bg: str = "#1e1e2e"
    palette: list[str] = field(
        default_factory=lambda: [
            "#45475a",
            "#f38ba8",
            "#a6e3a1",
            "#f9e2af",
            "#89b4fa",
            "#cba6f7",
            "#94e2d5",
            "#bac2de",
            "#585b70",
            "#f38ba8",
            "#a6e3a1",
            "#f9e2af",
            "#89b4fa",
            "#cba6f7",
            "#94e2d5",
            "#a6adc8",
        ]
    )


@dataclass
class TermInfo:
    """Terminal dimensions and type information."""

    cols: int = 80
    rows: int = 24
    type: str = "xterm-256color"
    theme: Theme = field(default_factory=Theme)


@dataclass
class Event:
    """A single recording event."""

    time: float  # Absolute time in seconds from start
    code: str  # "o", "i", "m", "r", "a", "x"
    data: str  # Event-specific payload


