"""Tests for the showreel feature (P0 vertical slice)."""

from __future__ import annotations

import json

import pytest

from great_docs._showreel import (
    ShowreelSpecError,
    build_showreel,
    load_showreel,
    render_preview_html,
    scaffold_spec,
)
from great_docs._showreel.captions import build_vtt
from great_docs._showreel.manifest import build_manifest
from great_docs._showreel.spec import Scene, Showreel
from great_docs._showreel.voice import (
    SilentEngine,
    estimate_duration,
    get_engine,
    synthesize_line,
)

# --- helpers ---------------------------------------------------------------

SPEC = """\
showreel:
  title: "My Reel"
  theme: dark
  brand: { accent: "#ff0066" }

voice:
  engine: silent
  name: "test-voice"

defaults:
  transition: crossfade
  captions: true
  motion: { type: pan-zoom, zoom: 1.1, from: center, to: top-left }

scenes:
  - id: intro
    type: title
    title: "Hello"
    subtitle: "World"
    say: "Welcome to the show."
    motion: { type: none }
  - id: pic
    type: image
    src: shot.png
    say: { prompt: "describe the screenshot" }
    duration: 4.0
  - id: bye
    type: card
    title: "Done"
    say: "Thanks for watching, that is all for now."
"""


def _write_spec(tmp_path, text=SPEC, name="demo.showreel.yml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --- spec parsing ----------------------------------------------------------


def test_load_showreel_basic(tmp_path):
    show = load_showreel(_write_spec(tmp_path))
    assert isinstance(show, Showreel)
    assert show.title == "My Reel"
    assert show.theme == "dark"
    assert show.brand["accent"] == "#ff0066"
    assert show.voice.engine == "silent"
    assert len(show.scenes) == 3


def test_say_string_vs_prompt(tmp_path):
    show = load_showreel(_write_spec(tmp_path))
    assert show.scenes[0].say == "Welcome to the show."
    assert show.scenes[0].say_prompt == ""
    # `say: { prompt: ... }` populates the AI directive, not literal text.
    assert show.scenes[1].say == ""
    assert show.scenes[1].say_prompt == "describe the screenshot"


def test_defaults_inherited_and_overridden(tmp_path):
    show = load_showreel(_write_spec(tmp_path))
    # intro overrides motion to none
    assert show.scenes[0].motion.type == "none"
    # pic inherits the default pan-zoom motion
    assert show.scenes[1].motion.type == "pan-zoom"
    assert show.scenes[1].motion.zoom == pytest.approx(1.1)
    assert show.scenes[1].motion.end == "top-left"


def test_motion_type_aliases(tmp_path):
    # Keynote-style names are canonical; the old cinematography names still parse.
    spec = (
        "scenes:\n"
        "  - id: a\n    type: image\n    src: x.png\n    motion: { type: ken_burns }\n"
        "  - id: b\n    type: image\n    src: x.png\n    motion: { type: zoom }\n"
        "  - id: c\n    type: image\n    src: x.png\n    motion: { type: pan }\n"
        "  - id: d\n    type: image\n    src: x.png\n    motion: { type: pan-zoom }\n"
    )
    show = load_showreel(_write_spec(tmp_path, spec))
    assert [s.motion.type for s in show.scenes] == ["pan-zoom", "scale", "move", "pan-zoom"]


def test_duration_auto_vs_explicit(tmp_path):
    show = load_showreel(_write_spec(tmp_path))
    assert show.scenes[0].duration is None  # auto
    assert show.scenes[1].duration == pytest.approx(4.0)


def test_lead_in_parsing_and_defaults(tmp_path):
    spec = (
        "voice: { engine: silent }\n"
        "defaults: { lead_in: 0.5 }\n"
        "scenes:\n"
        "  - id: a\n    type: title\n    title: A\n    say: hi\n"  # inherits default
        "  - id: b\n    type: title\n    title: B\n    say: hi\n    lead_in: 1.2\n"  # overrides
        "  - id: c\n    type: title\n    title: C\n    say: hi\n    time_before: 0.8\n"  # alias
    )
    show = load_showreel(_write_spec(tmp_path, spec))
    assert show.scenes[0].lead_in == pytest.approx(0.5)
    assert show.scenes[1].lead_in == pytest.approx(1.2)
    assert show.scenes[2].lead_in == pytest.approx(0.8)


def test_lead_in_extends_auto_duration_and_manifest(tmp_path):
    # A lead-in pushes narration later and lengthens an auto scene by that much,
    # and it surfaces in the manifest so the player/export can delay the audio.
    base = "voice: { engine: silent }\nscenes:\n  - id: a\n    type: title\n    title: A\n    say: welcome to the show\n"
    plain = build_showreel(_write_spec(tmp_path, base), tmp_path / "plain", engine="silent")
    withlead = build_showreel(
        _write_spec(tmp_path, base.replace("say: welcome", "lead_in: 0.75\n    say: welcome"), name="b.showreel.yml"),
        tmp_path / "lead",
        engine="silent",
    )
    d0 = plain.manifest.scenes[0]
    d1 = withlead.manifest.scenes[0]
    assert d1.end - d0.end == pytest.approx(0.75, abs=1e-3)  # scene grew by the lead-in
    sc = withlead.manifest.to_dict()["scenes"][0]
    assert sc["lead_in"] == pytest.approx(0.75)


def test_image_fit_option(tmp_path):
    spec = (
        "scenes:\n"
        "  - id: a\n    type: image\n    src: photo.png\n"  # default cover
        "  - id: b\n    type: image\n    src: table.png\n    fit: contain\n"
    )
    show = load_showreel(_write_spec(tmp_path, spec))
    assert show.scenes[0].fit == "cover"
    assert show.scenes[1].fit == "contain"
    # Only the non-default "contain" is carried into the manifest.
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    (tmp_path / "table.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    r = build_showreel(_write_spec(tmp_path, spec, name="c.showreel.yml"), tmp_path / "out", engine="silent")
    scenes = r.manifest.to_dict()["scenes"]
    assert "fit" not in scenes[0]
    assert scenes[1]["fit"] == "contain"


def test_figure_scene(tmp_path):
    (tmp_path / "t.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    spec = (
        "voice: { engine: silent }\n"
        "scenes:\n"
        "  - id: f\n    type: figure\n    src: t.png\n"
        '    text: "Use `cols_label()` for **clear** headers."\n'
    )
    show = load_showreel(_write_spec(tmp_path, spec))
    sc = show.scenes[0]
    assert sc.type == "figure"
    assert sc.fit == "contain"  # a figure shows the whole visual by default
    assert sc.motion.type == "none"  # figures are static unless a motion is set
    r = build_showreel(_write_spec(tmp_path, spec, name="g.showreel.yml"), tmp_path / "out", engine="silent")
    d = r.manifest.to_dict()["scenes"][0]
    assert d["type"] == "figure" and d["src"].startswith("media/")
    # The text is rendered to HTML with inline markdown honored.
    assert "<code>cols_label()</code>" in d["text"]
    assert "<strong>clear</strong>" in d["text"]


def test_render_inline_md_escapes_then_formats():
    from great_docs._showreel.manifest import render_inline_md

    out = render_inline_md("a `f()` <script> **b** *i*")
    assert "<code>f()</code>" in out
    assert "&lt;script&gt;" in out  # raw HTML is escaped, never injected
    assert "<strong>b</strong>" in out and "<em>i</em>" in out


def test_duplicate_scene_id_raises(tmp_path):
    bad = SPEC.replace("id: bye", "id: intro")
    with pytest.raises(ShowreelSpecError, match="Duplicate scene id"):
        load_showreel(_write_spec(tmp_path, bad))


def test_missing_scenes_raises(tmp_path):
    with pytest.raises(ShowreelSpecError, match="non-empty `scenes"):
        load_showreel(_write_spec(tmp_path, "showreel:\n  title: x\n"))


def test_scene_without_type_raises(tmp_path):
    bad = "scenes:\n  - id: a\n    say: hi\n"
    with pytest.raises(ShowreelSpecError, match="missing a `type`"):
        load_showreel(_write_spec(tmp_path, bad))


# --- voice -----------------------------------------------------------------


def test_estimate_duration_scales_with_words():
    assert estimate_duration("") == pytest.approx(1.2)
    short = estimate_duration("one two three")
    long = estimate_duration(" ".join(["word"] * 30))
    assert long > short


def test_silent_engine_word_timings():
    eng = SilentEngine()
    assert eng.available()
    syn = eng.synthesize("alpha beta gamma", None, None)  # type: ignore[arg-type]
    assert syn.audio_path is None
    assert len(syn.words) == 3
    assert syn.words[0][1] == 0.0
    assert syn.words[-1][2] == pytest.approx(syn.duration)


def test_get_engine_falls_back_to_silent():
    # An unknown engine name resolves to a usable engine (silent fallback).
    eng = get_engine("definitely-not-real")
    assert eng.available()


def test_synthesize_line_empty_text(tmp_path):
    syn = synthesize_line(SilentEngine(), "", None, tmp_path, scene_id="x")  # type: ignore[arg-type]
    assert syn.audio_path is None
    assert syn.duration > 0


# --- captions --------------------------------------------------------------


def test_build_vtt_format():
    scenes = [
        Scene(id="a", type="title", say="Hello there", start=0.0, end=2.0),
        Scene(id="b", type="card", say="", start=2.0, end=4.0),  # no say -> skipped
        Scene(id="c", type="title", say="Goodbye", start=4.0, end=6.0, captions=False),  # off
        Scene(id="d", type="title", say="Last line", start=6.0, end=8.5),
    ]
    vtt = build_vtt(scenes)
    assert vtt.startswith("WEBVTT")
    assert "Hello there" in vtt
    assert "Goodbye" not in vtt  # captions off
    assert "00:00:00.000 --> 00:00:02.000" in vtt
    assert "00:00:06.000 --> 00:00:08.500" in vtt


# --- manifest --------------------------------------------------------------


def test_manifest_serialization(tmp_path):
    show = load_showreel(_write_spec(tmp_path))
    # Lay out minimal timing for serialization.
    for i, sc in enumerate(show.scenes):
        sc.start, sc.end = float(i), float(i) + 1.0
    show.duration = float(len(show.scenes))
    manifest = build_manifest(show)
    data = json.loads(manifest.to_json())

    assert data["title"] == "My Reel"
    assert len(data["scenes"]) == 3
    assert len(data["chapters"]) == 3
    # title/card scenes carry a `layer`; image scenes carry `src`.
    title_scene = data["scenes"][0]
    assert title_scene["layer"]["title"] == "Hello"
    assert data["scenes"][1]["src"] == "shot.png"
    assert data["scenes"][0]["motion"]["type"] == "none"


def test_deferred_scene_type_marked(tmp_path):
    spec = "scenes:\n  - id: v\n    type: video\n    say: a video clip\n"
    show = load_showreel(_write_spec(tmp_path, spec))
    assert show.scenes[0].is_deferred
    for i, sc in enumerate(show.scenes):
        sc.start, sc.end = float(i), float(i) + 1.0
    data = json.loads(build_manifest(show).to_json())
    assert data["scenes"][0]["deferred"] is True


# --- builder (end to end) --------------------------------------------------


def test_karaoke_word_timings_in_manifest(tmp_path):
    spec = (
        "voice: { engine: silent }\n"
        "scenes:\n  - id: a\n    type: title\n    title: Hi\n"
        "    say: one two three four\n"
    )
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, spec), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    words = m["scenes"][0]["words"]
    assert [w[0] for w in words] == ["one", "two", "three", "four"]
    # Timings are ordered and cover the clip start-to-finish.
    assert words[0][1] == 0.0
    assert all(words[i][2] <= words[i + 1][1] + 1e-6 for i in range(len(words) - 1))


def test_build_showreel_end_to_end(tmp_path):
    spec = _write_spec(tmp_path)
    (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")  # any file copies

    out = tmp_path / "out"
    result = build_showreel(spec, out, engine="silent")

    # Manifest written, scenes laid out sequentially, no gaps.
    manifest_path = out / "manifest.json"
    assert manifest_path.exists()
    m = json.loads(manifest_path.read_text())
    starts_ends = [(s["start"], s["end"]) for s in m["scenes"]]
    for (_, prev_end), (next_start, _) in zip(starts_ends, starts_ends[1:]):
        assert next_start == pytest.approx(prev_end)
    assert m["duration"] == pytest.approx(starts_ends[-1][1])

    # Explicit 4.0s duration is respected for the image scene.
    assert m["scenes"][1]["end"] - m["scenes"][1]["start"] == pytest.approx(4.0)

    # Image copied into the bundle and path rewritten.
    assert (out / "media" / "shot.png").exists()
    assert m["scenes"][1]["src"] == "media/shot.png"

    # Captions + self-contained preview produced.
    assert (out / "captions" / "narration.vtt").exists()
    assert (out / "index.html").exists()
    assert result.engine == "silent"


def test_preview_html_is_self_contained(tmp_path):
    show = load_showreel(_write_spec(tmp_path))
    for i, sc in enumerate(show.scenes):
        sc.start, sc.end = float(i), float(i) + 1.0
    show.duration = float(len(show.scenes))
    html = render_preview_html(build_manifest(show))
    assert "GreatShowreel.mount" in html
    assert "gd-showreel-manifest" in html
    assert "My Reel" in html


# --- code scenes -----------------------------------------------------------

CODE_SPEC = """\
voice: { engine: silent }
scenes:
  - id: code
    type: code
    language: python
    say: "the code"
    steps:
      - code: "import x"
        typing: true
      - code: |
          import x
          x.run()
        focus: [2]
"""


def test_code_scene_parsing(tmp_path):
    show = load_showreel(_write_spec(tmp_path, CODE_SPEC))
    sc = show.scenes[0]
    assert sc.type == "code"
    assert sc.language == "python"
    assert len(sc.code_steps) == 2
    assert sc.code_steps[0].typing is True
    assert sc.code_steps[1].focus == [2]


def test_code_scene_missing_steps_raises(tmp_path):
    bad = "scenes:\n  - id: c\n    type: code\n"
    with pytest.raises(ShowreelSpecError, match="needs a `code:` or `steps:`"):
        load_showreel(_write_spec(tmp_path, bad))


def test_code_scene_builds_highlighted_html(tmp_path):
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, CODE_SPEC), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    code_scene = m["scenes"][0]
    assert code_scene["language"] == "python"
    assert len(code_scene["code_steps"]) == 2
    # Pygments produced highlighted markup and the token CSS is present.
    assert 'class="gd-sr-code"' in code_scene["code_steps"][0]["html"]
    assert m["code_css"]
    assert ".gd-sr-code" in m["code_css"]


def test_code_step_note(tmp_path):
    spec = (
        "scenes:\n"
        "  - id: c\n    type: code\n    language: python\n    captions: false\n"
        "    steps:\n"
        '      - code: "GT(df)"\n        note: "Start with the raw table."\n'
        '      - code: "GT(df).data_color()"\n        focus: [1]\n'
        '        note: "One `data_color()` call adds the scale."\n        note_side: top\n'
    )
    show = load_showreel(_write_spec(tmp_path, spec))
    steps = show.scenes[0].code_steps
    assert steps[0].note == "Start with the raw table." and steps[0].note_side == "auto"
    assert steps[1].note_side == "top"
    r = build_showreel(_write_spec(tmp_path, spec, name="n.showreel.yml"), tmp_path / "out", engine="silent")
    d = r.manifest.to_dict()["scenes"][0]["code_steps"]
    assert "note" not in d[0] or d[0]["note"]  # step 0 note serialized
    assert d[0]["note"] == "Start with the raw table."
    # Inline markdown in the note is rendered to HTML with the accent code.
    assert "<code>data_color()</code>" in d[1]["note"]
    assert d[1]["note_side"] == "top"


# --- overlays + cursor -----------------------------------------------------

OVERLAY_SPEC = """\
voice: { engine: silent }
scenes:
  - id: shot
    type: image
    src: shot.png
    duration: 6.0
    say: "look here"
    cursor:
      - { at: 0.2, x: 0.1, y: 0.7 }
      - { at: 1.6, x: 0.5, y: 0.5, click: true }
    overlays:
      - { at: 0.5, duration: 4.0, type: spotlight, rect: [0.1, 0.2, 0.5, 0.3] }
      - { at: 2.0, duration: 2.0, type: callout, text: "the title", color: "#8be9fd" }
"""


def test_overlay_and_cursor_parsing(tmp_path):
    show = load_showreel(_write_spec(tmp_path, OVERLAY_SPEC))
    sc = show.scenes[0]
    assert len(sc.overlays) == 2
    assert sc.overlays[0].type == "spotlight"
    assert sc.overlays[0].rect == [0.1, 0.2, 0.5, 0.3]
    assert sc.overlays[1].type == "callout"
    assert sc.overlays[1].text == "the title"
    assert len(sc.cursor) == 2
    assert sc.cursor[1].click is True
    assert sc.cursor[1].x == pytest.approx(0.5)


def test_overlay_cursor_in_manifest(tmp_path):
    (tmp_path / "shot.png").write_bytes(b"x")
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, OVERLAY_SPEC), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    sc = m["scenes"][0]
    assert len(sc["overlays"]) == 2
    assert sc["overlays"][0]["type"] == "spotlight"
    assert sc["cursor"][1]["click"] is True


