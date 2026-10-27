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
    Snippet,
    SpeedSegment,
    apply_script,
    load_script,
    playback_time,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _events(*times: float) -> list[Event]:
    """Create output events at the given absolute times."""
    return [Event(time=t, code="o", data=f"data_{i}") for i, t in enumerate(times)]


def _recording(events: list[Event]) -> Recording:
    """Create a minimal Recording wrapping some events."""
    return Recording(events=events)


def _times(script: Script, *times: float) -> list[float]:
    """Retime events at the given recording times through a script."""
    return [e.time for e in apply_script(_recording(_events(*times)), script).events]


# ---------------------------------------------------------------------------
# Cuts
# ---------------------------------------------------------------------------


class TestCuts:
    def test_no_cuts(self):
        assert _times(Script(), 0.0, 1.0, 2.0, 3.0) == pytest.approx([0.0, 1.0, 2.0, 3.0])

    def test_cut_adjusts_timing(self):
        # A 1s cut: later events move 1s earlier
        times = _times(Script(cuts=[Cut(start=1.5, end=2.5)]), 0.0, 1.0, 2.0, 3.0, 4.0)
        assert times == pytest.approx([0.0, 1.0, 1.5, 2.0, 3.0])

    def test_events_in_cut_are_kept_at_cut_start(self):
        # Output printed during a cut still reaches the screen, all at once
        result = apply_script(
            _recording(_events(0.0, 1.0, 2.0, 3.0, 4.0, 5.0)),
            Script(cuts=[Cut(start=1.5, end=3.5)]),
        )
        assert [e.data for e in result.events] == [f"data_{i}" for i in range(6)]
        assert [e.time for e in result.events] == pytest.approx([0.0, 1.0, 1.5, 1.5, 2.0, 3.0])

    def test_multiple_cuts(self):
        times = _times(
            Script(cuts=[Cut(start=0.5, end=1.5), Cut(start=4.5, end=5.5)]),
            0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0,
        )  # fmt: skip
        assert times == pytest.approx([0.0, 0.5, 1.0, 2.0, 3.0, 3.5, 4.0])

    def test_events_at_cut_boundaries(self):
        times = _times(Script(cuts=[Cut(start=1.0, end=2.0)]), 0.0, 1.0, 2.0, 3.0)
        assert times == pytest.approx([0.0, 1.0, 1.0, 2.0])

    def test_overlapping_cuts_remove_their_union(self):
        times = _times(Script(cuts=[Cut(start=1.0, end=3.0), Cut(start=2.0, end=4.0)]), 0.0, 5.0)
        assert times == pytest.approx([0.0, 2.0])

    def test_cut_hiding_final_output(self):
        # The last output happens inside the cut, but the final screen still shows it
        result = apply_script(
            _recording(_events(0.0, 1.0, 3.0)), Script(cuts=[Cut(start=2.0, end=5.0)])
        )
        assert [e.time for e in result.events] == pytest.approx([0.0, 1.0, 2.0])
        assert result.events[-1].data == "data_2"


# ---------------------------------------------------------------------------
# Speed map
# ---------------------------------------------------------------------------


def _speed(*segments: SpeedSegment) -> Script:
    return Script(speed_map=list(segments))


class TestSpeedMap:
    def test_time_before_segment_is_unchanged(self):
        f = playback_time(_speed(SpeedSegment(start=10.0, end=20.0, speed=2.0)))
        assert f(5.0) == pytest.approx(5.0)
        assert f(10.0) == pytest.approx(10.0)

    def test_time_inside_segment(self):
        # Segment [2, 6] at 2x: 2s before + 2s/2
        f = playback_time(_speed(SpeedSegment(start=2.0, end=6.0, speed=2.0)))
        assert f(4.0) == pytest.approx(3.0)

    def test_time_after_segment(self):
        # 2s before + 4s/2 + 2s after
        f = playback_time(_speed(SpeedSegment(start=2.0, end=6.0, speed=2.0)))
        assert f(8.0) == pytest.approx(6.0)

    def test_slow_speed(self):
        # Segment [1, 3] at 0.5x: 1s before + 2s/0.5
        f = playback_time(_speed(SpeedSegment(start=1.0, end=3.0, speed=0.5)))
        assert f(3.0) == pytest.approx(5.0)

    def test_multiple_segments(self):
        f = playback_time(
            _speed(
                SpeedSegment(start=5.0, end=7.0, speed=0.5),  # 2s → 4s
                SpeedSegment(start=1.0, end=3.0, speed=2.0),  # 2s → 1s
            )
        )
        # 1 + 2/2 + 2 + 2/0.5 + 3
        assert f(10.0) == pytest.approx(11.0)

    def test_events_before_between_and_after_segments(self):
        times = _times(
            _speed(
                SpeedSegment(start=2.0, end=4.0, speed=2.0),
                SpeedSegment(start=6.0, end=8.0, speed=4.0),
            ),
            0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 9.0,
        )  # fmt: skip
        assert times == pytest.approx([0.0, 1.0, 2.0, 2.5, 3.0, 4.0, 5.0, 5.5, 6.5])

    def test_overlapping_segments_earlier_start_wins(self):
        f = playback_time(
            _speed(
                SpeedSegment(start=2.0, end=6.0, speed=4.0),
                SpeedSegment(start=0.0, end=4.0, speed=2.0),
            )
        )
        # [0, 4] at 2x, then [4, 6] at 4x
        assert f(6.0) == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Cuts and speed map together
# ---------------------------------------------------------------------------


