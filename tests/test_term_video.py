"""Tests for GIF, MP4, and WebM export (`great-docs termshow export --gif/--mp4/--webm`)."""

from __future__ import annotations

import json
import shlex
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player import apply_script, generate_manifest
from great_docs._term_player import snap as snap_mod
from great_docs._term_player import video as video_mod
from great_docs._term_player.parser import parse_termshow_str
from great_docs._term_player.script import _parse_script_data
from great_docs._term_player.snap import find_rasterizer, rasterize, snap_svg
from great_docs._term_player.video import VideoError, export_video, find_ffmpeg, video_stills
from great_docs.cli import cli

# Screens change at 0s, 1s, 2s and 4s (delays are relative to the previous event)
EVENTS = [
    [0.0, "o", "$ "],
    [1.0, "o", "one\r\n$ "],
    [1.0, "o", "two\r\n$ "],
    [2.0, "o", "three\r\n$ "],
]

needs_tools = pytest.mark.skipif(
    find_ffmpeg() is None or find_rasterizer() is None, reason="needs ffmpeg and rsvg-convert"
)


def _recording_text(events=EVENTS) -> str:
    header = {"version": 1, "format": "termshow", "term": {"cols": 30, "rows": 5}}
    return "\n".join([json.dumps(header)] + [json.dumps(e) for e in events])


def _manifest(script: dict | None = None, events=EVENTS):
    recording = parse_termshow_str(_recording_text(events))
    script_obj = _parse_script_data(script) if script is not None else None
    if script_obj:
        recording = apply_script(recording, script_obj)
    return generate_manifest(recording, script_obj)


def _write(tmp_path: Path, script: str | None = None) -> Path:
    source = tmp_path / "demo.termshow"
    source.write_text(_recording_text(), encoding="utf-8")
    if script is not None:
        (tmp_path / "demo.termshow.yml").write_text(script, encoding="utf-8")
    return source


def _timeline(stills) -> list[tuple[float, float]]:
    return [(round(s.time, 3), round(s.duration, 3)) for s in stills]


def _png(width: int = 3, height: int = 2) -> bytes:
    """A blank PNG of a given size."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"".join(b"\0" + b"\0" * 3 * width for _ in range(height)))
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")
    )


@pytest.fixture
def fake_tools(tmp_path, monkeypatch):
    """A rasterizer that writes blank PNGs, and an `ffmpeg` that records how it was called.

    Returns a function giving the last call's arguments and the frame list it was given.
    """
    drawn = []

    def fake_rasterize(svg, output, *, scale=1.0, background=None):
        drawn.append((svg, scale, background))
        Path(output).write_bytes(_png(int(100 * scale) + 1, int(50 * scale)))

    log = tmp_path / "ffmpeg-args"
    frames = tmp_path / "ffmpeg-frames"
    tool = tmp_path / "ffmpeg"
    tool.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$@" > {shlex.quote(str(log))}\n'
        f"cp frames.txt {shlex.quote(str(frames))}\n"
        'for last; do :; done\nprintf "out" > "$last"\n'
    )
    tool.chmod(0o755)
    monkeypatch.setattr(video_mod, "rasterize", fake_rasterize)
    monkeypatch.setattr(video_mod, "find_ffmpeg", lambda: str(tool))

    def last_call():
        return log.read_text().splitlines(), frames.read_text().splitlines(), drawn

    return last_call


def _gif_delays(data: bytes) -> list[float]:
    """Each frame's delay in a GIF, in seconds, read from its graphic control extensions."""
    delays = []
    at = data.find(b"\x21\xf9\x04")
    while at != -1:
        delays.append(struct.unpack("<H", data[at + 4 : at + 6])[0] / 100)
        at = data.find(b"\x21\xf9\x04", at + 1)
    return delays