def test_annotate_region_callout(tmp_path):
    (tmp_path / "t.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    spec = (
        "scenes:\n"
        "  - id: out\n    type: image\n    src: t.png\n    fit: contain\n"
        "    annotate:\n"
        '      - rect: [0.4, 0.05, 0.25, 0.2]\n        note: "`data_color()` scales it"\n        at: 0.5\n        duration: 3\n'
        '      - rect: [0.1, 0.1, 0.2, 0.2]\n        note: "row labels"\n        side: left\n'
    )
    show = load_showreel(_write_spec(tmp_path, spec))
    ann = show.scenes[0].annotate
    assert len(ann) == 2
    assert ann[0].rect == [0.4, 0.05, 0.25, 0.2] and ann[0].at == 0.5
    assert ann[1].side == "left" and ann[1].duration == -1.0  # default: until scene end
    r = build_showreel(_write_spec(tmp_path, spec, name="a.showreel.yml"), tmp_path / "out", engine="silent")
    d = r.manifest.to_dict()["scenes"][0]["annotate"]
    assert d[0]["rect"] == [0.4, 0.05, 0.25, 0.2]
    assert "<code>data_color()</code>" in d[0]["note"]  # note rendered as markdown


def test_cursor_string_form_ignored(tmp_path):
    # `cursor: synthetic` (a web-scene flag, P1) must not break parsing.
    spec = "scenes:\n  - id: w\n    type: image\n    src: x.png\n    cursor: synthetic\n"
    show = load_showreel(_write_spec(tmp_path, spec))
    assert show.scenes[0].cursor == []