class TestCutsWithSpeedMap:
    def test_speed_map_uses_recording_timeline(self):
        # The segment refers to [4, 6] in the recording, not 4s into playback
        script = Script(
            cuts=[Cut(start=1.0, end=3.0)],
            speed_map=[SpeedSegment(start=4.0, end=6.0, speed=2.0)],
        )
        assert _times(script, 0.0, 2.0, 4.0, 6.0, 8.0) == pytest.approx([0.0, 1.0, 2.0, 3.0, 5.0])

    def test_cut_inside_speed_segment(self):
        # [0, 8] at 2x with [2, 4] cut: 2/2 + 4/2
        script = Script(
            cuts=[Cut(start=2.0, end=4.0)],
            speed_map=[SpeedSegment(start=0.0, end=8.0, speed=2.0)],
        )
        assert _times(script, 2.0, 3.0, 8.0) == pytest.approx([1.0, 1.0, 3.0])

    def test_segment_overlapping_cut_only_scales_the_rest(self):
        # Segment [2, 6] at 2x, cut [1, 3]: only [3, 6] is sped up
        script = Script(
            cuts=[Cut(start=1.0, end=3.0)],
            speed_map=[SpeedSegment(start=2.0, end=6.0, speed=2.0)],
        )
        assert _times(script, 6.0, 7.0) == pytest.approx([2.5, 3.5])

    def test_global_speed_applies_last(self):
        script = Script(
            speed=2.0,
            cuts=[Cut(start=1.0, end=3.0)],
            speed_map=[SpeedSegment(start=3.0, end=7.0, speed=4.0)],
        )
        # (1 + 4/4 + 1) / 2
        assert _times(script, 8.0) == pytest.approx([1.5])

    def test_times_never_decrease(self):
        script = Script(
            cuts=[Cut(start=0.5, end=1.25), Cut(start=3.0, end=3.5)],
            speed_map=[
                SpeedSegment(start=1.0, end=2.0, speed=3.0),
                SpeedSegment(start=1.5, end=4.0, speed=0.5),
            ],
        )
        times = _times(script, *[i / 4 for i in range(24)])
        assert times == sorted(times)


# ---------------------------------------------------------------------------
# apply_script (integration)
# ---------------------------------------------------------------------------


class TestApplyScript:
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
        # The event at 2.0 is kept, at the cut's start
        assert [e.time for e in result.events] == pytest.approx([0.0, 1.0, 1.5, 2.0, 3.0])

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

    def test_load_with_prompt_setting(self, tmp_path: Path):
        content = """\
settings:
  prompt: "❯"
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert script.prompt == "❯"
        assert script.prompt_pattern is None

    def test_load_with_prompt_and_pattern(self, tmp_path: Path):
        content = """\
settings:
  prompt: "→"
  prompt_pattern: '^\\$ '
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert script.prompt == "→"
        assert script.prompt_pattern == r"^\$ "

    def test_load_prompt_null_stays_none(self, tmp_path: Path):
        content = """\
settings:
  prompt: null
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert script.prompt is None

    def test_load_with_snippets(self, tmp_path: Path):
        """Snippets section is parsed into Script.snippets."""
        content = """\
snippets:
  - at: 1.0
    text: "pip install mylib"
    duration: 4.0
    label: Install
  - at: 5.0
    match: "def my_func"
    label: Definition
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert len(script.snippets) == 2
        assert script.snippets[0].text == "pip install mylib"
        assert script.snippets[0].duration == 4.0
        assert script.snippets[0].label == "Install"
        assert script.snippets[1].match == "def my_func"

    def test_load_invalid_list_items_skipped(self, tmp_path: Path):
        """Non-dict or incomplete items in lists are silently skipped."""
        content = """\
chapters:
  - 42
  - missing_at_key: value
  - at: 1.0
    label: Valid

cuts:
  - not_a_cut: true
  - from: 1.0
    to: 2.0

annotations:
  - missing_at: x
  - at: 3.0
    text: Note

speed_map:
  - bad_item: 1
  - from: 0.0
    to: 2.0
    speed: 2.0

snippets:
  - missing_at: true
  - at: 1.0
    duration: 2.0
  - at: 2.0
    text: Valid snippet
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert len(script.chapters) == 1
        assert script.chapters[0].label == "Valid"
        assert len(script.cuts) == 1
        assert len(script.annotations) == 1
        assert len(script.speed_map) == 1
        assert len(script.snippets) == 1
        assert script.snippets[0].text == "Valid snippet"

    def test_load_non_dict_settings_ignored(self, tmp_path: Path):
        """When settings: is not a dict, defaults are used."""
        content = "settings: null\n"
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert script.speed == 1.0
        assert script.window_chrome == "none"

    def test_load_highlight_non_dict_target_defaults_empty(self, tmp_path: Path):
        """A non-dict 'target' value is treated as an empty target."""
        content = """\
highlights:
  - at: 1.0
    target: "not a dict"
    style: outline
"""
        f = tmp_path / "test.yml"
        f.write_text(content, encoding="utf-8")

        script = load_script(f)
        assert len(script.highlights) == 1
        hl = script.highlights[0]
        assert hl.target.region is None
        assert hl.target.match is None


class TestApplyScriptSpeedMap:
    def test_speed_map_applied_through_apply_script(self):
        """apply_script retimes events through the speed map."""
        events = _events(0.0, 2.0, 4.0, 6.0)
        rec = _recording(events)
        script = Script(speed_map=[SpeedSegment(start=2.0, end=4.0, speed=2.0)])
        result = apply_script(rec, script)
        # Only the 2s inside the segment is halved
        assert [e.time for e in result.events] == pytest.approx([0.0, 2.0, 3.0, 5.0])
