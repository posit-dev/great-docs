"""Tests for asciicast export (`great-docs termshow export --cast`)."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from click.testing import CliRunner

from great_docs._term_player.cast import export_asciicast, left_out
from great_docs._term_player.parser import Theme, parse_asciicast_str, parse_termshow_str
from great_docs._term_player.script import _parse_script_data
from great_docs._term_player.themes import resolve_theme_pair
from great_docs.cli import cli

# Output at 0s, 1s, 3s and 4s, then the exit (delays are relative to the previous event)
EVENTS = [
    [0.0, "o", "$ "],
    [1.0, "o", "echo hi\r\nhi\r\n"],
    [2.0, "o", "$ "],
    [0.5, "r", "50x8"],
    [0.5, "o", "exit\r\n"],
    [0.25, "x", "0"],
]


def _recording(events=EVENTS, title: str = "Demo", timestamp: int | None = None):
    header = {
        "version": 1,
        "format": "termshow",
        "term": {"cols": 40, "rows": 6, "type": "xterm-256color"},
        "title": title,
    }
    if timestamp is not None:
        header["timestamp"] = timestamp
    text = "\n".join([json.dumps(header)] + [json.dumps(e) for e in events])
    return parse_termshow_str(text)


def _lines(text: str) -> tuple[dict, list[list]]:
    header, *events = (json.loads(line) for line in text.splitlines())
    return header, events


def _times(recording, code: str = "o") -> list[float]:
    return [round(e.time, 6) for e in recording.events if e.code == code]


class TestRoundTrip:
    @pytest.mark.parametrize("version", [2, 3])
    def test_events_survive(self, version):
        recording = _recording(timestamp=1700000000)
        back = parse_asciicast_str(export_asciicast(recording, version=version))
        assert back.version == version
        assert (back.term.cols, back.term.rows, back.term.type) == (40, 6, "xterm-256color")
        assert back.title == "Demo"
        assert back.timestamp == 1700000000
        assert _times(back) == [0.0, 1.0, 3.0, 4.0]
        assert [e.data for e in back.events if e.code == "o"] == [
            "$ ",
            "echo hi\r\nhi\r\n",
            "$ ",
            "exit\r\n",
        ]
        assert [e.data for e in back.events if e.code == "r"] == ["50x8"]

    def test_v3_uses_intervals_and_keeps_the_exit(self):
        header, events = _lines(export_asciicast(_recording()))
        assert header["version"] == 3
        assert "width" not in header and header["term"]["cols"] == 40
        assert [e[0] for e in events] == [0.0, 1.0, 2.0, 0.5, 0.5, 0.25]
        assert events[-1] == [0.25, "x", "0"]

    def test_v2_uses_absolute_times_without_the_exit(self):
        header, events = _lines(export_asciicast(_recording(), version=2))
        assert (header["version"], header["width"], header["height"]) == (2, 40, 6)
        assert header["env"] == {"TERM": "xterm-256color"}
        assert [e[0] for e in events] == [0.0, 1.0, 3.0, 3.5, 4.0]
        assert "x" not in [e[1] for e in events]

    def test_rounding_doesnt_drift(self):
        events = [[0.1, "o", "x"]] * 1000
        back = parse_asciicast_str(export_asciicast(_recording(events)))
        assert back.events[-1].time == pytest.approx(100.0, abs=1e-6)

    def test_unicode_is_written_as_is(self):
        text = export_asciicast(_recording([[0.0, "o", "✓ done"]]))
        assert "✓ done" in text

    def test_no_title_or_timestamp(self):
        header, _ = _lines(export_asciicast(_recording(title="")))
        assert "title" not in header and "timestamp" not in header

    def test_bad_version(self):
        with pytest.raises(ValueError, match="must be 2 or 3"):
            export_asciicast(_recording(), version=1)


class TestScript:
    def test_cuts_and_speed_shorten_it(self):
        script = _parse_script_data({"cuts": [{"from": 1.5, "to": 2.5}], "settings": {"speed": 2}})
        back = parse_asciicast_str(export_asciicast(_recording(), script))
        # 0, 1, 3 and 4 lose the second inside the cut, then play twice as fast
        assert _times(back) == [0.0, 0.5, 1.0, 1.5]

    def test_chapters_become_markers(self):
        script = _parse_script_data(
            {"chapters": [{"at": 1.0, "label": "Echo"}, {"at": 0.0, "label": "Start"}]}
        )
        _, events = _lines(export_asciicast(_recording(), script))
        markers = [(e[1], e[2]) for e in events if e[1] == "m"]
        assert markers == [("m", "Start"), ("m", "Echo")]
        # A marker comes before the output at its time
        assert [e[1:] for e in events[:3]] == [["m", "Start"], ["o", "$ "], ["m", "Echo"]]
        back = parse_asciicast_str(export_asciicast(_recording(), script))
        assert _times(back, "m") == [0.0, 1.0]

    def test_chapters_replace_the_recordings_markers(self):
        events = [[0.0, "m", "Recorded"], *EVENTS]
        script = _parse_script_data({"chapters": [{"at": 1.0, "label": "Scripted"}]})
        _, out = _lines(export_asciicast(_recording(events), script))
        assert [e[2] for e in out if e[1] == "m"] == ["Scripted"]

    def test_recorded_markers_are_kept_without_chapters(self):
        events = [[0.0, "m", "Recorded"], *EVENTS]
        _, out = _lines(export_asciicast(_recording(events), _parse_script_data({})))
        assert [e[2] for e in out if e[1] == "m"] == ["Recorded"]

    def test_left_out(self):
        script = _parse_script_data(
            {
                "annotations": [{"at": 1, "text": "Hi"}],
                "snippets": [{"at": 1, "text": "echo hi"}],
                "highlights": [{"at": 1, "target": {"lines": [0]}}],
                "settings": {"prompt": "❯ "},
            }
        )
        assert left_out(script) == [
            "annotations",
            "highlights",
            "snippets",
            "the prompt replacement",
        ]
        assert left_out(_parse_script_data({"chapters": [{"at": 0}]})) == []
        assert left_out(None) == []


class TestTheme:
    def test_recording_theme_by_default(self):
        header, _ = _lines(export_asciicast(_recording()))
        theme = Theme()
        assert header["term"]["theme"] == {
            "fg": theme.fg,
            "bg": theme.bg,
            "palette": ":".join(theme.palette),
        }

    @pytest.mark.parametrize("version", [2, 3])
    def test_script_theme_round_trips(self, version):
        script = _parse_script_data({"settings": {"theme": "dracula"}})
        back = parse_asciicast_str(export_asciicast(_recording(), script, version=version))
        assert back.term.theme.fg == script.theme.fg
        assert back.term.theme.bg == script.theme.bg
        assert back.term.theme.palette == script.theme.palette

    def test_pair_uses_the_light_side(self):
        spec = {"light": "github-light", "dark": "dracula"}
        light, _ = resolve_theme_pair(spec)
        script = _parse_script_data({"settings": {"theme": spec}})
        header, _ = _lines(export_asciicast(_recording(), script))
        assert header["term"]["theme"]["bg"] == light.bg

    def test_theme_argument_wins(self):
        theme = Theme(fg="#000000", bg="#ffffff")
        script = _parse_script_data({"settings": {"theme": "dracula"}})
        header, _ = _lines(export_asciicast(_recording(), script, version=2, theme=theme))
        assert (header["theme"]["fg"], header["theme"]["bg"]) == ("#000000", "#ffffff")


class TestCli:
    def _write(self, tmp_path, script: str | None = None):
        source = tmp_path / "demo.termshow"
        header = {"version": 1, "format": "termshow", "term": {"cols": 40, "rows": 6}}
        source.write_text("\n".join(json.dumps(x) for x in [header, *EVENTS]) + "\n")
        if script is not None:
            (tmp_path / "demo.termshow.yml").write_text(script)
        return source

    def test_default_output(self, tmp_path):
        source = self._write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--cast"])
        assert result.exit_code == 0, result.output
        out = tmp_path / "demo.cast"
        assert "asciicast v3" in result.stdout
        assert "Events: 6" in result.stdout
        assert parse_asciicast_str(out.read_text()).version == 3

    def test_output_and_v2(self, tmp_path):
        source = self._write(tmp_path)
        out = tmp_path / "sub" / "x.cast"
        result = CliRunner().invoke(
            cli, ["termshow", "export", str(source), "--cast", "--v2", "-o", str(out)]
        )
        assert result.exit_code == 0, result.output
        header, events = _lines(out.read_text())
        assert header["version"] == 2 and len(events) == 5

    def test_script_applied_and_reported(self, tmp_path):
        source = self._write(
            tmp_path,
            "chapters:\n  - at: 0\n    label: Start\n"
            "cuts:\n  - from: 1.5\n    to: 2.5\n"
            "annotations:\n  - at: 1\n    text: Hi\n"
            "settings:\n  theme:\n    light: github-light\n    dark: dracula\n",
        )
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--cast"])
        assert result.exit_code == 0, result.output
        assert "Markers: 1" in result.stdout
        assert "the light side was used" in result.stdout
        assert "Left out (they need the Termshow player): annotations." in result.stderr
        back = parse_asciicast_str((tmp_path / "demo.cast").read_text())
        assert _times(back) == [0.0, 1.0, 2.0, 3.0]

    def test_no_script(self, tmp_path):
        source = self._write(tmp_path, "cuts:\n  - from: 1.5\n    to: 2.5\n")
        result = CliRunner().invoke(
            cli, ["termshow", "export", str(source), "--cast", "--no-script"]
        )
        assert result.exit_code == 0, result.output
        back = parse_asciicast_str((tmp_path / "demo.cast").read_text())
        assert _times(back) == [0.0, 1.0, 3.0, 4.0]

    def test_wont_overwrite_the_source(self, tmp_path):
        source = tmp_path / "demo.cast"
        source.write_text(export_asciicast(_recording()))
        before = source.read_text()
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--cast"])
        assert result.exit_code == 2
        assert "is the recording being exported" in result.output
        assert source.read_text() == before

    def test_cast_to_cast(self, tmp_path):
        source = tmp_path / "demo.cast"
        source.write_text(export_asciicast(_recording(), version=2))
        out = tmp_path / "demo-v3.cast"
        result = CliRunner().invoke(
            cli, ["termshow", "export", str(source), "--cast", "-o", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert _times(parse_asciicast_str(out.read_text())) == [0.0, 1.0, 3.0, 4.0]

    @pytest.mark.parametrize(
        "args",
        [["--no-loop"], ["--chapter-cards"], ["--no-annotations"], ["--end-pause", "1"]],
    )
    def test_svg_options_rejected(self, tmp_path, args):
        source = self._write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--cast", *args])
        assert result.exit_code == 2
        assert f"{args[0]} only applies to --svg" in result.output

    def test_v2_needs_cast(self, tmp_path):
        source = self._write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--v2"])
        assert result.exit_code == 2
        assert "--v2 only applies to --cast" in result.output
        assert not (tmp_path / "demo.svg").exists()


def _asciinema_version() -> tuple[int, ...] | None:
    path = shutil.which("asciinema")
    if not path:
        return None
    out = subprocess.run([path, "--version"], capture_output=True, text=True).stdout
    digits = out.split()[-1] if out.split() else ""
    try:
        return tuple(int(x) for x in digits.split(".")[:2])
    except ValueError:
        return None


@pytest.mark.parametrize("version", [2, 3])
def test_asciinema_reads_it(tmp_path, version):
    found = _asciinema_version()
    if found is None:
        pytest.skip("asciinema isn't installed")
    if version == 3 and found < (3, 0):
        pytest.skip(f"asciinema {'.'.join(map(str, found))} only reads asciicast v1 and v2")
    path = tmp_path / "demo.cast"
    path.write_text(export_asciicast(_recording(), version=version))
    result = subprocess.run(["asciinema", "cat", str(path)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.decode() == "$ echo hi\r\nhi\r\n$ exit\r\n"