# --- web scenes (nokap capture) --------------------------------------------

WEB_SPEC = """\
voice: { engine: silent }
scenes:
  - id: app
    type: web
    url: app.html
    viewport: { width: 800, height: 600, scale: 1 }
    cursor: synthetic
    say: "live demo"
    steps:
      - { wait_for: "#title" }
      - { capture: { label: "start" } }
      - { click: "#go" }
      - { capture: { label: "after" } }
"""

APP_HTML = (
    "<!doctype html><html><body><h1 id='title'>Hi</h1>"
    "<button id='go' style='position:absolute;left:40px;top:120px'>Go</button>"
    "<div id='out'>x</div>"
    "<script>document.getElementById('go').onclick=function(){"
    "document.getElementById('out').textContent='clicked';};</script></body></html>"
)


def test_web_scene_parsing(tmp_path):
    show = load_showreel(_write_spec(tmp_path, WEB_SPEC))
    sc = show.scenes[0]
    assert sc.type == "web"
    assert sc.url == "app.html"
    assert sc.viewport["width"] == 800
    assert sc.cursor_mode == "synthetic"
    assert len(sc.steps) == 4


def test_web_capture_failure_degrades_to_placeholder(tmp_path):
    # A web scene with no URL must not crash the build — it becomes a placeholder.
    spec = "voice: { engine: silent }\nscenes:\n  - id: w\n    type: web\n    say: hi\n"
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, spec), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    assert m["scenes"][0]["deferred"] is True


