"""Manifest generation: composes scenes into the build→player contract.

The manifest is the single artifact both the web player and (later) the ffmpeg
export consume. Its shape intentionally echoes ``_term_player/manifest.py``.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field

from .spec import Scene, Showreel


def render_inline_md(text: str) -> str:
    """Render a small subset of inline Markdown to HTML for figure text.

    Supports ``code``, ``**bold**``, and ``*italic*``. Everything else is
    HTML-escaped first, so authored text can never inject markup.
    """
    s = html.escape(text, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def _code_step_to_dict(step) -> dict:
    """Serialize a CodeStep, rendering any per-step annotation to HTML."""
    d: dict = {"html": step.html, "focus": step.focus, "typing": step.typing}
    if step.note:
        d["note"] = render_inline_md(step.note)
        d["note_side"] = step.note_side
    return d


@dataclass
class Manifest:
    """The complete manifest describing a built showreel."""

    version: int = 1
    title: str = ""
    description: str = ""
    duration: float = 0.0
    aspect: str = "16:9"
    fps: int = 30
    theme: str = "auto"
    brand: dict = field(default_factory=dict)
    captions: str | None = None  # relative path to .vtt
    music: dict | None = None
    sfx: list = field(default_factory=list)  # [{time, file, gain_db}]
    code_css: str = ""  # Pygments token CSS for code scenes
    player: dict = field(default_factory=dict)  # chrome/loop/autoplay options
    scenes: list[Scene] = field(default_factory=list)

    def _scene_to_dict(self, sc: Scene) -> dict:
        data: dict = {
            "id": sc.id,
            "type": sc.type,
            "start": round(sc.start, 3),
            "end": round(sc.end, 3),
            "transition": sc.transition,
            "transition_duration": round(sc.transition_duration, 3),
            "motion": sc.motion.to_dict(),
            "captions": sc.captions,
        }
        if sc.is_deferred:
            data["deferred"] = True
        if sc.lead_in:
            data["lead_in"] = round(sc.lead_in, 3)
        if sc.audio:
            data["audio"] = sc.audio
        if sc.say:
            data["say"] = sc.say
        if sc.words:
            data["words"] = [[w, round(s, 3), round(e, 3)] for (w, s, e) in sc.words]
        # Type-specific payload the player renders directly.
        if sc.type in ("title", "card") or sc.is_deferred:
            data["layer"] = {
                "title": sc.title,
                "subtitle": sc.subtitle,
                "body": sc.body,
                "cta": sc.cta,
            }
        if sc.type == "image":
            data["src"] = sc.src
            if sc.fit == "contain":
                data["fit"] = sc.fit
        if sc.type == "figure":
            data["src"] = sc.src
            data["fit"] = sc.fit
            if sc.text:
                data["text"] = render_inline_md(sc.text)
        if sc.keyframes:
            data["keyframes"] = sc.keyframes
        if sc.type == "code":
            data["language"] = sc.language
            data["code_steps"] = [_code_step_to_dict(step) for step in sc.code_steps]
        if sc.overlays:
            data["overlays"] = [
                {
                    "at": round(ov.at, 3),
                    "duration": round(ov.duration, 3),
                    "type": ov.type,
                    "rect": [round(v, 4) for v in ov.rect],
                    "text": ov.text,
                    "color": ov.color,
                    "fade": round(ov.fade, 3),
                }
                for ov in sc.overlays
            ]
        if sc.annotate:
            data["annotate"] = [
                {
                    "rect": [round(v, 4) for v in an.rect],
                    "note": render_inline_md(an.note),
                    "at": round(an.at, 3),
                    "duration": round(an.duration, 3),
                    "fade": round(an.fade, 3),
                    "side": an.side,
                }
                for an in sc.annotate
            ]
        if sc.cursor:
            data["cursor"] = [
                {"at": round(k.at, 3), "x": round(k.x, 4), "y": round(k.y, 4), "click": k.click}
                for k in sc.cursor
            ]
        return data

    def to_dict(self) -> dict:
        data: dict = {
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "duration": round(self.duration, 3),
            "aspect": self.aspect,
            "fps": self.fps,
            "theme": self.theme,
            "brand": self.brand,
            "scenes": [self._scene_to_dict(s) for s in self.scenes],
            "chapters": [
                {"time": round(s.start, 3), "label": (s.title or s.id)} for s in self.scenes
            ],
        }
        if self.captions:
            data["captions"] = self.captions
        if self.music:
            data["music"] = self.music
        if self.sfx:
            data["sfx"] = self.sfx
        if self.code_css:
            data["code_css"] = self.code_css
        if self.player:
            data["player"] = self.player
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def build_manifest(
    show: Showreel,
    *,
    captions_path: str | None = None,
    code_css: str = "",
    sfx: list | None = None,
) -> Manifest:
    """Assemble a :class:`Manifest` from a built :class:`Showreel`."""
    return Manifest(
        title=show.title,
        description=show.description,
        duration=show.duration,
        aspect=show.aspect,
        fps=show.fps,
        theme=show.theme,
        brand=show.brand,
        captions=captions_path,
        music=show.music,
        sfx=sfx or [],
        code_css=code_css,
        player=show.player,
        scenes=list(show.scenes),
    )
