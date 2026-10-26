"""In-terminal playback of termshow recordings (for quick review)."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import TextIO

from .parser import Recording

# Reset attributes and make sure the cursor is visible when playback ends
_RESET = "\x1b[0m\x1b[?25h"


def play_recording(
    recording: Recording,
    *,
    speed: float = 1.0,
    out: TextIO | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Replay a recording's output events to a terminal stream.

    Cuts and speed changes should already be applied (via `apply_script`). Only
    output (`"o"`) events are written; input, markers, and other event types are
    skipped. Terminal resizes are not replayed.

    Parameters
    ----------
    recording
        The recording to play.
    speed
        Playback speed multiplier (e.g., `2.0` plays twice as fast).
    out
        Stream to write to (defaults to `sys.stdout`).
    sleep
        Sleep function (injectable for tests).

    Returns
    -------
    float
        The playback duration in recording seconds (before the speed multiplier).
    """
    if speed <= 0:
        raise ValueError("speed must be greater than 0")

    stream = out if out is not None else sys.stdout
    elapsed = 0.0

    try:
        for event in recording.events:
            if event.code != "o":
                continue
            delay = (event.time - elapsed) / speed
            if delay > 0:
                sleep(delay)
            elapsed = max(elapsed, event.time)
            stream.write(event.data)
            stream.flush()
    finally:
        stream.write(_RESET)
        stream.flush()

    return elapsed
