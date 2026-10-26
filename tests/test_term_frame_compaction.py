"""Tests for the compact (version 2) termshow manifest."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player import generate_manifest
from great_docs._term_player.manifest import Manifest
from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import Script
from great_docs._term_player.themes import get_theme
from great_docs.cli import cli

_PLAYER_JS = (
    Path(__file__).resolve().parents[1]
    / "great_docs"
    / "assets"
    / "_extensions"
    / "termshow"
    / "termshow.js"
)


def _recording() -> Recording:
    """A recording with repeated screens, styles, colors and awkward text."""
    return Recording(
        term=TermInfo(cols=40, rows=6),
        events=[
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.5, code="o", data="echo '<b>&</b>'\r\n"),
            Event(time=1.0, code="o", data="<b>&</b>\r\n$ "),
            Event(time=3.0, code="o", data="\x1b[1;31mbold red\x1b[0m \x1b[4munder\x1b[0m\r\n"),
            Event(time=3.5, code="o", data="\x1b[7minverse\x1b[0m \x1b[42;30m ok \x1b[0m\r\n"),
            Event(time=4.0, code="o", data="\x1b[3;2mitalic dim\x1b[0m café ✓ 日本\r\n$ "),
            Event(time=9.0, code="o", data=""),
        ],
    )


def _render(tmp_path: Path, **kwargs) -> tuple[Manifest, dict]:
    manifest = generate_manifest(_recording(), output_dir=tmp_path, **kwargs)
    return manifest, json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))


class TestFormat:
    def test_version_and_screen(self, tmp_path: Path):
        _, data = _render(tmp_path)
        assert data["version"] == 2
        assert set(data["screen"]) == {
            "font_family",
            "font_size",
            "line_height",
            "padding",
            "fg",
            "bg",
        }
        assert "deltas" not in data

    def test_identical_screens_share_a_frame(self, tmp_path: Path):
        """Interval keyframes during idle stretches point at one frame."""
        manifest, data = _render(tmp_path)
        assert len(data["frames"]) < len(data["keyframes"])
        idle = [kf for kf in manifest.keyframes if 5.0 <= kf.time <= 9.0]
        assert len({kf.frame for kf in idle}) == 1

    def test_keyframes_kept_for_every_time(self, tmp_path: Path):
        manifest, _ = _render(tmp_path)
        times = [kf.time for kf in manifest.keyframes]
        assert times == sorted(times)
        assert {0.0, 2.0, 4.0, 6.0, 8.0} <= set(times)

    def test_identical_rows_are_stored_once(self, tmp_path: Path):
        _, data = _render(tmp_path)
        rows = [i for frame in data["frames"] for i in frame["lines"]]
        assert len(data["lines"]) < len(rows)
        assert all(len(frame["lines"]) == 6 for frame in data["frames"])

    def test_one_svg_file_per_unique_frame(self, tmp_path: Path):
        manifest, data = _render(tmp_path)
        files = sorted(p.name for p in tmp_path.glob("frame-*.svg"))
        assert len(files) == len(data["frames"])
        assert {kf.file for kf in manifest.keyframes} == set(files)
        for kf in manifest.keyframes:
            assert kf.file == f"frame-{kf.frame:03d}.svg"

    def test_rerender_clears_stale_frames(self, tmp_path: Path):
        (tmp_path / "frame-999.svg").write_text("<svg/>")
        _render(tmp_path)
        assert not (tmp_path / "frame-999.svg").exists()

    def test_span_encoding(self, tmp_path: Path):
        _, data = _render(tmp_path)
        text_spans = [span for line in data["lines"] for span in line[1]]
        bg_spans = [span for line in data["lines"] for span in line[0]]
        assert all(len(span) in (3, 4) for span in text_spans)
        assert any(len(span) == 4 and "gd-tp-bold" in span[3] for span in text_spans)
        assert all(len(span) == 3 and isinstance(span[1], int) for span in bg_spans)

    def test_cursor_recorded(self, tmp_path: Path):
        _, data = _render(tmp_path)
        assert data["frames"][-1]["cursor"] == [5, 2]

    def test_cursor_omitted_when_hidden(self, tmp_path: Path):
        manifest = generate_manifest(_recording(), Script(show_cursor=False), output_dir=tmp_path)
        assert all(frame.cursor is None for frame in manifest.frames)
        assert "cursor" not in (tmp_path / "manifest.json").read_text()

    def test_keyframe_includes_event_at_its_time(self, tmp_path: Path):
        """Float error in accumulated delays mustn't push an event past its own keyframe."""
        recording = Recording(
            term=TermInfo(cols=20, rows=2),
            events=[Event(time=0.0, code="o", data="$ ")]
            + [
                Event(time=t, code="o", data=ch)
                for t, ch in zip([1.0 + 0.07 + 0.07, 1.0 + 0.07 + 0.07 + 0.07], "ab")
            ],
        )
        assert recording.events[1].time != round(recording.events[1].time, 3)
        manifest = generate_manifest(recording, output_dir=tmp_path)
        for kf, expected in zip(manifest.keyframes[-2:], ["$ a", "$ ab"]):
            frame = manifest.frames[kf.frame]
            assert "".join(span[1] for span in manifest.lines[frame.lines[0]][1]) == expected

    def test_resized_frames_record_their_size(self, tmp_path: Path):
        recording = Recording(
            term=TermInfo(cols=20, rows=4),
            events=[
                Event(time=0.0, code="o", data="small"),
                Event(time=1.0, code="r", data="30x5"),
                Event(time=1.5, code="o", data="!"),
            ],
        )
        manifest = generate_manifest(recording, output_dir=tmp_path)
        assert manifest.frames[0].size is None
        assert manifest.frames[-1].size == (30, 5)


