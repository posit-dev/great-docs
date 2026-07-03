"""Build pipeline: spec → narration audio → timeline → manifest + player assets.

P0 vertical slice. Acquisition of live visuals (``nokap`` web/notebook capture)
arrives in P1; ffmpeg export in P4. Here we synthesize narration, derive scene
timing, copy ``image`` assets, and emit ``manifest.json`` plus a self-contained
preview ``index.html``.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .captions import build_vtt
from .code import render_code_scene
from .manifest import Manifest, build_manifest
from .player import write_preview
from .spec import Scene, Showreel, load_showreel
from .voice import get_engine, synthesize_line

# Padding added after narration so a scene doesn't cut off on the last word.
TAIL_PADDING = 0.4
# Default duration for a scene with no narration (e.g. a silent title card).
DEFAULT_SILENT_SCENE = 3.0


@dataclass
class BuildResult:
    manifest: Manifest
    output_dir: Path
    engine: str
    audio_scenes: int


def _build_sfx(show: Showreel, audio_dir: Path) -> list[dict]:
    """Compute SFX events (transitions, cursor clicks, explicit cues) + synthesize them."""
    from .sfx import NONE, SFX_RECIPES, synthesize_sfx

    cfg = show.sfx or {}
    enabled = bool(cfg.get("enabled", False))
    transition = str(cfg.get("transition", "whoosh"))
    click_sound = str(cfg.get("cursor_click", "click"))
    base_gain = float(cfg.get("gain_db", -8))

    events: list[dict] = []
    for i, sc in enumerate(show.scenes):
        if enabled and i > 0 and transition not in NONE:
            events.append({"time": sc.start, "sound": transition, "gain_db": base_gain})
        if enabled and click_sound not in NONE:
            for k in sc.cursor:
                if k.click:
                    events.append(
                        {"time": sc.start + k.at, "sound": click_sound, "gain_db": base_gain}
                    )
        for cue in sc.sfx:  # explicit cues play regardless of the global toggle
            events.append(
                {
                    "time": sc.start + float(cue.get("at", 0.0)),
                    "sound": str(cue.get("sound", "click")),
                    "gain_db": float(cue.get("gain_db", base_gain)),
                }
            )

    files: dict[str, str] = {}
    out: list[dict] = []
    for ev in sorted(events, key=lambda e: e["time"]):
        name = ev["sound"]
        if name not in SFX_RECIPES:
            continue
        if name not in files:
            path = audio_dir / f"sfx-{name}.wav"
            synthesize_sfx(name, path)
            files[name] = f"audio/{path.name}"
        out.append({"time": round(ev["time"], 3), "file": files[name], "gain_db": ev["gain_db"]})
    return out


def default_output_dir(spec_path: Path) -> Path:
    """Output under ``great-docs/showreel/<name>/`` next to the project root."""
    name = spec_path.name
    for suffix in (".showreel.yml", ".showreel.yaml", ".yml", ".yaml"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return Path("great-docs") / "showreel" / name


# A code step holds for at least this long when there's no narration to pace it.
CODE_STEP_SECONDS = 2.6


def _resolve_duration(sc: Scene, syn_duration: float | None) -> float:
    # An explicit duration is the author's contract — the lead-in lives inside it.
    if sc.duration is not None:
        return sc.duration
    # For auto durations the lead-in is added on top, so the whole narration (or
    # content pacing) still plays after the dead air.
    lead = sc.lead_in
    if syn_duration is not None:
        return round(lead + syn_duration + TAIL_PADDING, 3)
    if sc.type == "code" and sc.code_steps:
        return round(lead + CODE_STEP_SECONDS * len(sc.code_steps) + 0.8, 3)
    if sc.type in ("web", "notebook") and sc.keyframes:
        return round(lead + CODE_STEP_SECONDS * len(sc.keyframes) + 0.8, 3)
    # A figure with no narration is paced to give the reader time to read its text.
    if sc.type == "figure" and sc.text:
        words = len(sc.text.split())
        return round(lead + max(3.5, words / 2.6) + 0.8, 3)
    return round(lead + DEFAULT_SILENT_SCENE, 3)


def build_showreel(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    engine: str | None = None,
) -> BuildResult:
    """Build a showreel into a directory of player assets."""
    spec_path = Path(spec_path)
    show: Showreel = load_showreel(spec_path)

    out = Path(output_dir) if output_dir else default_output_dir(spec_path)
    out.mkdir(parents=True, exist_ok=True)
    audio_dir = out / "audio"
    media_dir = out / "media"

    ve = get_engine(engine or show.voice.engine)

    # --- Syntax-highlight code scenes (build-time, Pygments) ----------------
    dark = show.theme != "light"
    code_css = ""
    for sc in show.scenes:
        if sc.type == "code" and sc.code_steps:
            css = render_code_scene(sc, dark=dark)
            if not code_css:
                code_css = css

    # --- Capture web + notebook scenes via nokap (Chrome) -------------------
    capture_cursor: dict[str, list] = {}
    capture_scenes = [sc for sc in show.scenes if sc.type in ("web", "notebook")]
    if capture_scenes:
        from .capture import CaptureError, capture_notebook_scene, capture_web_scene

        media_dir.mkdir(parents=True, exist_ok=True)
        for sc in capture_scenes:
            try:
                if sc.type == "web":
                    res = capture_web_scene(sc, spec_dir=spec_path.parent, media_dir=media_dir)
                else:
                    res = capture_notebook_scene(
                        sc, spec_dir=spec_path.parent, media_dir=media_dir
                    )
                sc.keyframes = res.keyframes
                if sc.cursor_mode == "synthetic" and not sc.cursor and res.cursor:
                    capture_cursor[sc.id] = res.cursor
            except CaptureError as exc:
                sc.failed = True
                print(f"  ! {sc.type} scene {sc.id!r} could not be captured ({exc}); placeholder")

    # --- Synthesize narration + lay out the timeline ------------------------
    t = 0.0
    audio_scenes = 0
    for sc in show.scenes:
        voice = sc.voice or show.voice
        syn = synthesize_line(ve, sc.say, voice, audio_dir, scene_id=sc.id) if sc.say else None

        dur = _resolve_duration(sc, syn.duration if syn else None)
        sc.start = round(t, 3)
        sc.end = round(t + dur, 3)
        t = sc.end

        if syn:
            sc.words = syn.words  # per-word timings for karaoke captions
        if syn and syn.audio_path and syn.audio_path.exists():
            sc.audio = f"audio/{syn.audio_path.name}"
            audio_scenes += 1

        # Convert captured synthetic-cursor fractions into scene-relative seconds.
        if sc.id in capture_cursor:
            from .spec import CursorKey

            sc.cursor = [
                CursorKey(at=round(frac * dur, 3), x=x, y=y, click=click)
                for (frac, x, y, click) in capture_cursor[sc.id]
            ]

        # Copy image assets into the bundle so the preview is self-contained.
        if sc.type in ("image", "figure") and sc.src:
            src = (spec_path.parent / sc.src).resolve()
            if src.exists():
                media_dir.mkdir(parents=True, exist_ok=True)
                dest = media_dir / src.name
                shutil.copyfile(src, dest)
                sc.src = f"media/{dest.name}"
            # If the source is missing we keep the path; the player shows a notice.

    show.duration = round(t, 3)

    # --- Brand logo (copy into the bundle for logo stings) ------------------
    if show.brand and show.brand.get("logo"):
        lsrc = (spec_path.parent / show.brand["logo"]).resolve()
        if lsrc.exists():
            media_dir.mkdir(parents=True, exist_ok=True)
            ldest = media_dir / lsrc.name
            shutil.copyfile(lsrc, ldest)
            show.brand = {**show.brand, "logo": f"media/{ldest.name}"}

    # --- Music bed (copy into the bundle so the player + export can find it) -
    if show.music and show.music.get("file"):
        msrc = (spec_path.parent / show.music["file"]).resolve()
        if msrc.exists():
            media_dir.mkdir(parents=True, exist_ok=True)
            mdest = media_dir / msrc.name
            shutil.copyfile(msrc, mdest)
            show.music = {**show.music, "file": f"media/{mdest.name}"}

    # --- Captions -----------------------------------------------------------
    vtt = build_vtt(show.scenes)
    captions_rel: str | None = None
    if vtt.strip() and vtt.strip() != "WEBVTT":
        (out / "captions").mkdir(parents=True, exist_ok=True)
        (out / "captions" / "narration.vtt").write_text(vtt, encoding="utf-8")
        captions_rel = "captions/narration.vtt"

    # --- Sound effects (synthesized, cached) --------------------------------
    sfx_events = _build_sfx(show, audio_dir)

    # --- Manifest + preview -------------------------------------------------
    manifest = build_manifest(
        show, captions_path=captions_rel, code_css=code_css, sfx=sfx_events
    )
    (out / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")
    write_preview(out, manifest)

    return BuildResult(
        manifest=manifest, output_dir=out, engine=ve.name, audio_scenes=audio_scenes
    )
