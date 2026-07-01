"""Voice synthesis (TTS) for showreel narration.

A small engine abstraction so reproducibility vs. quality is a config choice.
P0 ships two engines:

* ``piper`` — local, offline, free, reproducible (the default). Requires the
  ``piper`` binary on PATH (``pip install piper-tts`` provides it).
* ``silent`` — no audio; estimates a sensible duration from word count so the
  pipeline (timing, captions, player) works even with no TTS installed.

Cloud engines (openai / elevenlabs / azure) are declared in ``SHOWREEL_PLAN.md``
and slot in here at P2.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .spec import VoiceSpec

# Rough speaking rate used to estimate durations and distribute caption words.
WORDS_PER_SEC = 2.7
MIN_SCENE_SECONDS = 1.2


@dataclass
class Synthesis:
    """Result of synthesizing one narration line."""

    duration: float
    words: list[tuple[str, float, float]] = field(default_factory=list)  # (word, start, end)
    audio_path: Path | None = None


def _even_word_timings(text: str, duration: float) -> list[tuple[str, float, float]]:
    """Distribute words evenly across ``duration`` (P0 caption timing)."""
    words = text.split()
    if not words:
        return []
    step = duration / len(words)
    return [(w, round(i * step, 3), round((i + 1) * step, 3)) for i, w in enumerate(words)]


def estimate_duration(text: str) -> float:
    n = len(text.split())
    return max(MIN_SCENE_SECONDS, round(n / WORDS_PER_SEC, 3)) if n else MIN_SCENE_SECONDS


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return round(frames / float(rate), 3) if rate else 0.0


class VoiceEngine(Protocol):
    name: str

    def available(self) -> bool: ...

    def synthesize(self, text: str, voice: VoiceSpec, out_path: Path) -> Synthesis: ...


class SilentEngine:
    """Produces no audio; estimates duration and caption timing from text."""

    name = "silent"

    def available(self) -> bool:
        return True

    def synthesize(self, text: str, voice: VoiceSpec, out_path: Path) -> Synthesis:
        dur = estimate_duration(text)
        return Synthesis(duration=dur, words=_even_word_timings(text, dur), audio_path=None)


class PiperEngine:
    """Local Piper TTS via the ``piper`` CLI."""

    name = "piper"

    def available(self) -> bool:
        return shutil.which("piper") is not None

    def synthesize(self, text: str, voice: VoiceSpec, out_path: Path) -> Synthesis:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["piper", "--model", voice.name, "--output_file", str(out_path)]
        try:
            subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:  # pragma: no cover
            raise VoiceError(f"piper synthesis failed: {exc}") from exc

        duration = _wav_duration(out_path) if out_path.exists() else estimate_duration(text)
        return Synthesis(
            duration=duration,
            words=_even_word_timings(text, duration),
            audio_path=out_path,
        )


class VoiceError(RuntimeError):
    """Raised when a voice engine fails."""


_ENGINES: dict[str, type] = {
    "piper": PiperEngine,
    "silent": SilentEngine,
}


def get_engine(name: str, *, fallback: bool = True) -> VoiceEngine:
    """Resolve an engine by name, falling back to ``silent`` when unavailable."""
    engine_cls = _ENGINES.get(name, _ENGINES.get("piper"))
    engine = engine_cls()
    if engine.available():
        return engine
    if fallback:
        return SilentEngine()
    raise VoiceError(f"Voice engine {name!r} is not available")


def _cache_key(text: str, engine: str, voice: VoiceSpec) -> str:
    raw = f"{engine}|{voice.name}|{voice.rate}|{voice.pitch}|{voice.seed}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def synthesize_line(
    engine: VoiceEngine,
    text: str,
    voice: VoiceSpec,
    audio_dir: Path,
    *,
    scene_id: str,
) -> Synthesis:
    """Synthesize one line with content-hash caching.

    Re-uses an existing audio file when ``(text, engine, voice)`` is unchanged,
    so rebuilds skip slow/costly synthesis.
    """
    if not text.strip():
        return Synthesis(duration=MIN_SCENE_SECONDS)

    key = _cache_key(text, engine.name, voice)
    out_path = audio_dir / f"{scene_id}.{key}.wav"

    if out_path.exists():
        dur = _wav_duration(out_path)
        return Synthesis(duration=dur, words=_even_word_timings(text, dur), audio_path=out_path)

    return engine.synthesize(text, voice, out_path)
