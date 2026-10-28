"""Tests for screenshots (`great-docs termshow snap`)."""

from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player import apply_script, generate_manifest
from great_docs._term_player import snap as snap_mod
from great_docs._term_player.parser import parse_termshow_str
from great_docs._term_player.script import _parse_script_data
from great_docs._term_player.snap import (
    SnapError,
    find_rasterizer,
    frame_at,
    rasterize,
    snap_svg,
    snap_time,
)
from great_docs.cli import cli

SVG_NS = "{http://www.w3.org/2000/svg}"

# Screens change at 0s, 1s, 2s and 4s (delays are relative to the previous event)
EVENTS = [
    [0.0, "o", "$ "],
    [1.0, "o", "one\r\n$ "],
    [1.0, "o", "two\r\n$ "],
    [2.0, "o", "three\r\n$ "],
]


def _recording_text(events=EVENTS, title: str = "Demo") -> str:
    header = {"version": 1, "format": "termshow", "term": {"cols": 30, "rows": 5}, "title": title}
    return "\n".join([json.dumps(header)] + [json.dumps(e) for e in events])


def _manifest(script: dict | None = None, events=EVENTS):
    recording = parse_termshow_str(_recording_text(events))
    script_obj = _parse_script_data(script) if script is not None else None
    if script_obj:
        recording = apply_script(recording, script_obj)
    return generate_manifest(recording, script_obj)


def _screen(svg: str) -> list[str]:
    """The text of each drawn row, top to bottom."""
    root = ET.fromstring(svg)
    rows = {
        g.get("id"): "".join(t.text or "" for t in g.iter(f"{SVG_NS}text"))
        for g in root.iter(f"{SVG_NS}g")
        if g.get("id")
    }
    uses = sorted(root.iter(f"{SVG_NS}use"), key=lambda u: float(u.get("y")))
    return [rows[u.get("href")[1:]] for u in uses]


def _write(tmp_path: Path, script: str | None = None) -> Path:
    source = tmp_path / "demo.termshow"
    source.write_text(_recording_text(), encoding="utf-8")
    if script is not None:
        (tmp_path / "demo.termshow.yml").write_text(script, encoding="utf-8")
    return source


class TestSnapTime:
    def test_end_by_default(self):
        m = _manifest()
        assert snap_time(m) == pytest.approx(4.0)

    def test_at(self):
        assert snap_time(_manifest(), at=1.5) == 1.5

    @pytest.mark.parametrize("at, message", [(-1, "can't be negative"), (9, "past the end")])
    def test_at_out_of_range(self, at, message):
        with pytest.raises(SnapError, match=message):
            snap_time(_manifest(), at=at)

    def test_chapter_is_its_last_screen(self):
        m = _manifest({"chapters": [{"at": 0, "label": "First"}, {"at": 2, "label": "Second"}]})
        assert snap_time(m, chapter="First") == pytest.approx(1.0)
        assert _screen(snap_svg(m, snap_time(m, chapter="First")))[-1] == "$"
        # The last chapter runs to the end
        assert snap_time(m, chapter="Second") == pytest.approx(4.0)

    def test_chapter_label_ignores_case(self):
        m = _manifest({"chapters": [{"at": 0, "label": "First"}, {"at": 2, "label": "Second"}]})
        assert snap_time(m, chapter="first") == pytest.approx(1.0)

    def test_unknown_chapter_lists_the_labels(self):
        m = _manifest({"chapters": [{"at": 0, "label": "First"}]})
        with pytest.raises(SnapError, match=r"labeled 'Third' \(the chapters are: 'First'\)"):
            snap_time(m, chapter="Third")
        with pytest.raises(SnapError, match="the chapters are: none"):
            snap_time(_manifest(), chapter="First")


