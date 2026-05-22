"""Tests for the _term_player.script module."""

from __future__ import annotations

from pathlib import Path

import pytest

from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import (
    Annotation,
    Chapter,
    Cut,
    Highlight,
    Script,
    SpeedSegment,
    _apply_cuts,
    _apply_idle_limit,
    _apply_speed_map,
    _remap_time,
    apply_script,
    load_script,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _events(*times: float) -> list[Event]:
    """Create output events at the given absolute times."""
    return [Event(time=t, code="o", data=f"data_{i}") for i, t in enumerate(times)]


def _recording(events: list[Event], idle_time_limit: float | None = None) -> Recording:
    """Create a minimal Recording wrapping some events."""
    return Recording(events=events, idle_time_limit=idle_time_limit)


# ---------------------------------------------------------------------------
# _apply_idle_limit
# ---------------------------------------------------------------------------


class TestApplyIdleLimit:
    def test_no_events(self):
        result = _apply_idle_limit([], 2.0)
        assert result == []

    def test_no_compression_needed(self):
        events = _events(0.0, 0.5, 1.0, 1.5)
        result = _apply_idle_limit(events, 2.0)
        assert [e.time for e in result] == pytest.approx([0.0, 0.5, 1.0, 1.5])

    def test_single_gap_compressed(self):
        # Gap from 1.0 to 6.0 = 5s, limit = 2s → remove 3s
        events = _events(0.0, 1.0, 6.0, 7.0)
        result = _apply_idle_limit(events, 2.0)
        assert result[0].time == pytest.approx(0.0)
        assert result[1].time == pytest.approx(1.0)
        assert result[2].time == pytest.approx(3.0)  # 6.0 - 3.0
        assert result[3].time == pytest.approx(4.0)  # 7.0 - 3.0

    def test_multiple_gaps_compressed(self):
        # Two gaps: 1→5 (4s gap, remove 2s) and 6→12 (6s gap, remove 4s)
        events = _events(0.0, 1.0, 5.0, 6.0, 12.0)
        result = _apply_idle_limit(events, 2.0)
        assert result[0].time == pytest.approx(0.0)
        assert result[1].time == pytest.approx(1.0)
        assert result[2].time == pytest.approx(3.0)  # 5 - 2
        assert result[3].time == pytest.approx(4.0)  # 6 - 2
        assert result[4].time == pytest.approx(6.0)  # 12 - 2 - 4

    def test_preserves_event_data(self):
        events = [Event(time=0.0, code="o", data="hello"), Event(time=10.0, code="i", data="world")]
        result = _apply_idle_limit(events, 1.0)
        assert result[0].data == "hello"
        assert result[0].code == "o"
        assert result[1].data == "world"
        assert result[1].code == "i"


# ---------------------------------------------------------------------------
# _apply_cuts
# ---------------------------------------------------------------------------


class TestApplyCuts:
    def test_no_cuts(self):
        events = _events(0.0, 1.0, 2.0, 3.0)
        result = _apply_cuts(events, [])
        assert [e.time for e in result] == pytest.approx([0.0, 1.0, 2.0, 3.0])

    def test_single_cut_removes_events(self):
        events = _events(0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
        cuts = [Cut(start=1.5, end=3.5)]
        result = _apply_cuts(events, cuts)
        # Events at 2.0 and 3.0 are inside [1.5, 3.5], removed
        remaining_data = [e.data for e in result]
        assert "data_2" not in remaining_data
        assert "data_3" not in remaining_data

    def test_cut_adjusts_timing(self):
        events = _events(0.0, 1.0, 2.0, 3.0, 4.0)
        cuts = [Cut(start=1.5, end=2.5)]  # 1s cut
        result = _apply_cuts(events, cuts)
        # Events at 0.0 and 1.0 are before cut, events at 3.0 and 4.0 are after
        times = [e.time for e in result]
        # After cut: 3.0 - 1.0 = 2.0, 4.0 - 1.0 = 3.0
        assert times[0] == pytest.approx(0.0)
        assert times[1] == pytest.approx(1.0)
        assert times[-1] == pytest.approx(3.0)

    def test_multiple_cuts(self):
        events = _events(0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        cuts = [Cut(start=0.5, end=1.5), Cut(start=4.5, end=5.5)]
        result = _apply_cuts(events, cuts)
        # Event at 1.0 removed (in first cut), event at 5.0 removed (in second cut)
        remaining_data = [e.data for e in result]
        assert "data_1" not in remaining_data
        assert "data_5" not in remaining_data

    def test_event_at_cut_boundary_is_removed(self):
        events = _events(0.0, 1.0, 2.0, 3.0)
        # Event exactly at start or end of cut is inside [start, end]
        cuts = [Cut(start=1.0, end=2.0)]
        result = _apply_cuts(events, cuts)
        remaining_data = [e.data for e in result]
        assert "data_1" not in remaining_data
        assert "data_2" not in remaining_data


# ---------------------------------------------------------------------------
# _apply_speed_map / _remap_time
# ---------------------------------------------------------------------------


class TestRemapTime:
    def test_no_segments(self):
        # With a segment that doesn't cover our time, function returns 0
        # (time before first segment start is not accumulated when t <= seg.start)
        segs = [SpeedSegment(start=10.0, end=20.0, speed=2.0)]
        assert _remap_time(5.0, segs) == pytest.approx(0.0)

    def test_time_past_segment_start(self):
        # Segment [2, 6] at 2x speed: time is past start
        segs = [SpeedSegment(start=2.0, end=6.0, speed=2.0)]
        # At t=4: gap_before = min(4,2)-0 = 2, time_in_seg = min(4,6)-2 = 2, new_t = 2 + 2/2 = 3
        assert _remap_time(4.0, segs) == pytest.approx(3.0)

    def test_time_after_segment(self):
        # Segment [2, 6] at 2x speed
        # At t=8: 2s before + 4s/2 + 2s after = 2 + 2 + 2 = 6
        segs = [SpeedSegment(start=2.0, end=6.0, speed=2.0)]
        assert _remap_time(8.0, segs) == pytest.approx(6.0)

    def test_slow_speed(self):
        # Segment [1, 3] at 0.5x speed → 2s becomes 4s
        segs = [SpeedSegment(start=1.0, end=3.0, speed=0.5)]
        # At t=3: 1s before + 2s/0.5 = 1 + 4 = 5
        assert _remap_time(3.0, segs) == pytest.approx(5.0)

    def test_multiple_segments(self):
        segs = [
            SpeedSegment(start=1.0, end=3.0, speed=2.0),  # 2s → 1s
            SpeedSegment(start=5.0, end=7.0, speed=0.5),  # 2s → 4s
        ]
        # At t=10: 1s + 2s/2 + (5-3)=2s + 2s/0.5 + (10-7)=3s = 1 + 1 + 2 + 4 + 3 = 11
        assert _remap_time(10.0, segs) == pytest.approx(11.0)


class TestApplySpeedMap:
    def test_speed_map_adjusts_all_events(self):
        events = _events(0.0, 2.0, 4.0, 6.0)
        segs = [SpeedSegment(start=2.0, end=4.0, speed=2.0)]
        result = _apply_speed_map(events, segs)
        # t=0: 0 (t <= seg.start → 0)
        # t=2: 0 (t <= seg.start → 0)
        # t=4: gap_before=min(4,2)-0=2, in_seg=min(4,4)-2=2, new=2+2/2=3
        # t=6: gap_before=min(6,2)-0=2, in_seg=min(6,4)-2=2, new=2+1=3, prev=4; remaining=6-max(4,4)=2, total=5
        assert result[0].time == pytest.approx(0.0)
        assert result[1].time == pytest.approx(0.0)
        assert result[2].time == pytest.approx(3.0)
        assert result[3].time == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# apply_script (integration)
# ---------------------------------------------------------------------------


class TestApplyScript:
    def test_idle_limit_from_script(self):
        rec = _recording(_events(0.0, 1.0, 11.0, 12.0))
        script = Script(idle_time_limit=2.0)
        result = apply_script(rec, script)
        # Gap 1→11 = 10s, compressed to 2s → offset = 8
        assert result.events[2].time == pytest.approx(3.0)
        assert result.events[3].time == pytest.approx(4.0)

    def test_idle_limit_from_recording(self):
        rec = _recording(_events(0.0, 1.0, 11.0), idle_time_limit=3.0)
        script = Script()  # No idle limit in script
        result = apply_script(rec, script)
        # Uses recording's idle_time_limit=3.0: gap 10s → 3s, offset=7
        assert result.events[2].time == pytest.approx(4.0)

    def test_global_speed(self):
        rec = _recording(_events(0.0, 2.0, 4.0))
        script = Script(speed=2.0)
        result = apply_script(rec, script)
        assert result.events[0].time == pytest.approx(0.0)
        assert result.events[1].time == pytest.approx(1.0)
        assert result.events[2].time == pytest.approx(2.0)

    def test_cuts_applied(self):
        rec = _recording(_events(0.0, 1.0, 2.0, 3.0, 4.0))
        script = Script(cuts=[Cut(start=1.5, end=2.5)])
        result = apply_script(rec, script)
        # Event at 2.0 should be removed
        assert all(e.data != "data_2" for e in result.events)

    def test_empty_script_no_change(self):
        events = _events(0.0, 1.0, 2.0)
        rec = _recording(events)
        script = Script()
        result = apply_script(rec, script)
        assert [e.time for e in result.events] == pytest.approx([0.0, 1.0, 2.0])

    def test_preserves_recording_metadata(self):
        rec = Recording(
            version=1,
            format="termshow",
            term=TermInfo(cols=120, rows=40),
            title="My Recording",
            events=_events(0.0, 1.0),
        )
        script = Script()
        result = apply_script(rec, script)
        assert result.title == "My Recording"
        assert result.term.cols == 120
        assert result.format == "termshow"


# ---------------------------------------------------------------------------
# load_script (file-based)
# ---------------------------------------------------------------------------


class TestLoadScript:
    def test_load_basic_script(self, tmp_path: Path):
        content = """\
settings:
  idle_time_limit: 2.0
  speed: 1.5
  window_chrome: colorful
  font_family: "JetBrains Mono"
  show_cursor: false

chapters:
  - at: 0.0
    label: Start
  - at: 5.0
    label: Build

cuts:
  - from: 2.0
    to: 3.0
    type: ellipsis
"""
        f = tmp_path / "test.termshow.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert script.idle_time_limit == 2.0
        assert script.speed == 1.5
        assert script.window_chrome == "colorful"
        assert script.font_family == "JetBrains Mono"
        assert script.show_cursor is False
        assert len(script.chapters) == 2
        assert script.chapters[0].label == "Start"
        assert script.chapters[1].time == 5.0
        assert len(script.cuts) == 1
        assert script.cuts[0].type == "ellipsis"

    def test_load_with_annotations(self, tmp_path: Path):
        content = """\
annotations:
  - at: 1.0
    duration: 2.5
    text: "Look here!"
    position: top-left
    style: highlight
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert len(script.annotations) == 1
        ann = script.annotations[0]
        assert ann.time == 1.0
        assert ann.duration == 2.5
        assert ann.text == "Look here!"
        assert ann.position == "top-left"
        assert ann.style == "highlight"

    def test_load_with_speed_map(self, tmp_path: Path):
        content = """\
speed_map:
  - from: 1.0
    to: 3.0
    speed: 2.0
  - from: 5.0
    to: 8.0
    speed: 0.5
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert len(script.speed_map) == 2
        assert script.speed_map[0].start == 1.0
        assert script.speed_map[0].speed == 2.0
        assert script.speed_map[1].end == 8.0

    def test_load_with_highlights(self, tmp_path: Path):
        content = """\
highlights:
  - at: 2.0
    duration: 1.5
    region:
      row: 3
      col: 10
      width: 20
      height: 2
    style: glow
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert len(script.highlights) == 1
        hl = script.highlights[0]
        assert hl.time == 2.0
        assert hl.row == 3
        assert hl.col == 10
        assert hl.width == 20
        assert hl.height == 2
        assert hl.style == "glow"

    def test_load_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.yml"
        f.write_text("", encoding="utf-8")

        script = load_script(f)
        assert script.chapters == []
        assert script.cuts == []

    def test_load_invalid_yaml_returns_empty(self, tmp_path: Path):
        # safe_load returns None for empty/comment-only
        f = tmp_path / "comment.yml"
        f.write_text("# just a comment\n", encoding="utf-8")

        script = load_script(f)
        assert isinstance(script, Script)