def _chrome_available() -> bool:
    try:
        import nokap

        nokap.find_chrome()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _chrome_available(), reason="needs nokap + Chrome")
def test_web_capture_live(tmp_path):
    (tmp_path / "app.html").write_text(APP_HTML, encoding="utf-8")
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, WEB_SPEC), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    sc = m["scenes"][0]
    assert sc.get("deferred") is not True
    assert len(sc["keyframes"]) == 2
    assert all((out / kf["file"]).exists() for kf in sc["keyframes"])
    # The click on #go produced a synthetic cursor waypoint.
    assert sc.get("cursor") and sc["cursor"][0]["click"] is True


# --- export ----------------------------------------------------------------


def test_aspect_size():
    from great_docs._showreel.export import _aspect_size

    assert _aspect_size("16:9", 720) == (1280, 720)
    assert _aspect_size("1:1", 540) == (540, 540)
    assert _aspect_size("9:16", 1280) == (720, 1280)
    # Always even dimensions (h.264 yuv420p requirement).
    w, h = _aspect_size("16:9", 721)
    assert w % 2 == 0 and h % 2 == 0


def test_export_requires_manifest(tmp_path):
    from great_docs._showreel.export import ExportError, export_showreel

    with pytest.raises(ExportError, match="no manifest"):
        export_showreel(tmp_path)


