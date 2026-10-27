"""Tests for in-terminal playback (`termshow play`)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.playback import play_recording
from great_docs.cli import cli


def _recording() -> Recording:
    return Recording(
        term=TermInfo(cols=80, rows=24),
        events=[
            Event(time=0.5, code="o", data="$ "),
            Event(time=1.0, code="i", data="l"),
            Event(time=1.5, code="o", data="ls\r\n"),
            Event(time=1.5, code="m", data="Chapter"),
            Event(time=3.5, code="o", data="done\r\n"),
        ],
    )


class TestPlayRecording:
    def test_writes_output_events_in_order(self):
        out = io.StringIO()
        play_recording(_recording(), out=out, sleep=lambda _: None)
        assert out.getvalue().startswith("$ ls\r\ndone\r\n")

    def test_skips_non_output_events(self):
        out = io.StringIO()
        play_recording(_recording(), out=out, sleep=lambda _: None)
        assert "Chapter" not in out.getvalue()
        assert out.getvalue().startswith("$ ls")  # the "i" keystroke isn't echoed

    def test_sleeps_follow_event_timing(self):
        sleeps: list[float] = []
        play_recording(_recording(), out=io.StringIO(), sleep=sleeps.append)
        assert sleeps == pytest.approx([0.5, 1.0, 2.0])

    def test_speed_scales_sleeps(self):
        sleeps: list[float] = []
        play_recording(_recording(), speed=2.0, out=io.StringIO(), sleep=sleeps.append)
        assert sleeps == pytest.approx([0.25, 0.5, 1.0])

    def test_returns_duration(self):
        assert play_recording(_recording(), out=io.StringIO(), sleep=lambda _: None) == 3.5

    def test_resets_terminal_even_when_interrupted(self):
        out = io.StringIO()

        def interrupt(_):
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            play_recording(_recording(), out=out, sleep=interrupt)
        assert out.getvalue().endswith("\x1b[0m\x1b[?25h")

    @pytest.mark.parametrize("speed", [0, -1])
    def test_rejects_non_positive_speed(self, speed):
        with pytest.raises(ValueError, match="greater than 0"):
            play_recording(_recording(), speed=speed, out=io.StringIO())


def _write_termshow(tmp_path: Path) -> Path:
    header = {"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 24}}
    events = [[0.0, "o", "first\r\n"], [1.0, "o", "second\r\n"], [1.0, "o", "third\r\n"]]
    path = tmp_path / "demo.termshow"
    path.write_text("\n".join(json.dumps(x) for x in [header, *events]), encoding="utf-8")
    return path


class TestPlayCommand:
    def _run(self, args: list[str]):
        with patch("great_docs._term_player.playback.time.sleep"):
            return CliRunner().invoke(cli, ["termshow", "play", *args])

    def test_plays_recording(self, tmp_path: Path):
        source = _write_termshow(tmp_path)
        result = self._run([str(source)])
        assert result.exit_code == 0, result.output
        assert "first" in result.output and "third" in result.output

    def test_applies_companion_script_cuts(self, tmp_path: Path):
        source = _write_termshow(tmp_path)
        (tmp_path / "demo.termshow.yml").write_text(
            "cuts:\n  - from: 0.5\n    to: 1.5\n", encoding="utf-8"
        )
        with patch("great_docs._term_player.playback.play_recording") as play:
            result = self._run([str(source)])
        assert result.exit_code == 0, result.output
        # "second" is printed during the cut, so it's shown at the cut's start
        recording = play.call_args.args[0]
        assert [e.time for e in recording.events] == pytest.approx([0.0, 0.5, 1.0])

    def test_no_script_ignores_companion(self, tmp_path: Path):
        source = _write_termshow(tmp_path)
        (tmp_path / "demo.termshow.yml").write_text(
            "cuts:\n  - from: 0.5\n    to: 1.5\n", encoding="utf-8"
        )
        result = self._run([str(source), "--no-script"])
        assert result.exit_code == 0, result.output
        assert "second" in result.output

    def test_plays_asciicast(self, tmp_path: Path):
        cast = tmp_path / "demo.cast"
        cast.write_text(
            "\n".join(
                json.dumps(x) for x in [{"version": 2, "width": 80, "height": 24}, [0.1, "o", "hi"]]
            ),
            encoding="utf-8",
        )
        result = self._run([str(cast)])
        assert result.exit_code == 0, result.output
        assert "hi" in result.output

    def test_rejects_bad_speed(self, tmp_path: Path):
        result = self._run([str(_write_termshow(tmp_path)), "--speed", "0"])
        assert result.exit_code != 0
        assert "greater than 0" in result.output

    def test_listed_in_group_help(self):
        result = CliRunner().invoke(cli, ["termshow", "--help"])
        assert "play" in result.output