class TestFrame:
    def test_screen_at_each_time(self):
        m = _manifest()
        assert _screen(snap_svg(m, 0.5)) == ["$"]
        assert _screen(snap_svg(m, 1.0)) == ["$ one", "$"]
        assert _screen(snap_svg(m, 3.99)) == ["$ one", "$ two", "$"]
        assert _screen(snap_svg(m, 4.0)) == ["$ one", "$ two", "$ three", "$"]

    def test_at_is_playback_time(self):
        # The cut removes 2s to 3s of the recording, so "three" shows at 3s of playback
        m = _manifest({"cuts": [{"from": 2, "to": 3}]})
        assert m.duration == pytest.approx(3.0)
        assert _screen(snap_svg(m, 3.0))[-2] == "$ three"
        assert frame_at(m, 2.5) is frame_at(m, 2.0)

    def test_spaces_are_kept(self):
        svg = snap_svg(_manifest(events=[[0, "o", "a   b"]]), 0)
        assert ET.fromstring(svg).get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"
        assert _screen(svg) == ["a   b"]

    def test_not_animated(self):
        svg = snap_svg(_manifest(), 2)
        assert "@keyframes" not in svg and "animation" not in svg

    def test_size_without_chrome(self):
        m = _manifest()
        root = ET.fromstring(snap_svg(m, 0))
        cell_h = m.screen.font_size * m.screen.line_height
        assert float(root.get("width")) == pytest.approx(30 * m.screen.font_size * 0.6 + 32)
        assert float(root.get("height")) == pytest.approx(5 * cell_h + 32)

    def test_cursor(self):
        assert 'opacity="0.7"' in snap_svg(_manifest(), 0)
        assert 'opacity="0.7"' not in snap_svg(_manifest({"settings": {"show_cursor": False}}), 0)

    def test_needs_v2_manifest(self):
        m = _manifest()
        m.screen = None
        with pytest.raises(ValueError, match="version 2"):
            snap_svg(m, 0)


class TestDecorations:
    def test_title_bar_shows_the_current_chapter(self):
        m = _manifest(
            {
                "chapters": [{"at": 1, "label": "First"}, {"at": 2, "label": "Second"}],
                "settings": {"window_chrome": "colorful"},
            }
        )
        svg = snap_svg(m, 1.5)
        assert svg.count("<circle") == 3
        assert ">First</text>" in svg and "Second" not in svg
        # Before the first chapter, the bar is there but has no label
        early = snap_svg(m, 0.5)
        assert "First" not in early
        assert ET.fromstring(early).get("height") == ET.fromstring(svg).get("height")

    def test_annotations_only_when_asked_and_showing(self):
        m = _manifest({"annotations": [{"at": 1, "duration": 2, "text": "Look here"}]})
        assert "Look here" not in snap_svg(m, 1.5)
        shown = snap_svg(m, 1.5, annotations=True)
        assert "Look here" in shown
        assert '<g opacity="0"' not in shown
        assert "Look here" not in snap_svg(m, 3.5, annotations=True)

    def test_pair_sides(self):
        m = _manifest({"settings": {"theme": {"light": "github-light", "dark": "dracula"}}})
        light, dark = snap_svg(m, 1), snap_svg(m, 1, dark=True)
        assert m.screen.bg in light and m.dark.bg in dark
        assert m.dark.bg not in light

    def test_font_file(self, tmp_path):
        font = tmp_path / "f.woff2"
        font.write_bytes(b"font")
        assert "@font-face" in snap_svg(_manifest(), 0, font_file=font)


class TestRasterize:
    def test_no_rasterizer(self, monkeypatch, tmp_path):
        monkeypatch.setattr(snap_mod, "find_rasterizer", lambda: None)
        with pytest.raises(SnapError, match="needs rsvg-convert or resvg"):
            rasterize(snap_svg(_manifest(), 0), tmp_path / "x.png")

    def test_failure_is_reported(self, monkeypatch, tmp_path):
        tool = tmp_path / "rsvg-convert"
        tool.write_text("#!/bin/sh\necho broken >&2\nexit 3\n")
        tool.chmod(0o755)
        monkeypatch.setattr(snap_mod, "find_rasterizer", lambda: str(tool))
        with pytest.raises(SnapError, match="rsvg-convert couldn't make the PNG: broken"):
            rasterize(snap_svg(_manifest(), 0), tmp_path / "x.png")

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("rsvg-convert", "--zoom 1.5 --output OUT IN"),
            ("resvg", "--zoom 1.5 IN OUT"),
        ],
    )
    def test_arguments(self, monkeypatch, tmp_path, name, expected):
        tool = tmp_path / name
        log = tmp_path / "args"
        tool.write_text(f'#!/bin/sh\necho "$@" > {log}\n')
        tool.chmod(0o755)
        monkeypatch.setattr(snap_mod, "find_rasterizer", lambda: str(tool))
        out = tmp_path / "x.png"
        rasterize(snap_svg(_manifest(), 0), out, scale=1.5)
        args = log.read_text().split()
        source = next(a for a in args if a.endswith("snap.svg"))
        got = " ".join(args).replace(source, "IN").replace(str(out), "OUT")
        assert got == expected

    @pytest.mark.skipif(find_rasterizer() is None, reason="no rsvg-convert or resvg")
    def test_png_at_scale(self, tmp_path):
        svg = snap_svg(_manifest(), 0)
        width = float(ET.fromstring(svg).get("width"))
        out = tmp_path / "x.png"
        rasterize(svg, out, scale=2)
        data = out.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        png_w, _ = struct.unpack(">II", data[16:24])
        assert abs(png_w - width * 2) <= 1


