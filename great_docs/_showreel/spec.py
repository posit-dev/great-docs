"""Showreel spec: parse and validate ``name.showreel.yml`` files.

A showreel is an ordered list of *scenes*, each pairing one visual source with
one narration. This module covers the **P0** scene types rendered entirely by
the player (no external capture): ``title``, ``card``, and ``image``. Other
types declared in ``SHOWREEL_PLAN.md`` (``web``, ``notebook``, ``code``, ...)
parse successfully but render as a labeled placeholder card until their capture
backends land (P1+).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Scene types the player can render on its own (no external capture).
SUPPORTED_P0_TYPES = frozenset({"title", "card", "image", "code"})
# Types that are valid in the spec but not yet renderable; shown as placeholders.
DEFERRED_TYPES = frozenset({"table", "chart", "video", "termshow"})


@dataclass
class VoiceSpec:
    """Voice (TTS) configuration, global or per-scene."""

    engine: str = "piper"
    name: str = "en_US-amy-medium"
    rate: float = 1.0
    pitch: float = 0.0
    seed: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], base: VoiceSpec | None = None) -> VoiceSpec:
        base = base or cls()
        return cls(
            engine=str(data.get("engine", base.engine)),
            name=str(data.get("name", base.name)),
            rate=float(data.get("rate", base.rate)),
            pitch=float(data.get("pitch", base.pitch)),
            seed=data.get("seed", base.seed),
        )


@dataclass
class Motion:
    """A camera move applied over a scene's duration (player-side, scrub-accurate)."""

    type: str = "none"  # none | ken_burns | zoom | pan
    zoom: float = 1.06
    start: str = "center"  # corresponds to YAML `from`
    end: str = "center"  # corresponds to YAML `to`

    @classmethod
    def from_value(cls, value: Any) -> Motion:
        if not isinstance(value, dict):
            return cls()
        return cls(
            type=str(value.get("type", "none")),
            zoom=float(value.get("zoom", 1.06)),
            start=str(value.get("from", "center")),
            end=str(value.get("to", "center")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "zoom": round(self.zoom, 4), "from": self.start, "to": self.end}


@dataclass
class Overlay:
    """A time-ranged visual overlay on a scene (in normalized stage coords)."""

    at: float  # seconds relative to the scene start
    duration: float
    type: str = "box"  # box | spotlight | label | callout
    rect: list[float] = field(default_factory=lambda: [0.3, 0.3, 0.4, 0.2])  # x,y,w,h in 0..1
    text: str = ""
    color: str = "#f1fa8c"
    fade: float = 0.3


@dataclass
class CursorKey:
    """A waypoint for the synthetic cursor (normalized stage coords)."""

    at: float  # seconds relative to the scene start
    x: float
    y: float
    click: bool = False


@dataclass
class CodeStep:
    """One state of a ``code`` scene (magic-move morphs between consecutive steps)."""

    code: str
    focus: list[int] = field(default_factory=list)  # 1-based lines to highlight
    typing: bool = False  # reveal this step with a typing wipe
    html: str = ""  # syntax-highlighted HTML, filled at build time


@dataclass
class Scene:
    """A single scene: one visual + one narration."""

    id: str
    type: str
    say: str = ""  # resolved literal narration text
    say_prompt: str = ""  # AI directive (recorded in P0, generated in P5)
    duration: float | None = None  # None => auto (derived from narration)
    lead_in: float = 0.0  # dead-air seconds before narration begins (Keynote's "time before")
    transition: str = "crossfade"
    transition_duration: float = 0.5
    captions: bool = True
    motion: Motion = field(default_factory=Motion)
    voice: VoiceSpec | None = None

    # Type-specific content (title/card)
    title: str = ""
    subtitle: str = ""
    body: str = ""
    cta: str = ""
    # image
    src: str = ""
    # code
    language: str = "python"
    code_steps: list[CodeStep] = field(default_factory=list)
    # sound-effect cues: [{at, sound, gain_db}]
    sfx: list[dict[str, Any]] = field(default_factory=list)
    # web (captured via nokap)
    url: str = ""
    viewport: dict[str, Any] = field(default_factory=dict)  # {width, height, scale}
    steps: list[dict[str, Any]] = field(default_factory=list)
    cursor_mode: str = ""  # "synthetic" auto-generates a cursor path during capture
    # notebook (executed + captured)
    notebook: str = ""
    runtime: str = "marimo"  # marimo | jupyter
    capture: dict[str, Any] = field(default_factory=dict)  # {mode, settle_ms}
    # captured/produced keyframes (web, notebook): [{file, label}]
    keyframes: list[dict[str, Any]] = field(default_factory=list)
    # overlays + synthetic cursor
    overlays: list[Overlay] = field(default_factory=list)
    cursor: list[CursorKey] = field(default_factory=list)

    # Computed at build time
    start: float = 0.0
    end: float = 0.0
    audio: str | None = None  # relative path to synthesized audio, if any
    words: list[tuple[str, float, float]] = field(default_factory=list)  # karaoke timings
    failed: bool = False  # capture failed at build time -> render a placeholder

    @property
    def is_deferred(self) -> bool:
        return self.type in DEFERRED_TYPES or self.failed


@dataclass
class Showreel:
    """A parsed showreel spec."""

    title: str = ""
    description: str = ""
    aspect: str = "16:9"
    resolution: str = "1920x1080"
    fps: int = 30
    theme: str = "auto"
    brand: dict[str, Any] = field(default_factory=dict)
    voice: VoiceSpec = field(default_factory=VoiceSpec)
    music: dict[str, Any] | None = None
    sfx: dict[str, Any] = field(default_factory=dict)
    scenes: list[Scene] = field(default_factory=list)
    duration: float = 0.0
    source_path: Path | None = None


class ShowreelSpecError(ValueError):
    """Raised when a showreel spec is malformed."""


def _parse_say(value: Any) -> tuple[str, str]:
    """Return ``(literal_text, ai_prompt)`` from a scene's ``say`` value."""
    if value is None:
        return "", ""
    if isinstance(value, str):
        return value.strip(), ""
    if isinstance(value, dict):
        return str(value.get("text", "")).strip(), str(value.get("prompt", "")).strip()
    return str(value).strip(), ""


def _parse_scene(raw: dict[str, Any], index: int, defaults: dict[str, Any]) -> Scene:
    if not isinstance(raw, dict):
        raise ShowreelSpecError(f"Scene #{index} must be a mapping, got {type(raw).__name__}")

    stype = str(raw.get("type", "")).strip()
    if not stype:
        raise ShowreelSpecError(f"Scene #{index} is missing a `type`")
    sid = str(raw.get("id") or f"scene-{index:02d}")

    say, say_prompt = _parse_say(raw.get("say"))

    # Text scenes (title/card) stay centered by default: a global pan/zoom
    # default would drift the text off-center by the final frame. Image and
    # capture scenes inherit the default motion. Any scene can set `motion:`.
    if "motion" in raw:
        motion = Motion.from_value(raw["motion"])
    elif stype in ("title", "card"):
        motion = Motion()  # type "none"
    else:
        motion = Motion.from_value(defaults.get("motion"))

    duration = raw.get("duration")
    if isinstance(duration, str) and duration.strip().lower() == "auto":
        duration = None
    duration = float(duration) if duration is not None else None

    # A lead-in holds the scene's visual before narration starts (dead air), the
    # way Keynote's "start after" delays a build. Accept a few spellings; a
    # per-scene value overrides the `defaults` value.
    def _first(*keys: str) -> Any:
        for k in keys:
            if k in raw:
                return raw[k]
        for k in keys:
            if k in defaults:
                return defaults[k]
        return None

    lead_raw = _first("lead_in", "lead-in", "time_before", "time-before")
    lead_in = max(0.0, float(lead_raw)) if lead_raw is not None else 0.0

    voice = VoiceSpec.from_dict(raw["voice"]) if isinstance(raw.get("voice"), dict) else None

    code_steps: list[CodeStep] = []
    if stype == "code":
        scene_typing = bool(raw.get("typing", False))
        raw_steps = raw.get("steps")
        if isinstance(raw_steps, list):
            for st in raw_steps:
                if isinstance(st, dict) and "code" in st:
                    code_steps.append(
                        CodeStep(
                            code=str(st["code"]).rstrip("\n"),
                            focus=[int(n) for n in (st.get("focus") or [])],
                            typing=bool(st.get("typing", scene_typing)),
                        )
                    )
                elif isinstance(st, str):
                    code_steps.append(CodeStep(code=st.rstrip("\n"), typing=scene_typing))
        elif isinstance(raw.get("code"), str):
            code_steps.append(CodeStep(code=raw["code"].rstrip("\n"), typing=scene_typing))
        if not code_steps:
            raise ShowreelSpecError(f"code scene {sid!r} needs a `code:` or `steps:` list")

    overlays: list[Overlay] = []
    for ov in raw.get("overlays") or []:
        if isinstance(ov, dict):
            rect = ov.get("rect") or [0.3, 0.3, 0.4, 0.2]
            overlays.append(
                Overlay(
                    at=float(ov.get("at", 0.0)),
                    duration=float(ov.get("duration", 2.0)),
                    type=str(ov.get("type", "box")),
                    rect=[float(v) for v in rect][:4],
                    text=str(ov.get("text", "")),
                    color=str(ov.get("color", "#f1fa8c")),
                    fade=float(ov.get("fade", 0.3)),
                )
            )

    cursor: list[CursorKey] = []
    cursor_mode = ""
    raw_cursor = raw.get("cursor")
    if isinstance(raw_cursor, str):  # e.g. `cursor: synthetic` for web scenes
        cursor_mode = raw_cursor.strip()
    if isinstance(raw_cursor, list):  # explicit waypoint path
        for k in raw_cursor:
            if isinstance(k, dict):
                cursor.append(
                    CursorKey(
                        at=float(k.get("at", 0.0)),
                        x=float(k.get("x", 0.5)),
                        y=float(k.get("y", 0.5)),
                        click=bool(k.get("click", False)),
                    )
                )

    return Scene(
        id=sid,
        type=stype,
        say=say,
        say_prompt=say_prompt,
        duration=duration,
        lead_in=lead_in,
        transition=str(raw.get("transition", defaults.get("transition", "crossfade"))),
        transition_duration=float(
            raw.get("transition_duration", defaults.get("transition_duration", 0.5))
        ),
        captions=bool(raw.get("captions", defaults.get("captions", True))),
        motion=motion,
        voice=voice,
        title=str(raw.get("title", "")),
        subtitle=str(raw.get("subtitle", "")),
        body=str(raw.get("body", "")),
        cta=str(raw.get("cta", "")),
        src=str(raw.get("src", "")),
        language=str(raw.get("language", "python")),
        code_steps=code_steps,
        sfx=[c for c in (raw.get("sfx") or []) if isinstance(c, dict)],
        url=str(raw.get("url", "")),
        viewport=raw.get("viewport") if isinstance(raw.get("viewport"), dict) else {},
        steps=[s for s in (raw.get("steps") or []) if isinstance(s, dict)]
        if stype == "web"
        else [],
        cursor_mode=cursor_mode,
        notebook=str(raw.get("notebook", "")) if stype == "notebook" else "",
        runtime=str(raw.get("runtime", "marimo")),
        capture=raw.get("capture") if isinstance(raw.get("capture"), dict) else {},
        overlays=overlays,
        cursor=cursor,
    )


def load_showreel(path: str | Path) -> Showreel:
    """Load and validate a ``name.showreel.yml`` file."""
    import yaml

    p = Path(path)
    if not p.exists():
        raise ShowreelSpecError(f"Spec file not found: {p}")

    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ShowreelSpecError(f"{p} did not parse to a mapping")

    # The top-level config may live under a `showreel:` key or at the root.
    meta = data.get("showreel") if isinstance(data.get("showreel"), dict) else data

    def _get(key: str) -> Any:
        # Prefer the root, fall back to the `showreel:` block (or vice versa).
        if key in data:
            return data[key]
        return meta.get(key)

    voice = VoiceSpec.from_dict(_get("voice")) if isinstance(_get("voice"), dict) else VoiceSpec()
    defaults = _get("defaults") if isinstance(_get("defaults"), dict) else {}

    raw_scenes = _get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ShowreelSpecError(f"{p} must define a non-empty `scenes:` list")

    scenes = [_parse_scene(raw, i, defaults) for i, raw in enumerate(raw_scenes)]

    seen: set[str] = set()
    for sc in scenes:
        if sc.id in seen:
            raise ShowreelSpecError(f"Duplicate scene id: {sc.id!r}")
        seen.add(sc.id)

    return Showreel(
        title=str(meta.get("title", p.stem)),
        description=str(meta.get("description", "")),
        aspect=str(meta.get("aspect", "16:9")),
        resolution=str(meta.get("resolution", "1920x1080")),
        fps=int(meta.get("fps", 30)),
        theme=str(meta.get("theme", "auto")),
        brand=meta.get("brand") if isinstance(meta.get("brand"), dict) else {},
        voice=voice,
        music=_get("music") if isinstance(_get("music"), dict) else None,
        sfx=_get("sfx") if isinstance(_get("sfx"), dict) else {},
        scenes=scenes,
        source_path=p,
    )


SCAFFOLD_TEMPLATE = """\
# {name}.showreel.yml — a scripted, narrated demo reel for Great Docs.
# Build:   great-docs showreel build {name}
# Preview: great-docs showreel preview {name}
showreel:
  title: "{title}"
  description: "A short narrated demo."
  aspect: "16:9"
  theme: auto

voice:
  engine: piper            # piper (local) | openai | elevenlabs | azure
  name: "en_US-amy-medium"

defaults:
  transition: crossfade
  captions: true
  motion: {{ type: ken_burns, zoom: 1.06, from: center, to: top-left }}

scenes:
  - id: intro
    type: title
    title: "{title}"
    subtitle: "Built with Great Docs showreel"
    say: "Welcome — let me show you what this can do."
    motion: {{ type: none }}

  - id: shot
    type: image
    src: assets/screenshot.png
    say: "Here's the feature in action, with a gentle Ken Burns pan."

  - id: outro
    type: card
    title: "Get started"
    body: "pip install your-package"
    cta: "your-docs-site.example"
    say: "Give it a try today."
"""


def scaffold_spec(name: str, title: str | None = None) -> str:
    """Return starter YAML for ``great-docs showreel new``."""
    return SCAFFOLD_TEMPLATE.format(name=name, title=title or name.replace("-", " ").title())
