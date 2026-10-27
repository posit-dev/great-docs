"""Tests for animated SVG export (`great-docs termshow export`)."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player import apply_script, generate_manifest
from great_docs._term_player import export as export_mod
from great_docs._term_player.export import (
    CHAPTER_CARD_SECONDS,
    _wrap,
    export_svg,
    picture_snippet,
)
from great_docs._term_player.parser import parse_termshow_str
from great_docs._term_player.script import _parse_script_data
from great_docs.cli import cli

SVG_NS = "{http://www.w3.org/2000/svg}"

# Output at 0s, 1s, and 3s (delays are relative to the previous event)
EVENTS = [[0.0, "o", "$ "], [1.0, "o", "echo hi\r\nhi\r\n"], [2.0, "o", "$ "]]


def _recording_text(events=EVENTS, title: str = "Demo", cols: int = 40, rows: int = 6) -> str:
    header = {
        "version": 1,
        "format": "termshow",
        "term": {"cols": cols, "rows": rows},
        "title": title,
    }
    return "\n".join([json.dumps(header)] + [json.dumps(e) for e in events])


def _manifest(script: dict | None = None, **kwargs):
    recording = parse_termshow_str(_recording_text(**kwargs))
    script_obj = _parse_script_data(script) if script is not None else None
    if script_obj:
        recording = apply_script(recording, script_obj)
    return generate_manifest(recording, script_obj)


def _keyframes(svg: str, name: str) -> list[tuple[float, str]]:
    """The stops of one `@keyframes` rule, as (percentage, declaration)."""
    match = re.search(rf"@keyframes {name}\{{((?:[0-9.]+%\{{[^}}]*\}})*)\}}", svg)
    assert match, f"no @keyframes {name}"
    return [(float(p), v) for p, v in re.findall(r"([0-9.]+)%\{([^}]*)\}", match.group(1))]


def _duration(svg: str, name: str = "strip") -> float:
    match = re.search(rf"animation:{name} ([0-9.]+)s", svg)
    assert match, f"no animation {name}"
    return float(match.group(1))


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


class TestStructure:
    def test_well_formed_with_title(self):
        svg = export_svg(_manifest())
        root = ET.fromstring(svg)
        assert root.tag == f"{SVG_NS}svg"
        assert root.find(f"{SVG_NS}title").text == "Demo"
        assert root.get("aria-label") == "Demo"

    def test_size_matches_cell_grid_without_chrome(self):
        m = _manifest()
        root = ET.fromstring(export_svg(m))
        cell_w = m.screen.font_size * 0.6
        cell_h = m.screen.font_size * m.screen.line_height
        assert float(root.get("width")) == pytest.approx(40 * cell_w + 2 * m.screen.padding)
        assert float(root.get("height")) == pytest.approx(6 * cell_h + 2 * m.screen.padding)

    def test_title_bar_adds_height(self):
        plain = ET.fromstring(export_svg(_manifest()))
        chrome = ET.fromstring(export_svg(_manifest({"settings": {"window_chrome": "colorful"}})))
        assert float(chrome.get("height")) == pytest.approx(float(plain.get("height")) + 36)
        svg = export_svg(_manifest({"settings": {"window_chrome": "colorful"}}))
        assert svg.count("<circle") == 3
        assert 'fill="#f38ba8"' in svg

    def test_each_row_defined_once(self):
        m = _manifest()
        svg = export_svg(m)
        nonempty = {i for fr in m.frames for i in fr.lines if m.lines[i][0] or m.lines[i][1]}
        defined = re.findall(r'<g id="l(\d+)">', svg)
        assert sorted(int(i) for i in defined) == sorted(nonempty)
        assert len(defined) == len(set(defined))
        # Every non-empty row of every screen is drawn by reference
        uses = sum(1 for fr in m.frames for i in fr.lines if i in nonempty)
        assert svg.count("<use href=") == uses

    def test_one_slot_per_unique_screen(self):
        m = _manifest()
        svg = export_svg(m)
        cell_h = m.screen.font_size * m.screen.line_height
        term_h = 6 * cell_h + 2 * m.screen.padding
        slots = re.findall(r'<g transform="translate\(16,([0-9.]+)\)">', svg)
        assert [float(y) for y in slots] == pytest.approx(
            [i * term_h + 16 for i in range(len(m.frames))]
        )

    def test_text_is_escaped(self):
        svg = export_svg(_manifest(events=[[0.0, "o", "a < b & c"]]))
        ET.fromstring(svg)
        assert "a &lt; b &amp; c" in svg

    def test_cursor_blinks(self):
        svg = export_svg(_manifest())
        assert 'class="cur"' in svg
        assert ".cur{animation:blink 1s step-end infinite}" in svg

    def test_hidden_cursor_not_drawn(self):
        svg = export_svg(_manifest({"settings": {"show_cursor": False}}))
        assert 'class="cur"' not in svg

    def test_needs_v2_manifest(self):
        m = _manifest()
        m.screen = None
        with pytest.raises(ValueError, match="version 2"):
            export_svg(m)


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


class TestTiming:
    def test_strip_stops_at_screen_changes(self):
        m = _manifest()
        svg = export_svg(m, end_pause=2.0)
        # Duration 3s plus the 2s end pause
        assert _duration(svg) == pytest.approx(5.0)
        stops = _keyframes(svg, "strip")
        # Screens change at 0s, 1s, and 3s; the last stop holds to 100%
        assert [p for p, _ in stops] == pytest.approx([0, 20, 60, 100])
        assert stops[-1][1] == stops[-2][1]
        assert "step-end infinite" in svg

    def test_repeated_screens_merged(self):
        # Keyframes every 0.5s over an unchanging 4s stretch show one screen
        events = [[0.0, "o", "$ "], [4.0, "o", "x"]]
        m = generate_manifest(parse_termshow_str(_recording_text(events)), keyframe_interval=0.5)
        assert len(m.keyframes) > 3
        stops = _keyframes(export_svg(m, end_pause=0), "strip")
        assert [p for p, _ in stops] == pytest.approx([0, 100])

    def test_cuts_shorten_animation(self):
        full = _duration(export_svg(_manifest(), end_pause=0))
        cut = _duration(export_svg(_manifest({"cuts": [{"from": 1.5, "to": 2.5}]}), end_pause=0))
        assert full == pytest.approx(3.0)
        assert cut == pytest.approx(2.0)

    def test_speed_applied(self):
        svg = export_svg(_manifest({"settings": {"speed": 2}}), end_pause=0)
        assert _duration(svg) == pytest.approx(1.5)

    def test_speed_map_applied(self):
        m = _manifest({"speed_map": [{"from": 1, "to": 3, "speed": 4}]})
        # The output at 1s comes before the sped-up range, so it keeps its time
        assert [k.time for k in m.keyframes] == pytest.approx([0.0, 1.0, 1.5])
        assert _duration(export_svg(m, end_pause=0)) == pytest.approx(1.5)

    def test_no_loop_stops_on_last_screen(self):
        svg = export_svg(_manifest(), loop=False)
        assert "infinite" not in svg.replace("blink 1s step-end infinite", "")
        assert "step-end 1 forwards" in svg

    def test_fallback_and_reduced_motion_show_last_screen(self):
        m = _manifest()
        svg = export_svg(m)
        cell_h = m.screen.font_size * m.screen.line_height
        term_h = 6 * cell_h + 2 * m.screen.padding
        last = m.keyframes[-1].frame
        assert f'<g transform="translate(0,{-last * term_h:.1f})"' in svg
        assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in svg

    def test_zero_length_is_static(self):
        m = _manifest(events=[[0.0, "o", "$ "]])
        svg = export_svg(m, end_pause=0)
        ET.fromstring(svg)
        assert "animation:strip" not in svg


# ---------------------------------------------------------------------------
# Annotations and chapters
# ---------------------------------------------------------------------------


ANNOTATED = {
    "annotations": [
        {"at": 1.0, "duration": 1.0, "text": "Use <b> & co", "position": "top-left"},
        {"at": 0.0, "duration": 2.0, "text": "Subtle", "style": "subtle"},
    ]
}


class TestAnnotations:
    def test_baked_in_with_fades(self):
        svg = export_svg(_manifest(ANNOTATED), end_pause=0)
        ET.fromstring(svg)
        assert "Use &lt;b&gt; &amp; co" in svg
        stops = _keyframes(svg, "a0")
        # Fade in over 0.3s from 1s, fade out ending at 2s, of a 3s animation
        assert [p for p, _ in stops] == pytest.approx(
            [0, 100 / 3, 1.3 / 3 * 100, 1.7 / 3 * 100, 200 / 3, 100], abs=1e-3
        )
        assert [v for _, v in stops] == ["opacity:0", "opacity:0", "opacity:1"] + [
            "opacity:1",
            "opacity:0",
            "opacity:0",
        ]
        assert "animation:a0 3.000s linear infinite" in svg
        assert "animation:a1 " in svg

    def test_can_be_left_out(self):
        svg = export_svg(_manifest(ANNOTATED), annotations=False)
        assert "@keyframes a0" not in svg
        assert "Subtle" not in svg

    def test_positions(self):
        m = _manifest(ANNOTATED)
        root = ET.fromstring(export_svg(m))
        boxes = [g for g in root.iter(f"{SVG_NS}g") if "animation:a" in (g.get("style") or "")]
        x0, y0 = map(float, re.findall(r"[-0-9.]+", boxes[0].get("transform")))
        x1, y1 = map(float, re.findall(r"[-0-9.]+", boxes[1].get("transform")))
        assert (x0, y0) == (12.0, 12.0)  # top-left
        # bottom-right (the default): the box's far edges sit 12px inside the screen
        width = float(root.get("width"))
        height = float(root.get("height"))
        rect = boxes[1].find(f"{SVG_NS}rect")
        assert x1 + float(rect.get("width")) == pytest.approx(width - 12, abs=0.11)
        assert y1 + float(rect.get("height")) == pytest.approx(height - 12, abs=0.11)

    def test_after_end_skipped(self):
        svg = export_svg(
            _manifest({"annotations": [{"at": 10, "duration": 1, "text": "Too late"}]}), end_pause=0
        )
        assert "Too late" not in svg

    def test_wrap(self):
        assert _wrap("one two three four", 9) == ["one two", "three", "four"]
        assert _wrap("abcdefghij", 4) == ["abcd", "efgh", "ij"]
        assert _wrap("a\nb", 10) == ["a", "b"]


CHAPTERED = {"chapters": [{"at": 0, "label": "Start"}, {"at": 1, "label": "Echo & more"}]}


class TestChapters:
    def test_labels_in_title_bar(self):
        svg = export_svg(_manifest(CHAPTERED), end_pause=0)
        ET.fromstring(svg)
        assert "Echo &amp; more" in svg
        assert [p for p, _ in _keyframes(svg, "c0")] == pytest.approx([0, 100 / 3], abs=1e-3)
        assert _keyframes(svg, "c0")[0][1] == "opacity:1"
        # The last chapter's label is the one shown without animation
        assert 'opacity="1" style="animation:c1' in svg
        assert 'opacity="0" style="animation:c0' in svg

    def test_cards_lengthen_timeline(self):
        svg = export_svg(_manifest(CHAPTERED), end_pause=0, chapter_cards=True)
        ET.fromstring(svg)
        card = CHAPTER_CARD_SECONDS
        total = 3 + 2 * card
        assert _duration(svg) == pytest.approx(total)
        # The screen at 1s now changes after both cards
        stop_times = [p * total / 100 for p, _ in _keyframes(svg, "strip")]
        assert stop_times[1:3] == pytest.approx([card, 1 + 2 * card], abs=0.001)
        # The second card shows just before it
        k1 = _keyframes(svg, "k1")
        assert k1[1][0] * total / 100 == pytest.approx(1 + card, abs=0.001)
        assert k1[4][0] * total / 100 == pytest.approx(1 + 2 * card, abs=0.001)
        assert 'font-size="20"' in svg

    def test_no_cards_by_default(self):
        svg = export_svg(_manifest(CHAPTERED))
        assert "@keyframes k0" not in svg


# ---------------------------------------------------------------------------
# Themes and fonts
# ---------------------------------------------------------------------------


class TestThemes:
    def test_pair_sides(self):
        m = _manifest({"settings": {"theme": "auto"}})
        assert m.dark is not None
        light = export_svg(m)
        dark = export_svg(m, dark=True)
        assert f'fill="{m.screen.bg}"' in light
        assert f'fill="{m.dark.bg}"' in dark
        assert f'fill="{m.dark.bg}"' not in light

    def test_dark_ignored_without_pair(self):
        m = _manifest()
        assert export_svg(m, dark=True) == export_svg(m)

    def test_embedded_font(self, tmp_path: Path):
        font = tmp_path / "Mono.woff2"
        font.write_bytes(b"fontdata")
        svg = export_svg(_manifest(), font_file=font)
        assert 'src:url(data:font/woff2;base64,Zm9udGRhdGE=) format("woff2")' in svg
        assert '.t{font-family:"termshow-export", ' in svg

    def test_bad_font_type(self, tmp_path: Path):
        font = tmp_path / "Mono.pcf"
        font.write_bytes(b"x")
        with pytest.raises(ValueError, match="Unsupported font"):
            export_svg(_manifest(), font_file=font)

    def test_picture_snippet(self):
        snippet = picture_snippet("a-light.svg", "a-dark.svg", 'Say "hi"')
        assert '<source media="(prefers-color-scheme: dark)" srcset="a-dark.svg">' in snippet
        assert '<img src="a-light.svg" alt="Say &quot;hi&quot;">' in snippet


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, script: str | None = None) -> Path:
    source = tmp_path / "demo.termshow"
    source.write_text(_recording_text(), encoding="utf-8")
    if script is not None:
        (tmp_path / "demo.termshow.yml").write_text(script, encoding="utf-8")
    return source


class TestCli:
    def test_default_output(self, tmp_path: Path):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--svg"])
        assert result.exit_code == 0, result.output
        out = tmp_path / "demo.svg"
        ET.fromstring(out.read_text(encoding="utf-8"))
        assert "✓ Exported" in result.output
        assert "<picture>" not in result.output

    def test_output_option_and_script(self, tmp_path: Path):
        source = _write(tmp_path, "settings:\n  speed: 2\n")
        out = tmp_path / "sub" / "x.svg"
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert _duration(out.read_text(encoding="utf-8")) == pytest.approx(1.5 + 2)

    def test_no_script(self, tmp_path: Path):
        source = _write(tmp_path, "settings:\n  speed: 2\n")
        out = tmp_path / "x.svg"
        result = CliRunner().invoke(
            cli, ["termshow", "export", str(source), "-o", str(out), "--no-script", "--no-loop"]
        )
        assert result.exit_code == 0, result.output
        svg = out.read_text(encoding="utf-8")
        assert _duration(svg) == pytest.approx(3 + 2)
        assert "1 forwards" in svg

    def test_pair_writes_two_files_and_snippet(self, tmp_path: Path):
        source = _write(tmp_path, "settings:\n  theme: auto\n")
        result = CliRunner().invoke(cli, ["termshow", "export", str(source)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "demo-light.svg").exists()
        assert (tmp_path / "demo-dark.svg").exists()
        assert not (tmp_path / "demo.svg").exists()
        assert 'srcset="demo-dark.svg"' in result.output
        assert '<img src="demo-light.svg" alt="Demo">' in result.output

    def test_size_warning(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(export_mod, "SIZE_WARNING_BYTES", 100)
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source)])
        assert result.exit_code == 0, result.output
        assert "Warning:" in result.output
        assert "cuts" in result.output

    def test_no_warning_when_small(self, tmp_path: Path):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source)])
        assert "Warning:" not in result.output

    def test_negative_end_pause(self, tmp_path: Path):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--end-pause", "-1"])
        assert result.exit_code != 0
        assert "--end-pause" in result.output

    def test_bad_font_reported(self, tmp_path: Path):
        source = _write(tmp_path)
        font = tmp_path / "font.pcf"
        font.write_bytes(b"x")
        result = CliRunner().invoke(
            cli, ["termshow", "export", str(source), "--font-file", str(font)]
        )
        assert result.exit_code != 0
        assert "Unsupported font" in result.output
