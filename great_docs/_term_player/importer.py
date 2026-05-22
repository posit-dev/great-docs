"""Importers for asciicast and VHS tape formats."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .parser import Recording, parse_asciicast


def import_asciicast(source: str | Path, output: str | Path) -> Recording:
    """Import an asciicast v2/v3 file and save as .termshow.

    Parameters
    ----------
    source
        Path to .cast file.
    output
        Path to write .termshow file.

    Returns
    -------
    Recording
        The parsed recording.
    """
    recording = parse_asciicast(source)

    # Convert to termshow format and write
    _write_termshow(recording, output)
    return recording


def import_tape(source: str | Path, output: str | Path) -> Recording:
    """Import a VHS .tape file and convert to .termshow.

    Parses the VHS tape DSL and generates synthetic terminal events.
    This produces a scripted recording rather than a real capture.

    Parameters
    ----------
    source
        Path to .tape file.
    output
        Path to write .termshow file.

    Returns
    -------
    Recording
        The generated recording.
    """
    path = Path(source)
    text = path.read_text(encoding="utf-8")

    recording = _parse_tape(text)
    _write_termshow(recording, output)
    return recording


def _parse_tape(text: str) -> Recording:
    """Parse VHS tape DSL into a Recording with synthetic events."""
    from .parser import Event, Recording, TermInfo

    cols = 80
    rows = 24
    typing_speed = 0.05  # seconds per character
    events: list[Event] = []
    current_time = 0.0

    lines = text.strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Parse Set commands
        set_match = re.match(r"Set\s+(\w+)\s+(.+)", line)
        if set_match:
            key, value = set_match.group(1), set_match.group(2).strip().strip('"')
            if key == "Width":
                cols = int(value)
            elif key == "Height":
                rows = int(value)
            elif key == "TypingSpeed":
                typing_speed = _parse_duration(value)
            continue

        # Parse Type command
        type_match = re.match(r"Type(?:@(\S+))?\s+(.+)", line)
        if type_match:
            speed_override = type_match.group(1)
            text_content = type_match.group(2).strip().strip('"').strip("`")
            speed = _parse_duration(speed_override) if speed_override else typing_speed

            for ch in text_content:
                current_time += speed
                events.append(Event(time=current_time, code="o", data=ch))
            continue

        # Parse Sleep command
        sleep_match = re.match(r"Sleep\s+(.+)", line)
        if sleep_match:
            duration = _parse_duration(sleep_match.group(1).strip())
            current_time += duration
            continue

        # Parse Enter
        if re.match(r"Enter(\s+\d+)?", line):
            count_match = re.search(r"\d+", line)
            count = int(count_match.group()) if count_match else 1
            for _ in range(count):
                current_time += 0.05
                events.append(Event(time=current_time, code="o", data="\r\n"))
            continue

        # Parse key commands
        key_match = re.match(r"(Backspace|Tab|Space|Up|Down|Left|Right|Escape)(\s+\d+)?", line)
        if key_match:
            key_name = key_match.group(1)
            count_str = key_match.group(2)
            count = int(count_str.strip()) if count_str else 1
            char_map = {
                "Backspace": "\x08",
                "Tab": "\t",
                "Space": " ",
                "Up": "\x1b[A",
                "Down": "\x1b[B",
                "Right": "\x1b[C",
                "Left": "\x1b[D",
                "Escape": "\x1b",
            }
            char = char_map.get(key_name, "")
            for _ in range(count):
                current_time += 0.05
                events.append(Event(time=current_time, code="o", data=char))
            continue

        # Parse Ctrl+key
        ctrl_match = re.match(r"Ctrl\+(\w)", line)
        if ctrl_match:
            ch = ctrl_match.group(1).upper()
            ctrl_char = chr(ord(ch) - 64)
            current_time += 0.05
            events.append(Event(time=current_time, code="o", data=ctrl_char))
            continue

        # Hide/Show are noted as markers
        if line == "Hide":
            events.append(Event(time=current_time, code="m", data="[hidden]"))
            continue
        if line == "Show":
            events.append(Event(time=current_time, code="m", data="[visible]"))
            continue

    recording = Recording(
        version=1,
        format="termshow",
        term=TermInfo(cols=cols, rows=rows),
        title="",
        events=events,
    )

    return recording


def _parse_duration(s: str) -> float:
    """Parse a VHS duration string (e.g., '500ms', '1s', '2.5')."""
    s = s.strip()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000.0
    elif s.endswith("s"):
        return float(s[:-1])
    else:
        try:
            return float(s)
        except ValueError:
            return 0.1


