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