class TestStills:
    def test_one_per_screen_with_its_length(self):
        stills = video_stills(_manifest(), fps=20, end_pause=0)
        # The last screen comes at the very end, so it shows for one frame
        assert _timeline(stills) == [(0, 1.0), (1, 1.0), (2, 2.0), (4, 0.05)]

    def test_end_pause_holds_the_last_screen(self):
        stills = video_stills(_manifest(), fps=20, end_pause=2)
        assert _timeline(stills)[-1] == (4, 2.05)

    def test_lengths_fall_on_the_frame_grid(self):
        events = [[0, "o", "a"], [0.33, "o", "b"], [0.33, "o", "c"], [0.34, "o", "d"]]
        stills = video_stills(_manifest(events=events), fps=10, end_pause=0)
        assert [s.duration for s in stills] == pytest.approx([0.3, 0.4, 0.3, 0.1])
        # Rounding doesn't add up: the total stays on the timeline
        assert sum(s.duration for s in stills) == pytest.approx(1.1)

    def test_stretches_shorter_than_a_frame_are_skipped(self):
        events = [[0, "o", "a"], [1, "o", "b"], [0.01, "o", "c"], [1, "o", "d"]]
        stills = video_stills(_manifest(events=events), fps=10, end_pause=0)
        assert _timeline(stills) == [(0, 1.0), (1.01, 1.0), (2.01, 0.1)]

    def test_max_idle_shortens_pauses(self):
        stills = video_stills(_manifest(), fps=20, end_pause=1, max_idle=0.5)
        # The end pause isn't shortened
        assert _timeline(stills) == [(0, 0.5), (1, 0.5), (2, 0.5), (4, 1.05)]

    def test_annotations_and_chapters_start_stretches(self):
        script = {
            "annotations": [{"at": 0.5, "duration": 0.25, "text": "Hi"}],
            "chapters": [{"at": 2.5, "label": "Later"}],
        }
        m = _manifest(script)
        times = [t for t, _ in _timeline(video_stills(m, fps=20, end_pause=0))]
        assert times == [0, 0.5, 0.75, 1, 2, 2.5, 4]
        times = [t for t, _ in _timeline(video_stills(m, fps=20, annotations=False))]
        assert 0.5 not in times and 2.5 in times

    def test_cuts_and_speed_are_on_the_playback_timeline(self):
        m = _manifest({"cuts": [{"from": 2, "to": 3}], "settings": {"speed": 2}})
        assert _timeline(video_stills(m, fps=20, end_pause=0)) == [
            (0, 0.5),
            (0.5, 0.5),
            (1, 0.5),
            (1.5, 0.05),
        ]

    def test_fps_must_be_positive(self):
        with pytest.raises(ValueError, match="more than 0"):
            video_stills(_manifest(), fps=0)


class TestFrames:
    def test_drawn_at_one_size(self, fake_tools, tmp_path):
        # A resize makes the second screen bigger; both are drawn at the bigger size
        events = [[0, "o", "a"], [1, "r", "40x8"], [0, "o", "b"]]
        m = _manifest(events=events)
        export_video(m, tmp_path / "x.gif", "gif")
        _, _, drawn = fake_tools()
        widths = {ET.fromstring(svg).get("width") for svg, _, _ in drawn}
        assert widths == {ET.fromstring(snap_svg(m, 0, cells=(40, 8))).get("width")}
        assert ET.fromstring(snap_svg(m, 0)).get("width") not in widths

    def test_rasterizer_gets_the_background(self, monkeypatch, tmp_path):
        log = tmp_path / "args"
        for name, flag in (("rsvg-convert", "--background-color"), ("resvg", "--background")):
            tool = tmp_path / name
            tool.write_text(f'#!/bin/sh\necho "$@" > {log}\n')
            tool.chmod(0o755)
            monkeypatch.setattr(snap_mod, "find_rasterizer", lambda tool=tool: str(tool))
            rasterize(snap_svg(_manifest(), 0), tmp_path / "x.png", background="#123456")
            assert f"{flag} #123456" in log.read_text()


