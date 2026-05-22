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


