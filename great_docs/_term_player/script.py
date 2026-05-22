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


def _parse_script_data(data: dict[str, Any]) -> Script:
    """Parse script data from a dictionary."""
    script = Script()

    script.source = data.get("source", "")

    # Settings
    settings = data.get("settings", {})
    if isinstance(settings, dict):
        script.idle_time_limit = settings.get("idle_time_limit")
        script.speed = settings.get("speed", 1.0)
        script.theme_name = settings.get("theme")
        script.font_family = settings.get("font_family")
        script.show_cursor = settings.get("show_cursor", True)
        script.window_chrome = settings.get("window_chrome", "none")

    # Chapters
    for ch in data.get("chapters", []):
        if isinstance(ch, dict) and "at" in ch:
            script.chapters.append(
                Chapter(
                    time=float(ch["at"]),
                    label=ch.get("label", ""),
                )
            )

    # Cuts
    for cut in data.get("cuts", []):
        if isinstance(cut, dict) and "from" in cut and "to" in cut:
            script.cuts.append(
                Cut(
                    start=float(cut["from"]),
                    end=float(cut["to"]),
                    type=cut.get("type", "jump"),
                )
            )

    # Annotations
    for ann in data.get("annotations", []):
        if isinstance(ann, dict) and "at" in ann:
            script.annotations.append(
                Annotation(
                    time=float(ann["at"]),
                    duration=float(ann.get("duration", 3.0)),
                    text=ann.get("text", ""),
                    position=ann.get("position", "bottom-right"),
                    style=ann.get("style", "callout"),
                    row=ann.get("row"),
                    col=ann.get("col"),
                )
            )

    # Speed map
    for seg in data.get("speed_map", []):
        if isinstance(seg, dict) and "from" in seg and "to" in seg:
            script.speed_map.append(
                SpeedSegment(
                    start=float(seg["from"]),
                    end=float(seg["to"]),
                    speed=float(seg.get("speed", 1.0)),
                )
            )

    # Highlights
    for hl in data.get("highlights", []):
        if isinstance(hl, dict) and "at" in hl and "region" in hl:
            region = hl["region"]
            script.highlights.append(
                Highlight(
                    time=float(hl["at"]),
                    duration=float(hl.get("duration", 2.0)),
                    row=int(region.get("row", 0)),
                    col=int(region.get("col", 0)),
                    width=int(region.get("width", 10)),
                    height=int(region.get("height", 1)),
                    style=hl.get("style", "box"),
                )
            )

    return script


