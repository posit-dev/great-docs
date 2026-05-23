"""Tests for the _term_player.importer module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from great_docs._term_player.importer import (
    _parse_duration,
    _parse_tape,
    _write_termshow,
    import_asciicast,
    import_tape,
)
from great_docs._term_player.parser import Event, Recording, TermInfo, parse_termshow_str


# ---------------------------------------------------------------------------
# _parse_duration
# ---------------------------------------------------------------------------


class TestParseDuration:
    def test_milliseconds(self):
        assert _parse_duration("500ms") == pytest.approx(0.5)

    def test_seconds(self):
        assert _parse_duration("2s") == pytest.approx(2.0)

    def test_fractional_seconds(self):
        assert _parse_duration("1.5s") == pytest.approx(1.5)

    def test_plain_number(self):
        assert _parse_duration("0.1") == pytest.approx(0.1)

    def test_invalid_returns_default(self):
        assert _parse_duration("abc") == pytest.approx(0.1)

    def test_with_whitespace(self):
        assert _parse_duration("  200ms  ") == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# _parse_tape
# ---------------------------------------------------------------------------


class TestParseTape:
    def test_basic_type_command(self):
        tape = 'Type "hello"'
        rec = _parse_tape(tape)
        # Should produce one event per character
        assert len(rec.events) == 5
        chars = "".join(e.data for e in rec.events)
        assert chars == "hello"

    def test_type_with_backtick_quotes(self):
        tape = "Type `world`"
        rec = _parse_tape(tape)
        chars = "".join(e.data for e in rec.events)
        assert chars == "world"

    def test_enter_command(self):
        tape = "Enter"
        rec = _parse_tape(tape)
        assert len(rec.events) == 1
        assert rec.events[0].data == "\r\n"

    def test_enter_count(self):
        tape = "Enter 3"
        rec = _parse_tape(tape)
        assert len(rec.events) == 3
        assert all(e.data == "\r\n" for e in rec.events)

    def test_sleep_advances_time(self):
        tape = 'Type "a"\nSleep 2s\nType "b"'
        rec = _parse_tape(tape)
        first_time = rec.events[0].time
        last_time = rec.events[-1].time
        assert last_time - first_time >= 2.0

    def test_set_width_height(self):
        tape = 'Set Width 120\nSet Height 40\nType "x"'
        rec = _parse_tape(tape)
        assert rec.term.cols == 120
        assert rec.term.rows == 40

    def test_set_typing_speed(self):
        tape = 'Set TypingSpeed 100ms\nType "ab"'
        rec = _parse_tape(tape)
        # Two chars at 100ms each
        gap = rec.events[1].time - rec.events[0].time
        assert gap == pytest.approx(0.1)

    def test_type_speed_override(self):
        tape = 'Type@200ms "ab"'
        rec = _parse_tape(tape)
        gap = rec.events[1].time - rec.events[0].time
        assert gap == pytest.approx(0.2)

    def test_backspace(self):
        tape = "Backspace"
        rec = _parse_tape(tape)
        assert rec.events[0].data == "\x08"

    def test_backspace_count(self):
        tape = "Backspace 3"
        rec = _parse_tape(tape)
        assert len(rec.events) == 3
        assert all(e.data == "\x08" for e in rec.events)

    def test_tab(self):
        tape = "Tab"
        rec = _parse_tape(tape)
        assert rec.events[0].data == "\t"

    def test_space(self):
        tape = "Space"
        rec = _parse_tape(tape)
        assert rec.events[0].data == " "

    def test_arrow_keys(self):
        tape = "Up\nDown\nLeft\nRight"
        rec = _parse_tape(tape)
        assert rec.events[0].data == "\x1b[A"
        assert rec.events[1].data == "\x1b[B"
        assert rec.events[2].data == "\x1b[D"
        assert rec.events[3].data == "\x1b[C"

    def test_escape(self):
        tape = "Escape"
        rec = _parse_tape(tape)
        assert rec.events[0].data == "\x1b"

    def test_ctrl_key(self):
        tape = "Ctrl+C"
        rec = _parse_tape(tape)
        # Ctrl+C = chr(3)
        assert rec.events[0].data == "\x03"

    def test_ctrl_d(self):
        tape = "Ctrl+D"
        rec = _parse_tape(tape)
        assert rec.events[0].data == "\x04"

    def test_hide_show_markers(self):
        tape = "Hide\nShow"
        rec = _parse_tape(tape)
        assert rec.events[0].code == "m"
        assert rec.events[0].data == "[hidden]"
        assert rec.events[1].code == "m"
        assert rec.events[1].data == "[visible]"

    def test_comments_ignored(self):
        tape = '# This is a comment\nType "x"'
        rec = _parse_tape(tape)
        assert len(rec.events) == 1

    def test_blank_lines_ignored(self):
        tape = '\n\nType "x"\n\n'
        rec = _parse_tape(tape)
        assert len(rec.events) == 1

    def test_events_have_output_code(self):
        tape = 'Type "abc"'
        rec = _parse_tape(tape)
        assert all(e.code == "o" for e in rec.events)

    def test_times_are_monotonic(self):
        tape = 'Type "hello"\nSleep 1s\nEnter\nType "world"'
        rec = _parse_tape(tape)
        times = [e.time for e in rec.events]
        assert times == sorted(times)


# ---------------------------------------------------------------------------
# _write_termshow
# ---------------------------------------------------------------------------


class TestWriteTermshow:
    def test_writes_valid_termshow(self, tmp_path: Path):
        rec = Recording(
            version=1,
            format="termshow",
            term=TermInfo(cols=80, rows=24),
            title="Test",
            events=[
                Event(time=0.0, code="o", data="$ "),
                Event(time=0.5, code="o", data="hello"),
                Event(time=1.5, code="o", data="\r\n"),
            ],
        )

        out = tmp_path / "output.termshow"
        _write_termshow(rec, out)

        assert out.exists()
        # Parse it back
        content = out.read_text()
        parsed = parse_termshow_str(content)
        assert parsed.term.cols == 80
        assert len(parsed.events) == 3
        assert parsed.events[0].time == pytest.approx(0.0)
        assert parsed.events[1].time == pytest.approx(0.5)
        assert parsed.events[2].time == pytest.approx(1.5)

    def test_creates_parent_dirs(self, tmp_path: Path):
        out = tmp_path / "deep" / "nested" / "dir" / "rec.termshow"
        rec = Recording(events=[Event(time=0.0, code="o", data="x")])
        _write_termshow(rec, out)
        assert out.exists()

    def test_relative_intervals_in_output(self, tmp_path: Path):
        rec = Recording(
            events=[
                Event(time=0.0, code="o", data="a"),
                Event(time=1.0, code="o", data="b"),
                Event(time=3.0, code="o", data="c"),
            ]
        )
        out = tmp_path / "test.termshow"
        _write_termshow(rec, out)

        lines = out.read_text().strip().splitlines()
        # Line 0 = header, lines 1-3 = events
        ev1 = json.loads(lines[1])
        ev2 = json.loads(lines[2])
        ev3 = json.loads(lines[3])
        assert ev1[0] == pytest.approx(0.0)
        assert ev2[0] == pytest.approx(1.0)
        assert ev3[0] == pytest.approx(2.0)  # 3.0 - 1.0

    def test_header_includes_title(self, tmp_path: Path):
        rec = Recording(title="My Demo", events=[Event(time=0.0, code="o", data="x")])
        out = tmp_path / "test.termshow"
        _write_termshow(rec, out)

        lines = out.read_text().strip().splitlines()
        header = json.loads(lines[0])
        assert header["title"] == "My Demo"


# ---------------------------------------------------------------------------
# import_asciicast (integration)
# ---------------------------------------------------------------------------


class TestImportAsciicast:
    def test_imports_and_writes(self, tmp_path: Path):
        # Create a minimal asciicast file
        header = {"version": 2, "width": 80, "height": 24}
        events = [[0.5, "o", "hello"], [1.0, "o", " world"]]
        source = tmp_path / "test.cast"
        source.write_text(
            "\n".join([json.dumps(header)] + [json.dumps(e) for e in events]),
            encoding="utf-8",
        )

        output = tmp_path / "result.termshow"
        rec = import_asciicast(source, output)

        assert output.exists()
        assert len(rec.events) == 2
        assert rec.events[0].data == "hello"

        # Verify the output is parseable
        parsed = parse_termshow_str(output.read_text())
        assert len(parsed.events) == 2


# ---------------------------------------------------------------------------
# import_tape (integration)
# ---------------------------------------------------------------------------


class TestImportTape:
    def test_imports_and_writes(self, tmp_path: Path):
        tape_content = """\
Set Width 100
Set Height 30
Type "ls -la"
Enter
Sleep 500ms
Type "exit"
Enter
"""
        source = tmp_path / "test.tape"
        source.write_text(tape_content, encoding="utf-8")

        output = tmp_path / "result.termshow"
        rec = import_tape(source, output)

        assert output.exists()
        assert rec.term.cols == 100
        assert rec.term.rows == 30
        assert len(rec.events) > 0

        # Verify the output is parseable
        parsed = parse_termshow_str(output.read_text())
        assert parsed.term.cols == 100
