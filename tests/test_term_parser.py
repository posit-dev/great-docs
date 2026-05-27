"""Tests for the _term_player.parser module."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from great_docs._term_player.parser import (
    Event,
    Recording,
    TermInfo,
    Theme,
    _header_to_recording,
    _parse_theme,
    parse_asciicast_str,
    parse_termshow_str,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_header(**overrides) -> str:
    """Build a minimal termshow header JSON line."""
    hdr = {"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 24}}
    hdr.update(overrides)
    return json.dumps(hdr)


def _make_termshow(header: dict, events: list[tuple[float, str, str]]) -> str:
    """Build a complete termshow file as a string."""
    lines = [json.dumps(header)]
    for interval, code, data in events:
        lines.append(json.dumps([interval, code, data]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Theme parsing
# ---------------------------------------------------------------------------


class TestParseTheme:
    def test_empty_dict_returns_defaults(self):
        theme = _parse_theme({})
        assert theme.fg == "#d0d0d0"
        assert theme.bg == "#1e1e2e"
        assert len(theme.palette) == 16

    def test_custom_fg_bg(self):
        theme = _parse_theme({"fg": "#ffffff", "bg": "#000000"})
        assert theme.fg == "#ffffff"
        assert theme.bg == "#000000"

    def test_palette_from_colon_string(self):
        pal = "#aaa:#bbb:#ccc"
        theme = _parse_theme({"palette": pal})
        assert theme.palette == ["#aaa", "#bbb", "#ccc"]

    def test_palette_from_list(self):
        pal = ["#111", "#222", "#333"]
        theme = _parse_theme({"palette": pal})
        assert theme.palette == pal

    def test_empty_palette_string_keeps_default(self):
        theme = _parse_theme({"palette": ""})
        assert len(theme.palette) == 16


# ---------------------------------------------------------------------------
# Recording dataclass
# ---------------------------------------------------------------------------


class TestRecording:
    def test_duration_empty(self):
        rec = Recording()
        assert rec.duration == 0.0

    def test_duration_with_events(self):
        rec = Recording(
            events=[Event(time=1.0, code="o", data="a"), Event(time=5.5, code="o", data="b")]
        )
        assert rec.duration == 5.5

    def test_default_values(self):
        rec = Recording()
        assert rec.version == 1
        assert rec.format == "termshow"
        assert rec.term.cols == 80
        assert rec.term.rows == 24


# ---------------------------------------------------------------------------
# parse_termshow_str
# ---------------------------------------------------------------------------


class TestParseTermshowStr:
    def test_empty_input(self):
        rec = parse_termshow_str("")
        assert rec.duration == 0.0
        assert rec.events == []

    def test_header_only(self):
        rec = parse_termshow_str(_minimal_header(title="Hello"))
        assert rec.title == "Hello"
        assert rec.events == []

    def test_events_relative_to_absolute(self):
        text = _make_termshow(
            {"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20}},
            [(0.0, "o", "$ "), (0.5, "o", "hello"), (1.0, "o", " world")],
        )
        rec = parse_termshow_str(text)
        assert len(rec.events) == 3
        assert rec.events[0].time == pytest.approx(0.0)
        assert rec.events[1].time == pytest.approx(0.5)
        assert rec.events[2].time == pytest.approx(1.5)

    def test_term_info_parsed(self):
        text = _make_termshow(
            {
                "version": 1,
                "format": "termshow",
                "term": {"cols": 120, "rows": 40, "type": "screen"},
            },
            [],
        )
        rec = parse_termshow_str(text)
        assert rec.term.cols == 120
        assert rec.term.rows == 40
        assert rec.term.type == "screen"

    def test_skips_comments(self):
        text = _minimal_header() + "\n# comment\n" + json.dumps([1.0, "o", "data"])
        rec = parse_termshow_str(text)
        assert len(rec.events) == 1

    def test_skips_blank_lines(self):
        text = _minimal_header() + "\n\n\n" + json.dumps([1.0, "o", "x"])
        rec = parse_termshow_str(text)
        assert len(rec.events) == 1

    def test_skips_malformed_events(self):
        text = (
            _minimal_header() + "\n" + json.dumps([1.0, "o"]) + "\n" + json.dumps([0.5, "o", "ok"])
        )
        rec = parse_termshow_str(text)
        # First event has only 2 elements, should be skipped
        assert len(rec.events) == 1
        assert rec.events[0].data == "ok"

    def test_event_codes_preserved(self):
        text = _make_termshow(
            {"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 24}},
            [(0.0, "o", "out"), (0.1, "i", "in"), (0.2, "m", "marker")],
        )
        rec = parse_termshow_str(text)
        assert rec.events[0].code == "o"
        assert rec.events[1].code == "i"
        assert rec.events[2].code == "m"

    def test_theme_in_header(self):
        text = _make_termshow(
            {
                "version": 1,
                "format": "termshow",
                "term": {"cols": 80, "rows": 24, "theme": {"fg": "#ff0000", "bg": "#00ff00"}},
            },
            [],
        )
        rec = parse_termshow_str(text)
        assert rec.term.theme.fg == "#ff0000"
        assert rec.term.theme.bg == "#00ff00"


# ---------------------------------------------------------------------------
# parse_asciicast_str
# ---------------------------------------------------------------------------


class TestParseAsciicastStr:
    def test_v2_absolute_timestamps(self):
        header = {"version": 2, "width": 100, "height": 30}
        lines = [
            json.dumps(header),
            json.dumps([0.5, "o", "hello"]),
            json.dumps([1.2, "o", " world"]),
            json.dumps([3.0, "o", "\n"]),
        ]
        rec = parse_asciicast_str("\n".join(lines))
        assert rec.format == "asciicast"
        assert rec.term.cols == 100
        assert rec.term.rows == 30
        assert rec.events[0].time == pytest.approx(0.5)
        assert rec.events[1].time == pytest.approx(1.2)
        assert rec.events[2].time == pytest.approx(3.0)

    def test_v3_relative_timestamps(self):
        header = {"version": 3, "width": 80, "height": 24}
        lines = [
            json.dumps(header),
            json.dumps([0.5, "o", "a"]),
            json.dumps([0.3, "o", "b"]),
            json.dumps([1.0, "o", "c"]),
        ]
        rec = parse_asciicast_str("\n".join(lines))
        assert rec.events[0].time == pytest.approx(0.5)
        assert rec.events[1].time == pytest.approx(0.8)
        assert rec.events[2].time == pytest.approx(1.8)

    def test_env_term_parsed(self):
        header = {"version": 2, "width": 80, "height": 24, "env": {"TERM": "rxvt-unicode"}}
        rec = parse_asciicast_str(json.dumps(header))
        assert rec.term.type == "rxvt-unicode"

    def test_empty_input(self):
        rec = parse_asciicast_str("")
        assert rec.events == []


# ---------------------------------------------------------------------------
# _header_to_recording
# ---------------------------------------------------------------------------


class TestHeaderToRecording:
    def test_asciicast_width_height_at_top(self):
        rec = _header_to_recording({"version": 2, "width": 132, "height": 50})
        assert rec.term.cols == 132
        assert rec.term.rows == 50

    def test_timestamp(self):
        rec = _header_to_recording({"timestamp": 1700000000})
        assert rec.timestamp == 1700000000

    def test_non_dict_term(self):
        # Some edge-case headers might have term as non-dict
        rec = _header_to_recording({"term": "invalid", "width": 90, "height": 30})
        assert rec.term.cols == 90
        assert rec.term.rows == 30


# ---------------------------------------------------------------------------
# File-based parsing (parse_termshow, parse_asciicast)
# ---------------------------------------------------------------------------


class TestFileParsing:
    def test_parse_termshow_file(self, tmp_path: Path):
        from great_docs._term_player.parser import parse_termshow

        content = _make_termshow(
            {"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 20}, "title": "Test"},
            [(0.0, "o", "$ "), (0.5, "o", "cmd\r\n")],
        )
        f = tmp_path / "test.termshow"
        f.write_text(content, encoding="utf-8")

        rec = parse_termshow(f)
        assert rec.title == "Test"
        assert len(rec.events) == 2
        assert rec.duration == pytest.approx(0.5)

    def test_parse_asciicast_file(self, tmp_path: Path):
        from great_docs._term_player.parser import parse_asciicast

        header = {"version": 2, "width": 80, "height": 24}
        content = json.dumps(header) + "\n" + json.dumps([1.0, "o", "hello"])
        f = tmp_path / "test.cast"
        f.write_text(content, encoding="utf-8")

        rec = parse_asciicast(f)
        assert rec.format == "asciicast"
        assert len(rec.events) == 1