class TestExport:
    def test_gif(self, fake_tools, tmp_path):
        out = tmp_path / "demo.gif"
        result = export_video(_manifest(), out, "gif")
        argv, frames, drawn = fake_tools()
        assert out.read_text() == "out"
        assert argv[-1] == str(out.resolve())
        assert "palettegen" in " ".join(argv) and argv[argv.index("-loop") + 1] == "0"
        assert "-t" not in argv
        # One image per screen, each listed with its duration, and the last listed again
        assert frames[0] == "ffconcat version 1.0"
        assert [line for line in frames if line.startswith("duration")] == [
            "duration 1.000000",
            "duration 1.000000",
            "duration 2.000000",
            "duration 2.050000",
        ]
        assert frames[-1] == frames[-3]
        assert result.duration == pytest.approx(6.05)
        assert (result.stills, result.images) == (4, 4)
        assert (result.width, result.height) == (101, 50)
        assert {(scale, bg) for _, scale, bg in drawn} == {(1.0, _manifest().screen.bg)}

    def test_gif_without_loop(self, fake_tools, tmp_path):
        export_video(_manifest(), tmp_path / "x.gif", "gif", loop=False)
        argv, _, _ = fake_tools()
        assert argv[argv.index("-loop") + 1] == "-1"

    @pytest.mark.parametrize("fmt, codec", [("mp4", "libx264"), ("webm", "libvpx-vp9")])
    def test_video(self, fake_tools, tmp_path, fmt, codec):
        result = export_video(_manifest(), tmp_path / f"x.{fmt}", fmt, end_pause=0)
        argv, _, drawn = fake_tools()
        assert argv[argv.index("-c:v") + 1] == codec
        # The last screen shows for one frame
        assert argv[argv.index("-t") + 1] == "4.033333"
        assert "fps=30,pad=ceil(iw/2)*2:ceil(ih/2)*2" in argv[argv.index("-vf") + 1]
        # Twice the size, made even
        assert drawn[0][1] == 2.0
        assert (result.width, result.height) == (202, 100)

    def test_repeated_screens_share_an_image(self, fake_tools, tmp_path):
        events = [[0, "o", "a"], [1, "o", "\rb"], [1, "o", "\ra"]]
        result = export_video(_manifest(events=events), tmp_path / "x.gif", "gif")
        _, frames, drawn = fake_tools()
        assert (result.stills, result.images, len(drawn)) == (3, 2, 2)
        files = [line for line in frames if line.startswith("file")]
        assert files[0] == files[2]

    def test_unchanged_screens_are_merged(self, fake_tools, tmp_path):
        # Output that redraws the same text doesn't change the screen
        events = [[0, "o", "a"], [1, "o", "\ra"], [1, "o", "b"]]
        m = _manifest(events=events)
        assert len(video_stills(m, fps=20, end_pause=0)) == 3
        result = export_video(m, tmp_path / "x.gif", "gif", end_pause=0)
        _, frames, _ = fake_tools()
        assert result.stills == 2
        assert "duration 2.000000" in frames

    def test_dark_side(self, fake_tools, tmp_path):
        m = _manifest({"settings": {"theme": "auto"}})
        export_video(m, tmp_path / "x.gif", "gif", dark=True)
        _, _, drawn = fake_tools()
        assert drawn[0][2] == m.dark.bg and m.dark.bg in drawn[0][0]

    def test_without_ffmpeg(self, monkeypatch, tmp_path):
        monkeypatch.setattr(video_mod, "find_ffmpeg", lambda: None)
        with pytest.raises(VideoError, match="GIF export needs ffmpeg"):
            export_video(_manifest(), tmp_path / "x.gif", "gif")

    def test_without_a_rasterizer(self, fake_tools, monkeypatch, tmp_path):
        monkeypatch.setattr(video_mod, "rasterize", rasterize)
        monkeypatch.setattr(snap_mod, "find_rasterizer", lambda: None)
        with pytest.raises(VideoError, match="MP4 export needs rsvg-convert or resvg"):
            export_video(_manifest(), tmp_path / "x.mp4", "mp4")

    def test_ffmpeg_failure_is_reported(self, fake_tools, monkeypatch, tmp_path):
        tool = tmp_path / "broken-ffmpeg"
        tool.write_text("#!/bin/sh\necho 'Unknown encoder' >&2\nexit 1\n")
        tool.chmod(0o755)
        monkeypatch.setattr(video_mod, "find_ffmpeg", lambda: str(tool))
        with pytest.raises(VideoError, match="couldn't make the WEBM: Unknown encoder"):
            export_video(_manifest(), tmp_path / "x.webm", "webm")

    def test_unknown_format(self, tmp_path):
        with pytest.raises(ValueError, match="unknown format 'avi'"):
            export_video(_manifest(), tmp_path / "x.avi", "avi")

    @needs_tools
    def test_real_gif(self, tmp_path):
        out = tmp_path / "x.gif"
        result = export_video(_manifest(), out, "gif", end_pause=1)
        data = out.read_bytes()
        assert data[:6] == b"GIF89a"
        assert struct.unpack("<HH", data[6:10]) == (result.width, result.height)
        # Each screen keeps its own delay, to the hundredth of a second (the very last frame is
        # a short repeat)
        assert _gif_delays(data)[:4] == pytest.approx([1.0, 1.0, 2.0, 1.05], abs=0.011)

    @needs_tools
    @pytest.mark.parametrize("fmt, magic", [("mp4", b"ftyp"), ("webm", b"\x1a\x45\xdf\xa3")])
    def test_real_video(self, tmp_path, fmt, magic):
        out = tmp_path / f"x.{fmt}"
        export_video(_manifest(), out, fmt, scale=1)
        assert magic in out.read_bytes()[:12]