def test_export_rejects_unknown_format(tmp_path):
    from great_docs._showreel.export import ExportError, export_showreel

    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ExportError, match="unsupported format"):
        export_showreel(tmp_path, fmt="mov")


def test_audio_filter_graph():
    from great_docs._showreel.export import _audio_filter

    # Nothing to mix.
    assert _audio_filter([], None, 1) is None
    # Foreground clips only (narration/SFX).
    voice = _audio_filter([(0.0, 0.0), (1.0, 0.0)], None, 3)
    assert "amix=inputs=2" in voice and "[outa]" in voice
    # Music only -> gain applied, no sidechain.
    mus = _audio_filter([], {"gain_db": -20}, 1)
    assert "volume=-20dB" in mus and "sidechaincompress" not in mus
    # Clips + music -> music ducked under the foreground via sidechain.
    both = _audio_filter([(0.5, -8)], {"gain_db": -22}, 2)
    assert "sidechaincompress" in both and "asplit=2" in both
    # Per-clip gain is applied (SFX clip at -8 dB).
    assert "volume=-8dB" in both


def _ffmpeg_available() -> bool:
    import shutil

    return shutil.which("ffmpeg") is not None


@pytest.mark.skipif(
    not (_chrome_available() and _ffmpeg_available()), reason="needs nokap+Chrome+ffmpeg"
)
def test_export_live(tmp_path):
    from great_docs._showreel import export_showreel

    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path), out, engine="silent")  # title/image/card, no shot.png
    video = export_showreel(out, tmp_path / "reel.mp4", fps=12, height=360)
    assert video.exists()
    assert video.stat().st_size > 1000
    assert video.read_bytes()[4:8] == b"ftyp"  # MP4 signature


