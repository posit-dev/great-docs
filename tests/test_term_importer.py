"""Tests for the _term_player.importer module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from great_docs._term_player.importer import (
    _write_termshow,
    import_asciicast,
)
from great_docs._term_player.parser import Event, Recording, TermInfo, parse_termshow_str


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