class TestCli:
    def test_gif(self, fake_tools, tmp_path):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--gif"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "demo.gif").exists()
        assert "✓ Exported" in result.output and "101×50" in result.output
        assert "Frames: 4 | Unique images: 4" in result.output

    @pytest.mark.parametrize("name, codec", [("x.mp4", "libx264"), ("x.webm", "libvpx-vp9")])
    def test_format_from_the_output_name(self, fake_tools, tmp_path, name, codec):
        source = _write(tmp_path)
        out = tmp_path / name
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "-o", str(out)])
        assert result.exit_code == 0, result.output
        argv, _, _ = fake_tools()
        assert argv[argv.index("-c:v") + 1] == codec

    def test_options(self, fake_tools, tmp_path):
        source = _write(tmp_path, "annotations:\n  - at: 1\n    duration: 1\n    text: Hi\n")
        args = ["--gif", "--fps", "10", "--scale", "1.5", "--max-idle", "0.5", "--no-loop"]
        result = CliRunner().invoke(
            cli, ["termshow", "export", str(source), *args, "--no-annotations"]
        )
        assert result.exit_code == 0, result.output
        argv, frames, drawn = fake_tools()
        assert argv[argv.index("-loop") + 1] == "-1"
        assert drawn[0][1] == 1.5
        assert not any("Hi" in svg for svg, _, _ in drawn)
        assert "duration 0.500000" in frames

    def test_pair_writes_two_files_and_snippet(self, fake_tools, tmp_path):
        source = _write(tmp_path, "settings:\n  theme: auto\n")
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--gif"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "demo-light.gif").exists() and (tmp_path / "demo-dark.gif").exists()
        assert 'srcset="demo-dark.gif"' in result.output
        # A video can't go in a <picture>
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--mp4"])
        assert (tmp_path / "demo-dark.mp4").exists() and "<picture>" not in result.output

    def test_size_warning(self, fake_tools, tmp_path, monkeypatch):
        monkeypatch.setattr(video_mod, "SIZE_WARNING_BYTES", 1)
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--gif"])
        assert "GitHub won't take in an issue or pull request" in result.stderr

    def test_missing_ffmpeg(self, monkeypatch, tmp_path):
        monkeypatch.setattr(video_mod, "find_ffmpeg", lambda: None)
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--webm"])
        assert result.exit_code == 1
        assert "WEBM export needs ffmpeg" in result.output

    @pytest.mark.parametrize(
        "args, message",
        [
            (["--gif", "-o", "x.mp4"], "--gif writes a .gif file, but -o ends in .mp4"),
            (["--fps", "10"], "--fps only applies to --gif, --mp4 and --webm"),
            (["--cast", "--scale", "2"], "--scale only applies to --gif, --mp4 and --webm"),
            (["--mp4", "--no-loop"], "--no-loop only applies to --svg and --gif"),
            (["--gif", "--chapter-cards"], "--chapter-cards only applies to --svg"),
            (["--webm", "--v2"], "--v2 only applies to --cast"),
            (["--gif", "--fps", "0"], "0 is not in the range"),
            (["--gif", "--scale", "0"], "must be more than 0"),
            (["--gif", "--max-idle", "-1"], "must be more than 0"),
        ],
    )
    def test_usage_errors(self, tmp_path, args, message):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), *args])
        assert result.exit_code == 2
        assert message in result.output

    @needs_tools
    def test_real_gif(self, tmp_path):
        source = _write(tmp_path)
        out = tmp_path / "x.gif"
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert out.read_bytes()[:6] == b"GIF89a"
