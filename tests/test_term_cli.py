"""Tests for CLI term subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs.cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_termshow_file(tmp_path: Path, name: str = "test.termshow", duration: float = 3.0) -> Path:
    """Create a minimal .termshow file for testing."""
    header = {
        "version": 1,
        "format": "termshow",
        "term": {"cols": 80, "rows": 24, "type": "xterm-256color"},
        "title": "Test",
    }
    events = [
        [0.0, "o", "$ "],
        [1.0, "o", "hello\r\n"],
        [duration - 1.0, "o", "$ "],
    ]
    content = "\n".join([json.dumps(header)] + [json.dumps(e) for e in events])
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


def _make_asciicast_file(tmp_path: Path, name: str = "test.cast") -> Path:
    """Create a minimal asciicast v2 file."""
    header = {"version": 2, "width": 80, "height": 24}
    events = [[0.5, "o", "hello"], [1.0, "o", " world"]]
    content = "\n".join([json.dumps(header)] + [json.dumps(e) for e in events])
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


def _make_tape_file(tmp_path: Path, name: str = "test.tape") -> Path:
    """Create a minimal VHS tape file."""
    content = 'Set Width 80\nSet Height 24\nType "hello"\nEnter\n'
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# term render
# ---------------------------------------------------------------------------


class TestTermRender:
    def test_basic_render(self, tmp_path: Path):
        source = _make_termshow_file(tmp_path)
        out_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "render", str(source), "-o", str(out_dir)])

        assert result.exit_code == 0
        assert "Rendered" in result.output
        assert (out_dir / "manifest.json").exists()

    def test_render_with_interval(self, tmp_path: Path):
        source = _make_termshow_file(tmp_path, duration=6.0)
        out_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(
            cli, ["termshow", "render", str(source), "-o", str(out_dir), "--interval", "1.0"]
        )

        assert result.exit_code == 0
        manifest = json.loads((out_dir / "manifest.json").read_text())
        # With 6s duration and 1s interval, should have at least 6 keyframes
        assert len(manifest["keyframes"]) >= 6

    def test_render_with_script(self, tmp_path: Path):
        source = _make_termshow_file(tmp_path)
        script = tmp_path / "test.termshow.yml"
        script.write_text(
            "settings:\n  window_chrome: colorful\nchapters:\n  - at: 0.0\n    label: Start\n",
            encoding="utf-8",
        )
        out_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["termshow", "render", str(source), "-o", str(out_dir), "--script", str(script)],
        )

        assert result.exit_code == 0
        assert "Chapters: 1" in result.output

    def test_render_auto_detects_script(self, tmp_path: Path):
        source = _make_termshow_file(tmp_path)
        # Create companion .termshow.yml with same base name
        script = tmp_path / "test.termshow.yml"
        script.write_text(
            "chapters:\n  - at: 1.0\n    label: Auto\n",
            encoding="utf-8",
        )
        out_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "render", str(source), "-o", str(out_dir)])

        assert result.exit_code == 0
        assert "Chapters: 1" in result.output

    def test_render_default_output_dir(self, tmp_path: Path):
        source = _make_termshow_file(tmp_path)

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Copy source into CWD
            Path("test.termshow").write_text(source.read_text())
            result = runner.invoke(cli, ["termshow", "render", "test.termshow"])

        assert result.exit_code == 0

    def test_render_nonexistent_file(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "render", str(tmp_path / "missing.termshow")])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# term import-cast
# ---------------------------------------------------------------------------


class TestTermImportCast:
    def test_import_cast(self, tmp_path: Path):
        source = _make_asciicast_file(tmp_path)
        output = tmp_path / "imported.termshow"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "import-cast", str(source), str(output)])

        assert result.exit_code == 0
        assert "Imported" in result.output
        assert output.exists()

    def test_import_cast_appends_extension(self, tmp_path: Path):
        source = _make_asciicast_file(tmp_path)
        output = tmp_path / "imported"  # No .termshow extension

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "import-cast", str(source), str(output)])

        assert result.exit_code == 0
        assert (tmp_path / "imported.termshow").exists()

    def test_import_cast_shows_stats(self, tmp_path: Path):
        source = _make_asciicast_file(tmp_path)
        output = tmp_path / "out.termshow"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "import-cast", str(source), str(output)])

        assert "Duration:" in result.output
        assert "Events:" in result.output


# ---------------------------------------------------------------------------
# term import-tape
# ---------------------------------------------------------------------------


class TestTermImportTape:
    def test_import_tape(self, tmp_path: Path):
        source = _make_tape_file(tmp_path)
        output = tmp_path / "imported.termshow"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "import-tape", str(source), str(output)])

        assert result.exit_code == 0
        assert "Imported" in result.output
        assert output.exists()

    def test_import_tape_appends_extension(self, tmp_path: Path):
        source = _make_tape_file(tmp_path)
        output = tmp_path / "imported"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "import-tape", str(source), str(output)])

        assert result.exit_code == 0
        assert (tmp_path / "imported.termshow").exists()

    def test_import_tape_shows_stats(self, tmp_path: Path):
        source = _make_tape_file(tmp_path)
        output = tmp_path / "out.termshow"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "import-tape", str(source), str(output)])

        assert "Duration:" in result.output
        assert "Events:" in result.output


# ---------------------------------------------------------------------------
# term (group help)
# ---------------------------------------------------------------------------


class TestTermGroup:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "--help"])
        assert result.exit_code == 0
        assert "record" in result.output
        assert "render" in result.output
        assert "import-cast" in result.output
        assert "import-tape" in result.output
        assert "edit" in result.output


# ---------------------------------------------------------------------------
# Recorder message stripping
# ---------------------------------------------------------------------------


class TestStripRecorderMessages:
    """Tests for _strip_recorder_messages post-processing."""

    def _build_events(self, event_tuples: list[tuple]) -> list[str]:
        """Build event list from (interval, code, data) tuples with a header."""
        header = json.dumps({"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 24}})
        return [header] + [json.dumps(list(t)) for t in event_tuples]

    def test_strips_recording_started(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        events = self._build_events(
            [
                (0.5, "o", "$ "),
                (0.3, "o", "\x1b[36m\x1b[1m● Recording started\x1b[0m (Ctrl+D to stop)\r\n"),
                (1.0, "o", "$ hello\r\n"),
            ]
        )
        result = _strip_recorder_messages(events)
        # Header + 2 events (started message removed)
        assert len(result) == 3
        # The time from stripped event merges into next
        arr = json.loads(result[2])
        assert arr[0] == pytest.approx(1.3)  # 0.3 + 1.0

    def test_strips_recording_stopped(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        events = self._build_events(
            [
                (0.5, "o", "real output\r\n"),
                (0.2, "o", "\x1b[36m● Recording stopped\x1b[0m (5 events captured, 3.2s)\r\n"),
                (0.5, "o", "$ "),
            ]
        )
        result = _strip_recorder_messages(events)
        assert len(result) == 3
        # Last event absorbs the stripped interval
        arr = json.loads(result[2])
        assert arr[0] == pytest.approx(0.7)

    def test_strips_saved_line(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        events = self._build_events(
            [
                (0.5, "o", "real output\r\n"),
                (0.1, "o", "  \x1b[90mSaved: /tmp/my-demo.termshow\x1b[0m\r\n"),
                (0.5, "o", "$ "),
            ]
        )
        result = _strip_recorder_messages(events)
        assert len(result) == 3

    def test_preserves_non_recorder_output(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        events = self._build_events(
            [
                (0.5, "o", "$ pip install great-tables\r\n"),
                (1.0, "o", "Successfully installed great-tables\r\n"),
                (0.5, "o", "$ "),
            ]
        )
        result = _strip_recorder_messages(events)
        # Nothing stripped
        assert len(result) == 4  # header + 3 events

    def test_preserves_input_events(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        events = self._build_events(
            [
                (0.5, "i", "Recording started"),  # Input event, not output
                (0.5, "o", "$ "),
            ]
        )
        result = _strip_recorder_messages(events)
        # Input event preserved (only "o" events are filtered)
        assert len(result) == 3

    def test_preserves_marker_events(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        events = self._build_events(
            [
                (0.5, "m", "recording started"),
                (0.5, "o", "$ "),
            ]
        )
        result = _strip_recorder_messages(events)
        assert len(result) == 3

    def test_empty_events(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        result = _strip_recorder_messages([])
        assert result == []

    def test_header_only(self):
        from great_docs._term_player.recorder import _strip_recorder_messages

        header = json.dumps({"version": 1, "format": "termshow"})
        result = _strip_recorder_messages([header])
        assert result == [header]