# --- notebook scenes (marimo) ----------------------------------------------

NB_SPEC = """\
voice: { engine: silent }
scenes:
  - id: nb
    type: notebook
    notebook: nb.py
    runtime: marimo
    viewport: { width: 900, height: 500 }
    capture: { mode: full, settle_ms: 800 }
    say: "a notebook"
"""

NB_PY = (
    "import marimo\n"
    "app = marimo.App()\n\n"
    "@app.cell\n"
    "def _():\n"
    "    x = 6 * 7\n"
    "    x\n"
    "    return (x,)\n\n"
    'if __name__ == "__main__":\n'
    "    app.run()\n"
)


def test_notebook_scene_parsing(tmp_path):
    show = load_showreel(_write_spec(tmp_path, NB_SPEC))
    sc = show.scenes[0]
    assert sc.type == "notebook"
    assert sc.notebook == "nb.py"
    assert sc.runtime == "marimo"
    assert sc.capture["mode"] == "full"


def test_notebook_capture_failure_degrades(tmp_path):
    # Missing notebook file -> scene degrades to a placeholder, build still succeeds.
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, NB_SPEC), out, engine="silent")  # nb.py absent
    m = json.loads((out / "manifest.json").read_text())
    assert m["scenes"][0]["deferred"] is True


def _marimo_available() -> bool:
    try:
        import marimo  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not (_chrome_available() and _marimo_available()), reason="needs marimo + Chrome"
)
def test_notebook_capture_live(tmp_path):
    (tmp_path / "nb.py").write_text(NB_PY, encoding="utf-8")
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, NB_SPEC), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    sc = m["scenes"][0]
    assert sc.get("deferred") is not True
    assert len(sc["keyframes"]) >= 1
    assert (out / sc["keyframes"][0]["file"]).exists()


