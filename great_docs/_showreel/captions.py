"""Caption (WebVTT) generation for showreel narration.

P0 emits one cue per scene spanning its time range. Word-level/karaoke cues
(using the per-scene word timings already computed by the voice engine) are a
straightforward P3 upgrade.
"""

from __future__ import annotations

from .spec import Scene


def _ts(seconds: float) -> str:
    """Format seconds as a WebVTT timestamp (HH:MM:SS.mmm)."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def build_vtt(scenes: list[Scene]) -> str:
    """Build a WebVTT document from scenes that have narration + captions on."""
    lines = ["WEBVTT", ""]
    n = 0
    for sc in scenes:
        if not sc.captions or not sc.say.strip():
            continue
        n += 1
        lines.append(str(n))
        lines.append(f"{_ts(sc.start)} --> {_ts(sc.end)}")
        lines.append(sc.say.strip())
        lines.append("")
    return "\n".join(lines)
