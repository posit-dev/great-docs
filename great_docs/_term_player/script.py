"""Script processor: applies .termshow.yml edits to recordings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .parser import Event, Recording, Theme


@dataclass
class Chapter:
    """A labeled chapter/cutpoint in the recording timeline."""

    time: float
    label: str


@dataclass
class Cut:
    """A segment to remove from playback."""

    start: float
    end: float
    type: str = "jump"  # "jump", "ellipsis"


@dataclass
class Annotation:
    """A floating annotation overlay."""

    time: float
    duration: float
    text: str
    position: str = "bottom-right"
    style: str = "callout"
    row: int | None = None
    col: int | None = None


@dataclass
class SpeedSegment:
    """A speed override for a time range."""

    start: float
    end: float
    speed: float = 1.0


@dataclass
class Highlight:
    """A highlighted region of the terminal."""

    time: float
    duration: float
    row: int
    col: int
    width: int
    height: int
    style: str = "box"  # "box", "underline", "glow"


@dataclass
class Script:
    """Parsed .termshow.yml script overlay."""

    source: str = ""
    idle_time_limit: float | None = None
    speed: float = 1.0
    theme_name: str | None = None
    theme: Theme | None = None
    font_family: str | None = None
    show_cursor: bool = True
    window_chrome: str = "none"
    chapters: list[Chapter] = field(default_factory=list)
    cuts: list[Cut] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    speed_map: list[SpeedSegment] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)


def load_script(path: str | Path) -> Script:
    """Load a .termshow.yml script file.

    Parameters
    ----------
    path
        Path to the YAML script file.

    Returns
    -------
    Script
        Parsed script object.
    """
    import yaml

    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return Script()

    return _parse_script_data(data)


