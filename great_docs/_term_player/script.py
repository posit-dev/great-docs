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
    width: str = "medium"
    row: int | None = None
    col: int | None = None


@dataclass
class SpeedSegment:
    """A speed override for a time range."""

    start: float
    end: float
    speed: float = 1.0


@dataclass
class Snippet:
    """A copyable text snippet associated with a time range."""

    time: float
    duration: float
    text: str = ""
    match: str = ""
    label: str = ""


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
    line_height: float | None = None
    show_cursor: bool = True
    window_chrome: str = "none"
    prompt: str | None = None
    prompt_pattern: str | None = None
    chapters: list[Chapter] = field(default_factory=list)
    cuts: list[Cut] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    speed_map: list[SpeedSegment] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)
    snippets: list[Snippet] = field(default_factory=list)


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
        script.line_height = settings.get("line_height")
        script.show_cursor = settings.get("show_cursor", True)
        script.window_chrome = settings.get("window_chrome", "none")
        if "prompt" in settings:
            script.prompt = str(settings["prompt"]) if settings["prompt"] is not None else None
        if "prompt_pattern" in settings:
            script.prompt_pattern = (
                str(settings["prompt_pattern"]) if settings["prompt_pattern"] is not None else None
            )

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
                    width=ann.get("width", "medium"),
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

    # Snippets (copyable text associated with time ranges)
    for snip in data.get("snippets", []):
        if isinstance(snip, dict) and "at" in snip and ("text" in snip or "match" in snip):
            script.snippets.append(
                Snippet(
                    time=float(snip["at"]),
                    duration=float(snip.get("duration", 5.0)),
                    text=snip.get("text", ""),
                    match=snip.get("match", ""),
                    label=snip.get("label", ""),
                )
            )

    return script


def apply_script(recording: Recording, script: Script) -> Recording:
    """Apply a script overlay to a recording, producing a modified recording.

    This applies:
    - Idle time limiting
    - Cuts (segment removal)
    - Speed map adjustments
    - Global speed multiplier

    Annotations/highlights are not applied to the recording itself —
    they go into the manifest for the player to handle at runtime.

    Parameters
    ----------
    recording
        The original recording.
    script
        The script overlay to apply.

    Returns
    -------
    Recording
        A new Recording with modified timing.
    """
    events = list(recording.events)

    # 1. Apply idle time limit
    idle_limit = script.idle_time_limit or recording.idle_time_limit
    if idle_limit is not None:
        events = _apply_idle_limit(events, idle_limit)

    # 2. Apply cuts
    if script.cuts:
        events = _apply_cuts(events, script.cuts)

    # 3. Apply speed map
    if script.speed_map:
        events = _apply_speed_map(events, script.speed_map)

    # 4. Apply global speed
    if script.speed != 1.0:
        events = [Event(time=e.time / script.speed, code=e.code, data=e.data) for e in events]

    # Build new recording
    new_rec = Recording(
        version=recording.version,
        format=recording.format,
        term=recording.term,
        title=recording.title,
        timestamp=recording.timestamp,
        idle_time_limit=idle_limit,
        events=events,
    )

    return new_rec


def _apply_idle_limit(events: list[Event], limit: float) -> list[Event]:
    """Compress idle periods longer than limit."""
    if not events:
        return events

    result: list[Event] = []
    prev_time = 0.0
    time_offset = 0.0  # Accumulated time removed

    for event in events:
        gap = event.time - prev_time
        if gap > limit:
            time_offset += gap - limit
        new_time = event.time - time_offset
        result.append(Event(time=new_time, code=event.code, data=event.data))
        prev_time = event.time

    return result


def _apply_cuts(events: list[Event], cuts: list[Cut]) -> list[Event]:
    """Remove events within cut ranges and adjust timing."""
    # Sort cuts by start time
    sorted_cuts = sorted(cuts, key=lambda c: c.start)

    result: list[Event] = []
    time_offset = 0.0

    for event in events:
        in_cut = False
        for cut in sorted_cuts:
            if cut.start <= event.time <= cut.end:
                in_cut = True
                break

        if not in_cut:
            # Compute how much time has been cut before this event
            offset = sum(
                min(cut.end, event.time) - cut.start
                for cut in sorted_cuts
                if cut.start < event.time
            )
            new_time = event.time - offset
            result.append(Event(time=max(0.0, new_time), code=event.code, data=event.data))

    return result


def _apply_speed_map(events: list[Event], speed_map: list[SpeedSegment]) -> list[Event]:
    """Apply segment-specific speed adjustments."""
    sorted_segs = sorted(speed_map, key=lambda s: s.start)

    result: list[Event] = []
    for event in events:
        new_time = _remap_time(event.time, sorted_segs)
        result.append(Event(time=new_time, code=event.code, data=event.data))

    return result


def _remap_time(t: float, segments: list[SpeedSegment]) -> float:
    """Remap a single timestamp through speed segments.

    Time within a speed segment is scaled by 1/speed.
    Time outside any segment is unchanged.
    """
    new_t = 0.0
    prev = 0.0

    for seg in segments:
        if t <= seg.start:
            break

        # Time before this segment (at normal speed)
        gap_before = min(t, seg.start) - prev
        new_t += gap_before

        # Time within this segment (scaled)
        time_in_seg = min(t, seg.end) - seg.start
        new_t += time_in_seg / seg.speed

        prev = seg.end

    # Time after last segment
    last_end = segments[-1].end if segments else 0.0
    if t > last_end:
        # Add gap from last segment end to prev accumulation point
        remaining = t - max(prev, last_end)
        new_t += remaining

    return new_t
