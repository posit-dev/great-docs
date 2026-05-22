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


@dataclass
class Recording:
    """A parsed terminal recording."""

    version: int = 1
    format: str = "termshow"
    term: TermInfo = field(default_factory=TermInfo)
    title: str = ""
    timestamp: int | None = None
    idle_time_limit: float | None = None
    events: list[Event] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Total duration in seconds."""
        if not self.events:
            return 0.0
        return self.events[-1].time


def parse_termshow(source: str | Path) -> Recording:
    """Parse a .termshow file into a Recording.

    The format is newline-delimited JSON:
    - Line 1: header object
    - Lines 2+: event arrays [interval, code, data]

    Intervals are relative (seconds since previous event).
    """
    path = Path(source)
    text = path.read_text(encoding="utf-8")
    return parse_termshow_str(text)


def parse_termshow_str(text: str) -> Recording:
    """Parse termshow-format text into a Recording."""
    lines = [
        line
        for line in text.strip().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not lines:
        return Recording()

    # Parse header
    header = json.loads(lines[0])
    rec = _header_to_recording(header)

    # Parse events (relative intervals → absolute times)
    abs_time = 0.0
    for line in lines[1:]:
        arr = json.loads(line)
        if not isinstance(arr, list) or len(arr) < 3:
            continue
        interval, code, data = arr[0], arr[1], arr[2]
        abs_time += float(interval)
        rec.events.append(Event(time=abs_time, code=str(code), data=str(data)))

    return rec