class TestJsonEncoding:
    def test_compact(self, tmp_path: Path):
        manifest, _ = _render(tmp_path)
        assert "\n" not in manifest.to_json()
        assert ", " not in manifest.to_json()[:200]

    def test_script_close_tag_is_escaped(self, tmp_path: Path):
        """Terminal text can't end the inline `<script>` element early."""
        manifest, data = _render(tmp_path)
        text = manifest.to_json()
        assert "</" not in text
        assert any("<b>&</b>" in span[1] for line in data["lines"] for span in line[1])

    def test_non_ascii_kept_verbatim(self, tmp_path: Path):
        manifest, _ = _render(tmp_path)
        assert "café" in manifest.to_json()


class TestStats:
    def test_counts(self, tmp_path: Path):
        manifest, data = _render(tmp_path)
        stats = manifest.stats
        assert stats.keyframes == len(data["keyframes"])
        assert stats.frames == len(data["frames"])
        assert stats.lines == len(data["lines"])
        assert stats.manifest_bytes == len((tmp_path / "manifest.json").read_bytes())

    def test_stats_not_serialized(self, tmp_path: Path):
        _, data = _render(tmp_path)
        assert "stats" not in data

    def test_cli_reports_payload(self, tmp_path: Path):
        source = tmp_path / "demo.termshow"
        header = {"version": 1, "format": "termshow", "term": {"cols": 40, "rows": 6}}
        events = [[0.0, "o", "$ "], [0.5, "o", "ls\r\n"], [9.0, "o", "$ "]]
        source.write_text("\n".join(json.dumps(x) for x in [header, *events]), encoding="utf-8")
        result = CliRunner().invoke(cli, ["termshow", "render", str(source)])
        assert result.exit_code == 0, result.output
        assert "unique screens" in result.output
        assert "Page payload:" in result.output
        assert "→" not in result.output and "smaller" not in result.output


# The player draws v2 frames itself; its output must match the SVG files
# written by Python so highlights, snippets and posters line up.
_PARITY_JS = r"""
const fs = require('fs');
const vm = require('vm');
const [playerPath, manifestPath] = process.argv.slice(1);
const window = { location: { protocol: 'https:' } };
const document = {
  readyState: 'complete',
  querySelectorAll: () => [],
  body: {},
  addEventListener: () => {},
};
class MutationObserver { observe() {} }
vm.runInNewContext(fs.readFileSync(playerPath, 'utf8'), { window, document, MutationObserver });
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const out = manifest.frames.map((_, i) => window.Termshow.renderFrame(manifest, i));
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
class TestPlayerParity:
    def _js_frames(self, out: Path) -> list[str]:
        result = subprocess.run(
            ["node", "-e", _PARITY_JS, str(_PLAYER_JS), str(out / "manifest.json")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return json.loads(result.stdout)

    @pytest.mark.parametrize(
        "script",
        [
            None,
            Script(font_family="Courier", line_height=1.3),
            Script(theme_name="dracula", theme=get_theme("dracula"), show_cursor=False),
        ],
        ids=["default", "font-and-line-height", "no-cursor"],
    )
    def test_js_matches_python_svg(self, tmp_path: Path, script: Script | None):
        manifest = generate_manifest(_recording(), script, output_dir=tmp_path)
        js_frames = self._js_frames(tmp_path)
        assert len(js_frames) == len(manifest.frames)
        for i, svg in enumerate(js_frames):
            assert svg == (tmp_path / f"frame-{i:03d}.svg").read_text(encoding="utf-8"), i

    def test_js_matches_after_resize(self, tmp_path: Path):
        recording = Recording(
            term=TermInfo(cols=20, rows=4),
            events=[
                Event(time=0.0, code="o", data="small"),
                Event(time=1.0, code="r", data="30x5"),
                Event(time=1.5, code="o", data="\x1b[44m wide \x1b[0m"),
            ],
        )
        generate_manifest(recording, output_dir=tmp_path)
        for i, svg in enumerate(self._js_frames(tmp_path)):
            assert svg == (tmp_path / f"frame-{i:03d}.svg").read_text(encoding="utf-8")