# --- embed / Quarto --------------------------------------------------------


def test_discover_showreel_refs():
    from great_docs._showreel import discover_showreel_refs

    text = (
        "intro\n{{< showreel file=\"reels/a\" >}}\n"
        "{{< showreel file='b' autoplay=true >}}\n"
        "{{< termshow file=\"x\" >}}\n"  # not a showreel
    )
    assert discover_showreel_refs(text) == ["reels/a", "b"]


def test_render_embed_html_self_contained(tmp_path):
    from great_docs._showreel import render_embed_html

    (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path), out, engine="silent")
    html = render_embed_html(out, element_id="gd-showreel-x")
    assert 'id="gd-showreel-x"' in html
    assert "GreatShowreel.mount" in html
    assert "Player.prototype.render" in html  # runtime inlined
    assert "gd-sr-stage" in html  # css inlined
    # The image asset is inlined as a data URI (no external fetch).
    assert "data:image/png;base64," in html


def test_embed_inlines_music_and_sfx(tmp_path):
    # Regression: the music bed and SFX files must be inlined as data URIs in the
    # embed, else the rendered guide serves nothing and the reel plays silently.
    from great_docs._showreel import render_embed_html

    (tmp_path / "bed.mp3").write_bytes(b"ID3" + b"\x00" * 128)
    (tmp_path / "logo.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    spec = (
        "showreel: { title: M, brand: { accent: '#2563eb', logo: logo.svg } }\n"
        "voice: { engine: silent }\n"
        "music: { file: bed.mp3, gain_db: -20 }\n"
        "sfx: { enabled: true, transition: whoosh }\n"
        "scenes:\n"
        "  - id: a\n    type: title\n    title: One\n    say: first scene here\n"
        "  - id: b\n    type: card\n    title: Two\n    say: second scene here now\n"
    )
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, spec), out, engine="silent")
    html = render_embed_html(out, element_id="gd-showreel-m")
    # The music bed, the synthesized whoosh, and the brand logo all land inline; the
    # bundle-relative "media/" paths must not survive into the shipped manifest.
    assert "data:audio" in html
    assert "data:image/svg" in html
    assert '"file": "media/' not in html
    assert '"logo": "media/' not in html
    from great_docs._showreel import prerender_showreels

    (tmp_path / "reels").mkdir()
    (tmp_path / "reels" / "demo.showreel.yml").write_text(
        "voice: { engine: silent }\nscenes:\n  - id: a\n    type: title\n    title: Hi\n    say: hello\n",
        encoding="utf-8",
    )
    (tmp_path / "page.qmd").write_text(
        "---\ntitle: t\n---\n{{< showreel file=\"reels/demo\" >}}\n", encoding="utf-8"
    )
    built = prerender_showreels(tmp_path, tmp_path, engine="silent")
    assert "reels/demo" in built
    assert (tmp_path / "showreel" / "demo" / "embed.html").exists()
    assert (tmp_path / "showreel" / "demo" / "manifest.json").exists()


# --- sfx --------------------------------------------------------------------