class TestCli:
    def test_default_output(self, tmp_path):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "snap", str(source)])
        assert result.exit_code == 0, result.output
        out = tmp_path / "demo-snap.svg"
        assert _screen(out.read_text())[-2] == "$ three"
        assert "At 4.00s of 4.00s" in result.output

    def test_at_and_output(self, tmp_path):
        source = _write(tmp_path)
        out = tmp_path / "sub" / "shot.svg"
        result = CliRunner().invoke(
            cli, ["termshow", "snap", str(source), "--at", "1.5", "-o", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert _screen(out.read_text()) == ["$ one", "$"]

    def test_script_and_no_script(self, tmp_path):
        source = _write(tmp_path, "settings:\n  speed: 2\n")
        result = CliRunner().invoke(cli, ["termshow", "snap", str(source), "--at", "1"])
        assert result.exit_code == 0, result.output
        assert _screen((tmp_path / "demo-snap.svg").read_text())[-2] == "$ two"
        result = CliRunner().invoke(
            cli, ["termshow", "snap", str(source), "--at", "1", "--no-script"]
        )
        assert result.exit_code == 0, result.output
        assert _screen((tmp_path / "demo-snap.svg").read_text())[-2] == "$ one"

    def test_chapter(self, tmp_path):
        source = _write(
            tmp_path, "chapters:\n  - at: 0\n    label: Start\n  - at: 2\n    label: More\n"
        )
        result = CliRunner().invoke(cli, ["termshow", "snap", str(source), "--chapter", "start"])
        assert result.exit_code == 0, result.output
        assert _screen((tmp_path / "demo-snap.svg").read_text()) == ["$ one", "$"]

    def test_pair_writes_two_files_and_snippet(self, tmp_path):
        source = _write(tmp_path, "settings:\n  theme: auto\n")
        result = CliRunner().invoke(cli, ["termshow", "snap", str(source)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "demo-snap-light.svg").exists()
        assert (tmp_path / "demo-snap-dark.svg").exists()
        assert 'srcset="demo-snap-dark.svg"' in result.output

    def test_png_without_rasterizer(self, tmp_path, monkeypatch):
        monkeypatch.setattr(snap_mod, "find_rasterizer", lambda: None)
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "snap", str(source), "--png"])
        assert result.exit_code == 1
        assert "needs rsvg-convert or resvg" in result.output
        assert not (tmp_path / "demo-snap.png").exists()

    @pytest.mark.skipif(find_rasterizer() is None, reason="no rsvg-convert or resvg")
    @pytest.mark.parametrize(
        "args, name", [(["--png"], "demo-snap.png"), (["-o", "s.png"], "s.png")]
    )
    def test_png(self, tmp_path, monkeypatch, args, name):
        monkeypatch.chdir(tmp_path)
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "snap", str(source), *args, "--scale", "1"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / name).read_bytes()[:4] == b"\x89PNG"

    @pytest.mark.parametrize(
        "args, message",
        [
            (["--at", "1", "--end"], "only one of --at, --chapter, and --end"),
            (["--at", "1", "--chapter", "x"], "only one of --at, --chapter, and --end"),
            (["-o", "x.jpg"], "must end in .svg or .png"),
            (["--png", "-o", "x.svg"], "-o ends in .svg"),
            (["--scale", "2"], "--scale only applies to PNG output"),
            (["--png", "--scale", "0"], "must be more than 0"),
            (["--at", "99"], "past the end"),
            (["--chapter", "x"], "no chapter is labeled 'x'"),
        ],
    )
    def test_usage_errors(self, tmp_path, args, message):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "snap", str(source), *args])
        assert result.exit_code == 2
        assert message in result.output

    def test_font_file_is_svg_only(self, tmp_path):
        source = _write(tmp_path)
        font = tmp_path / "f.woff2"
        font.write_bytes(b"font")
        result = CliRunner().invoke(
            cli, ["termshow", "snap", str(source), "--png", "--font-file", str(font)]
        )
        assert result.exit_code == 2
        assert "--font-file only applies to SVG output" in result.output
