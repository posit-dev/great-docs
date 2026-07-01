"""Synthesized UI sound effects for showreel transitions and cues.

SFX are generated with ffmpeg's audio-synthesis filters at build time and
cached in the bundle — no bundled sound files, no licensing, fully reproducible
and offline (matching the rest of showreel). Each recipe is a self-contained
ffmpeg filtergraph producing a short ``[a]`` stream.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# name -> ffmpeg filter_complex graph producing a labeled [a] output.
SFX_RECIPES: dict[str, str] = {
    # A soft filtered-noise transition swell.
    "whoosh": (
        "anoisesrc=d=0.42:c=pink:a=0.7,highpass=f=260,lowpass=f=3600,"
        "afade=t=in:d=0.09,afade=t=out:st=0.18:d=0.24,volume=0.7[a]"
    ),
    # A longer, darker transition.
    "swoosh": (
        "anoisesrc=d=0.6:c=brown:a=0.6,highpass=f=170,lowpass=f=2400,"
        "afade=t=in:d=0.14,afade=t=out:st=0.28:d=0.32,volume=0.8[a]"
    ),
    # A crisp UI click.
    "click": "sine=f=2100:d=0.035,afade=t=out:d=0.032,volume=0.5[a]",
    # An even shorter tick.
    "tick": "sine=f=1500:d=0.02,afade=t=out:d=0.018,volume=0.4[a]",
    # A rounded pop.
    "pop": "sine=f=520:d=0.09,afade=t=out:st=0.008:d=0.082,volume=0.7[a]",
    # A pleasant confirmation chime (two tones).
    "ding": (
        "sine=f=880:d=0.55[t1];sine=f=1320:d=0.55[t2];"
        "[t1][t2]amix=inputs=2,afade=t=out:st=0.06:d=0.48,volume=0.5[a]"
    ),
}

NONE = {"", "none", "off"}


def available_sfx() -> list[str]:
    return sorted(SFX_RECIPES)


def synthesize_sfx(name: str, out_path: Path) -> Path:
    """Render a named SFX to a wav via ffmpeg (idempotent: skips if present)."""
    if name not in SFX_RECIPES:
        raise ValueError(f"unknown sfx {name!r}; choices: {', '.join(available_sfx())}")
    if out_path.exists():
        return out_path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH (required to synthesize SFX)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-filter_complex", SFX_RECIPES[name],
        "-map", "[a]", "-ar", "44100", "-ac", "1",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError("SFX synthesis failed:\n" + proc.stderr.decode("utf-8", "replace")[-800:])
    return out_path