def test_sfx_recipes_defined():
    from great_docs._showreel.sfx import SFX_RECIPES, available_sfx

    assert "whoosh" in SFX_RECIPES and "click" in SFX_RECIPES
    assert set(available_sfx()) == set(SFX_RECIPES)


def test_sfx_events_in_manifest(tmp_path):
    # Transition SFX between scenes + a per-scene explicit cue.
    spec = (
        "showreel:\n  title: T\n"
        "voice: { engine: silent }\n"
        "sfx: { enabled: true, transition: whoosh, gain_db: -6 }\n"
        "scenes:\n"
        "  - id: a\n    type: title\n    title: A\n    say: first\n"
        "  - id: b\n    type: card\n    title: B\n    say: second\n"
        "    sfx:\n      - { at: 0.2, sound: ding, gain_db: -4 }\n"
    )
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, spec), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    sfx = m["sfx"]
    sounds = {ev["file"] for ev in sfx}
    # A transition whoosh (scene b start) + an explicit ding cue.
    assert any("whoosh" in f for f in sounds)
    assert any("ding" in f for f in sounds)
    # Events are time-ordered and their sound files exist in the bundle.
    times = [ev["time"] for ev in sfx]
    assert times == sorted(times)
    assert all((out / ev["file"]).exists() for ev in sfx)


# --- logo stings + poster --------------------------------------------------


def test_brand_logo_copied_into_bundle(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nlogo")
    spec = (
        "showreel:\n  title: T\n  brand: { logo: logo.png, accent: '#6ea8ff' }\n"
        "voice: { engine: silent }\n"
        "scenes:\n  - id: a\n    type: title\n    title: Hi\n    say: hi\n"
    )
    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path, spec), out, engine="silent")
    m = json.loads((out / "manifest.json").read_text())
    assert m["brand"]["logo"] == "media/logo.png"
    assert (out / "media" / "logo.png").exists()


def test_export_poster_requires_manifest(tmp_path):
    from great_docs._showreel.export import ExportError, export_poster

    with pytest.raises(ExportError, match="no manifest"):
        export_poster(tmp_path)


@pytest.mark.skipif(not _chrome_available(), reason="needs nokap + Chrome")
def test_export_poster_live(tmp_path):
    from great_docs._showreel import export_poster

    out = tmp_path / "out"
    build_showreel(_write_spec(tmp_path), out, engine="silent")
    png = export_poster(out, tmp_path / "poster.png", at=0.5, height=360)
    assert png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


# --- studio editor ---------------------------------------------------------


def test_editor_yaml_roundtrip(tmp_path):
    from great_docs._showreel.editor import load_spec_doc, save_spec_doc

    spec = _write_spec(tmp_path)
    doc = load_spec_doc(spec)
    assert doc["scenes"][0]["type"] == "title"
    # Edit like the editor would, then write back and reload.
    doc["scenes"][0]["subtitle"] = "edited"
    doc["scenes"].append({"id": "outro", "type": "card", "title": "Bye", "say": "bye"})
    save_spec_doc(spec, doc)
    reloaded = load_spec_doc(spec)
    assert reloaded["scenes"][0]["subtitle"] == "edited"
    assert reloaded["scenes"][-1]["id"] == "outro"
    # And it still parses through the normal loader.
    show = load_showreel(spec)
    assert len(show.scenes) == 4
    assert show.scenes[-1].type == "card"


def test_editor_html_self_contained():
    from great_docs._showreel.editor import _editor_html

    html = _editor_html()
    assert "GreatStudio.mount" in html
    assert "GreatShowreel" in html  # player runtime inlined
    assert "st-toolbar" in html  # editor CSS inlined
    assert "window.__studio" in html  # command API present


# --- scaffold --------------------------------------------------------------


def test_scaffold_spec_round_trips(tmp_path):
    text = scaffold_spec("my-demo", "My Demo")
    p = _write_spec(tmp_path, text, name="my-demo.showreel.yml")
    show = load_showreel(p)
    assert show.title == "My Demo"
    assert len(show.scenes) == 3
    assert {s.type for s in show.scenes} == {"title", "image", "card"}
