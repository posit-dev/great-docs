"""Tests for the _term_player.manifest module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from great_docs._term_player.manifest import (
    KeyframeEntry,
    Manifest,
    _apply_prompt_pattern_substitution,
    _apply_prompt_substitution,
    _compute_keyframe_times,
    _detect_prompt_prefix,
    _find_prompt_char_in_prefix,
    generate_manifest,
)
from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import (
    Annotation,
    Chapter,
    Cut,
    Highlight,
    HighlightTarget,
    Script,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_recording(duration: float = 5.0) -> Recording:
    """Create a minimal recording with output events."""
    events = [
        Event(time=0.0, code="o", data="$ "),
        Event(time=1.0, code="o", data="hello\r\n"),
        Event(time=2.5, code="o", data="world\r\n"),
        Event(time=duration, code="o", data="$ "),
    ]
    return Recording(
        version=1,
        format="termshow",
        term=TermInfo(cols=80, rows=24),
        title="Test Recording",
        events=events,
    )


# ---------------------------------------------------------------------------
# Manifest dataclass
# ---------------------------------------------------------------------------


class TestManifest:
    def test_to_json_basic(self):
        m = Manifest(title="Test", duration=5.0, cols=80, rows=24)
        j = json.loads(m.to_json())
        assert j["title"] == "Test"
        assert j["duration"] == 5.0
        assert j["term"]["cols"] == 80
        assert j["term"]["rows"] == 24

    def test_to_json_includes_chapters(self):
        m = Manifest(chapters=[Chapter(time=1.0, label="Start"), Chapter(time=3.0, label="Build")])
        j = json.loads(m.to_json())
        assert len(j["chapters"]) == 2
        assert j["chapters"][0]["label"] == "Start"
        assert j["chapters"][1]["time"] == 3.0

    def test_to_json_includes_keyframes(self):
        m = Manifest(
            keyframes=[
                KeyframeEntry(time=0.0, file="frame-000.svg"),
                KeyframeEntry(time=2.0, file="frame-001.svg"),
            ]
        )
        j = json.loads(m.to_json())
        assert len(j["keyframes"]) == 2
        assert j["keyframes"][0]["file"] == "frame-000.svg"

    def test_to_json_includes_annotations(self):
        m = Manifest(
            annotations=[Annotation(time=1.0, duration=2.0, text="Note", position="top-left")]
        )
        j = json.loads(m.to_json())
        assert j["annotations"][0]["text"] == "Note"

    def test_to_json_includes_highlights(self):
        m = Manifest(
            highlights=[
                Highlight(
                    time=1.0,
                    duration=1.5,
                    target=HighlightTarget(region={"row": 5, "col": 10, "width": 20, "height": 1}),
                )
            ]
        )
        j = json.loads(m.to_json())
        assert j["highlights"][0]["target"]["region"]["row"] == 5

    def test_to_json_rounds_times(self):
        m = Manifest(duration=5.123456789)
        j = json.loads(m.to_json())
        assert j["duration"] == 5.123


# ---------------------------------------------------------------------------
# _compute_keyframe_times
# ---------------------------------------------------------------------------


class TestComputeKeyframeTimes:
    def test_regular_intervals(self):
        times = _compute_keyframe_times(10.0, 2.0, [])
        assert 0.0 in times
        assert 2.0 in times
        assert 4.0 in times
        assert 6.0 in times
        assert 8.0 in times
        assert 10.0 in times

    def test_includes_chapter_times(self):
        chapters = [Chapter(time=1.5, label="A"), Chapter(time=3.7, label="B")]
        times = _compute_keyframe_times(5.0, 2.0, chapters)
        assert 1.5 in times
        assert 3.7 in times

    def test_deduplicates(self):
        chapters = [Chapter(time=2.0, label="At interval")]
        times = _compute_keyframe_times(4.0, 2.0, chapters)
        # 2.0 appears from both interval and chapter, but only once
        assert times.count(2.0) == 1

    def test_sorted_output(self):
        chapters = [Chapter(time=0.5, label="A"), Chapter(time=3.5, label="B")]
        times = _compute_keyframe_times(4.0, 2.0, chapters)
        assert times == sorted(times)

    def test_zero_duration(self):
        times = _compute_keyframe_times(0.0, 2.0, [])
        assert times == [0.0]


# ---------------------------------------------------------------------------
# generate_manifest
# ---------------------------------------------------------------------------


class TestGenerateManifest:
    def test_generates_keyframes(self):
        rec = _minimal_recording(5.0)
        manifest = generate_manifest(rec, keyframe_interval=2.0)
        assert len(manifest.keyframes) > 0
        assert manifest.keyframes[0].time == 0.0

    def test_duration_matches_recording(self):
        rec = _minimal_recording(5.0)
        manifest = generate_manifest(rec)
        assert manifest.duration == 5.0

    def test_title_from_recording(self):
        rec = _minimal_recording()
        manifest = generate_manifest(rec)
        assert manifest.title == "Test Recording"

    def test_term_dimensions(self):
        rec = _minimal_recording()
        manifest = generate_manifest(rec)
        assert manifest.cols == 80
        assert manifest.rows == 24

    def test_chapters_from_script(self):
        rec = _minimal_recording(5.0)
        script = Script(chapters=[Chapter(time=1.0, label="Start"), Chapter(time=3.0, label="End")])
        manifest = generate_manifest(rec, script)
        assert len(manifest.chapters) == 2
        assert manifest.chapters[0].label == "Start"

    def test_chapters_from_marker_events(self):
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=1.0, code="m", data="Begin"),
            Event(time=3.0, code="o", data="output"),
            Event(time=5.0, code="m", data="Done"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        manifest = generate_manifest(rec)
        assert len(manifest.chapters) == 2
        assert manifest.chapters[0].label == "Begin"
        assert manifest.chapters[1].label == "Done"

    def test_annotations_from_script(self):
        rec = _minimal_recording()
        script = Script(annotations=[Annotation(time=1.0, duration=2.0, text="Hello")])
        manifest = generate_manifest(rec, script)
        assert len(manifest.annotations) == 1
        assert manifest.annotations[0].text == "Hello"

    def test_highlights_from_script(self):
        rec = _minimal_recording()
        script = Script(
            highlights=[
                Highlight(
                    time=1.0,
                    duration=1.0,
                    target=HighlightTarget(region={"row": 0, "col": 0, "width": 5, "height": 1}),
                )
            ]
        )
        manifest = generate_manifest(rec, script)
        assert len(manifest.highlights) == 1

    def test_writes_files_to_output_dir(self, tmp_path: Path):
        rec = _minimal_recording(4.0)
        out = tmp_path / "output"
        manifest = generate_manifest(rec, output_dir=out, keyframe_interval=2.0)

        # Should have manifest.json
        assert (out / "manifest.json").exists()

        # Should have SVG files
        for kf in manifest.keyframes:
            assert (out / kf.file).exists()
            svg_content = (out / kf.file).read_text()
            assert svg_content.startswith("<svg")

    def test_keyframe_at_chapter_time(self):
        rec = _minimal_recording(5.0)
        script = Script(chapters=[Chapter(time=1.5, label="Mid")])
        manifest = generate_manifest(rec, script, keyframe_interval=10.0)
        # With interval=10 and duration=5, only 0.0 would be regular
        # But chapter at 1.5 should also have a keyframe
        times = [kf.time for kf in manifest.keyframes]
        assert 1.5 in times

    def test_render_settings_from_script(self, tmp_path: Path):
        rec = _minimal_recording(2.0)
        script = Script(window_chrome="colorful", font_family="Courier")
        out = tmp_path / "render"
        generate_manifest(rec, script, output_dir=out)

        # First frame SVG should use the script font settings
        svg = (out / "frame-000.svg").read_text()

        assert "Courier" in svg

        # Chrome is rendered by the CSS player, not in the SVG
        assert "circle" not in svg

        # But window_chrome should be in the manifest
        manifest_text = (out / "manifest.json").read_text()
        data = json.loads(manifest_text)

        assert data["window_chrome"] == "colorful"

    def test_manifest_json_valid(self, tmp_path: Path):
        rec = _minimal_recording(3.0)
        out = tmp_path / "json_test"
        generate_manifest(rec, output_dir=out)

        manifest_text = (out / "manifest.json").read_text()
        data = json.loads(manifest_text)
        assert data["version"] == 2
        assert "keyframes" in data
        assert "chapters" in data


# ---------------------------------------------------------------------------
# Prompt substitution helpers
# ---------------------------------------------------------------------------


class TestFindPromptCharInPrefix:
    def test_dollar_sign(self):
        result = _find_prompt_char_in_prefix("$ ")
        assert result == (0, "$")

    def test_dollar_with_path(self):
        result = _find_prompt_char_in_prefix("user@host:~ $ ")
        assert result == (12, "$")

    def test_chevron(self):
        result = _find_prompt_char_in_prefix("❯ ")
        assert result == (0, "❯")

    def test_hash(self):
        result = _find_prompt_char_in_prefix("root# ")
        assert result == (4, "#")

    def test_no_prompt_char(self):
        result = _find_prompt_char_in_prefix("hello ")
        assert result is None

    def test_percent(self):
        result = _find_prompt_char_in_prefix("% ")
        assert result == (0, "%")


class TestDetectPromptPrefix:
    def test_detects_from_input_events(self):
        # Simulate: prompt appears, then user types
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.5, code="i", data="ls"),
            Event(time=1.0, code="o", data="ls\r\nfile1\r\n"),
            Event(time=2.0, code="o", data="$ "),
            Event(time=2.5, code="i", data="pwd"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix == "$ "

    def test_no_input_events(self):
        events = [
            Event(time=0.0, code="o", data="$ hello\r\n"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix is None

    def test_custom_prompt(self):
        events = [
            Event(time=0.0, code="o", data="❯ "),
            Event(time=0.5, code="i", data="git status"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix == "❯ "


class TestApplyPromptSubstitution:
    def _make_screen(self, rows_text: list[str], cols: int = 80) -> "ScreenState":
        """Create a ScreenState from text rows."""
        from great_docs._term_player.emulator import Cell, CellStyle, ScreenState

        n_rows = len(rows_text)
        cells = []
        for text in rows_text:
            row = []
            for i in range(cols):
                ch = text[i] if i < len(text) else " "
                row.append(Cell(char=ch, style=CellStyle()))
            cells.append(row)
        return ScreenState(cols=cols, rows=n_rows, cells=cells)

    def test_substitutes_dollar_prompt(self):
        state = self._make_screen(["$ hello", "output", "$ "])
        result = _apply_prompt_substitution(state, "$ ", "❯")
        # Row 0: "$ " prefix → "$" replaced with "❯"
        assert result.cells[0][0].char == "❯"
        # Row 1: "output" doesn't match → untouched
        assert result.cells[1][0].char == "o"
        # Row 2: "$ " prefix → substituted
        assert result.cells[2][0].char == "❯"

    def test_does_not_touch_dollar_in_output(self):
        state = self._make_screen(["$ echo", "$HOME is set", "$ "])
        result = _apply_prompt_substitution(state, "$ ", "❯")
        # Row 0: matches prefix "$ " → substituted
        assert result.cells[0][0].char == "❯"
        # Row 1: "$HOME" does NOT start with "$ " (no space after) → untouched
        assert result.cells[1][0].char == "$"
        # Row 2: matches
        assert result.cells[2][0].char == "❯"

    def test_does_not_mutate_original(self):
        state = self._make_screen(["$ hello"])
        result = _apply_prompt_substitution(state, "$ ", "→")
        assert state.cells[0][0].char == "$"
        assert result.cells[0][0].char == "→"

    def test_no_match_returns_copy(self):
        state = self._make_screen(["hello", "world"])
        result = _apply_prompt_substitution(state, "$ ", "❯")
        assert result.cells[0][0].char == "h"
        assert result.cells[1][0].char == "w"

    def test_complex_prompt_prefix(self):
        state = self._make_screen(["user@host:~ $ ls", "output"])
        result = _apply_prompt_substitution(state, "user@host:~ $ ", "❯")
        # The $ at col 12 should be replaced
        assert result.cells[0][12].char == "❯"
        # The rest is untouched
        assert result.cells[0][0].char == "u"


class TestApplyPromptPatternSubstitution:
    def _make_screen(self, rows_text: list[str], cols: int = 80) -> "ScreenState":
        from great_docs._term_player.emulator import Cell, CellStyle, ScreenState

        n_rows = len(rows_text)
        cells = []
        for text in rows_text:
            row = []
            for i in range(cols):
                ch = text[i] if i < len(text) else " "
                row.append(Cell(char=ch, style=CellStyle()))
            cells.append(row)
        return ScreenState(cols=cols, rows=n_rows, cells=cells)

    def test_pattern_substitution(self):
        state = self._make_screen(["$ hello", "output", "$ "])
        result = _apply_prompt_pattern_substitution(state, r"^\$ ", "❯")
        assert result.cells[0][0].char == "❯"
        assert result.cells[1][0].char == "o"
        assert result.cells[2][0].char == "❯"

    def test_invalid_regex_returns_unchanged(self):
        state = self._make_screen(["$ hello"])
        result = _apply_prompt_pattern_substitution(state, "[invalid", "❯")
        assert result.cells[0][0].char == "$"

    def test_does_not_match_mid_line(self):
        state = self._make_screen(["echo $HOME", "$ cmd"])
        result = _apply_prompt_pattern_substitution(state, r"^\$ ", "❯")
        # "echo $HOME" doesn't match ^
        assert result.cells[0][5].char == "$"
        # "$ cmd" matches
        assert result.cells[1][0].char == "❯"


class TestPromptSubstitutionIntegration:
    def test_generate_manifest_with_prompt(self, tmp_path: Path):
        """End-to-end test: prompt setting changes rendered SVG content."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.5, code="i", data="ls"),
            Event(time=0.6, code="o", data="ls\r\n"),
            Event(time=1.0, code="o", data="file1.txt\r\n"),
            Event(time=2.0, code="o", data="$ "),
            Event(time=2.5, code="i", data="pwd"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=40, rows=10), title="Prompt Test")
        script = Script(prompt="❯")

        out = tmp_path / "prompt_test"
        manifest = generate_manifest(rec, script, output_dir=out)

        # Read the last frame (should have "$ " → "❯" substituted)
        last_frame = manifest.keyframes[-1].file
        svg = (out / last_frame).read_text()

        # The SVG should contain the substituted prompt char
        assert "❯" in svg
        # Frame at t=0.0 has only "$ " displayed
        first_svg = (out / manifest.keyframes[0].file).read_text()
        assert "❯" in first_svg

    def test_generate_manifest_without_prompt_no_change(self, tmp_path: Path):
        """Without prompt setting, $ renders as-is."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.5, code="i", data="ls"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=40, rows=10))
        script = Script()  # No prompt setting

        out = tmp_path / "no_prompt"
        generate_manifest(rec, script, output_dir=out)

        svg = (out / "frame-000.svg").read_text()
        # Should still have the original $
        assert "$" in svg

    def test_prompt_pattern_fallback(self, tmp_path: Path):
        """When no input events exist, prompt_pattern regex is used."""
        events = [
            Event(time=0.0, code="o", data="$ hello\r\n"),
            Event(time=1.0, code="o", data="output\r\n"),
            Event(time=2.0, code="o", data="$ "),
        ]
        rec = Recording(events=events, term=TermInfo(cols=40, rows=10))
        script = Script(prompt="→", prompt_pattern=r"^\$ ")

        out = tmp_path / "pattern_test"
        generate_manifest(rec, script, output_dir=out)

        # The last frame should have → instead of $
        last_frame_file = sorted(out.glob("frame-*.svg"))[-1]
        svg = last_frame_file.read_text()
        assert "→" in svg


# ---------------------------------------------------------------------------
# _serialize_highlight — uncovered branches
# ---------------------------------------------------------------------------


class TestSerializeHighlight:
    """Cover branches in Manifest._serialize_highlight via to_json()."""

    def _highlight(self, **kw):
        return Highlight(
            time=1.0,
            duration=0.5,
            target=HighlightTarget(
                **{
                    k: v
                    for k, v in kw.items()
                    if k in ("region", "match", "group", "lines", "track_scroll")
                }
            ),
            **{
                k: v
                for k, v in kw.items()
                if k not in ("region", "match", "group", "lines", "track_scroll")
            },
        )

    def test_match_target(self):
        h = self._highlight(match="error")
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["target"]["match"] == "error"

    def test_match_with_group(self):
        h = self._highlight(match="(error)", group=1)
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["target"]["group"] == 1

    def test_match_without_group_no_group_key(self):
        """match set but group=0 (default) → group key absent."""
        h = self._highlight(match="error")
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert "group" not in j["highlights"][0]["target"]

    def test_lines_target(self):
        h = self._highlight(lines=[3, 4, 5])
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["target"]["lines"] == [3, 4, 5]

    def test_track_scroll(self):
        h = self._highlight(track_scroll=True)
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["target"]["track_scroll"] is True

    def test_badge_icon(self):
        h = Highlight(
            time=1.0,
            duration=0.5,
            target=HighlightTarget(region={"row": 0, "col": 0, "width": 5, "height": 1}),
            badge_icon="warning",
        )
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["badge_icon"] == "warning"

    def test_custom_fade_in(self):
        h = Highlight(
            time=1.0,
            duration=0.5,
            target=HighlightTarget(),
            fade_in=0.1,
        )
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["fade_in"] == 0.1

    def test_custom_fade_out(self):
        h = Highlight(
            time=1.0,
            duration=0.5,
            target=HighlightTarget(),
            fade_out=0.5,
        )
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["fade_out"] == 0.5

    def test_pulse(self):
        h = Highlight(
            time=1.0,
            duration=0.5,
            target=HighlightTarget(),
            pulse=True,
        )
        m = Manifest(highlights=[h])
        j = json.loads(m.to_json())
        assert j["highlights"][0]["pulse"] is True


# ---------------------------------------------------------------------------
# generate_manifest — uncovered branches
# ---------------------------------------------------------------------------


class TestGenerateManifestBranches:
    def test_script_theme_applied(self, tmp_path: Path):
        """script.theme being a Theme object overrides the default theme."""
        from great_docs._term_player.parser import Theme

        rec = _minimal_recording(2.0)
        script = Script(theme=Theme(bg="#1e1e1e", fg="#d4d4d4"))
        out = tmp_path / "themed"
        generate_manifest(rec, script, output_dir=out)
        svg = (out / "frame-000.svg").read_text()
        assert "#1e1e1e" in svg

    def test_script_line_height_applied(self, tmp_path: Path):
        """script.line_height being set passes it through to the render."""
        rec = _minimal_recording(2.0)
        script = Script(line_height=1.5)
        out = tmp_path / "lh"
        generate_manifest(rec, script, output_dir=out)
        svg = (out / "frame-000.svg").read_text()
        assert svg.startswith("<svg")

    def test_resize_events_processed(self, tmp_path: Path):
        """'r' events in generate_manifest are handled (resize path)."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.5, code="r", data="40x20"),
            Event(time=1.0, code="o", data="hello"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        out = tmp_path / "resize"
        manifest = generate_manifest(rec, output_dir=out)
        assert len(manifest.keyframes) > 0

    def test_resize_event_bad_format_ignored(self, tmp_path: Path):
        """'r' event with no 'x' separator (len(parts) != 2) is skipped."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.5, code="r", data="badformat"),
            Event(time=1.0, code="o", data="hello"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        out = tmp_path / "bad_resize"
        manifest = generate_manifest(rec, output_dir=out)
        assert len(manifest.keyframes) > 0

    def test_resize_event_non_integer_ignored(self, tmp_path: Path):
        """'r' event with non-integer dimensions raises ValueError, which is caught."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.5, code="r", data="abcxdef"),
            Event(time=1.0, code="o", data="hello"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        out = tmp_path / "bad_resize2"
        manifest = generate_manifest(rec, output_dir=out)
        assert len(manifest.keyframes) > 0

    def test_prompt_replacement_no_prefix_no_pattern(self, tmp_path: Path):
        """prompt set, no input events (prefix=None), no prompt_pattern → no substitution."""
        events = [
            Event(time=0.0, code="o", data="$ hello\r\n"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=40, rows=10))
        script = Script(prompt="❯")  # no input events → prefix=None, no pattern
        out = tmp_path / "no_prefix"
        manifest = generate_manifest(rec, script, output_dir=out)
        assert len(manifest.keyframes) > 0


# ---------------------------------------------------------------------------
# _detect_prompt_prefix — uncovered branches
# ---------------------------------------------------------------------------


class TestDetectPromptPrefixBranches:
    def test_resize_event_in_recording(self):
        """'r' events are processed in _detect_prompt_prefix without error."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.3, code="r", data="40x20"),
            Event(time=0.5, code="i", data="ls"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix is not None

    def test_resize_bad_format_ignored(self):
        """'r' event with bad format (no 'x') is skipped in _detect_prompt_prefix."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.3, code="r", data="badformat"),
            Event(time=0.5, code="i", data="ls"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix == "$ "

    def test_resize_non_integer_caught(self):
        """'r' event with non-integer dimensions raises ValueError, which is caught."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.3, code="r", data="abcxdef"),
            Event(time=0.5, code="i", data="ls"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix == "$ "

    def test_marker_event_ignored(self):
        """'m' events (code != 'o'/'r'/'i') are skipped gracefully."""
        events = [
            Event(time=0.0, code="o", data="$ "),
            Event(time=0.2, code="m", data="chapter"),
            Event(time=0.5, code="i", data="ls"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix == "$ "

    def test_input_event_at_col_zero_skipped(self):
        """'i' event when cursor_col == 0 is skipped (no text captured)."""
        # Only an input event with cursor at col 0 → nothing appended → returns None
        events = [
            Event(time=0.5, code="i", data="x"),
        ]
        rec = Recording(events=events, term=TermInfo(cols=80, rows=24))
        prefix = _detect_prompt_prefix(rec)
        assert prefix is None


# ---------------------------------------------------------------------------
# _apply_prompt_substitution — char_info is None path
# ---------------------------------------------------------------------------


class TestApplyPromptSubstitutionNone:
    def _make_screen(self, rows_text: list[str], cols: int = 80):
        from great_docs._term_player.emulator import Cell, CellStyle, ScreenState

        cells = []
        for text in rows_text:
            row = [
                Cell(char=text[i] if i < len(text) else " ", style=CellStyle()) for i in range(cols)
            ]
            cells.append(row)
        return ScreenState(cols=cols, rows=len(rows_text), cells=cells)

    def test_no_prompt_char_in_prefix_returns_original(self):
        """prefix with no known prompt char → char_info is None → returns state unchanged."""
        state = self._make_screen(["hello world"])
        result = _apply_prompt_substitution(state, "hello ", "❯")
        # "hello " has no $, %, ❯, etc. → returns state as-is
        assert result.cells[0][0].char == "h"


# ---------------------------------------------------------------------------
# _apply_prompt_pattern_substitution — space-only match end
# ---------------------------------------------------------------------------


class TestApplyPromptPatternSubstitutionBranches:
    def _make_screen(self, rows_text: list[str], cols: int = 80):
        from great_docs._term_player.emulator import Cell, CellStyle, ScreenState

        cells = []
        for text in rows_text:
            row = [
                Cell(char=text[i] if i < len(text) else " ", style=CellStyle()) for i in range(cols)
            ]
            cells.append(row)
        return ScreenState(cols=cols, rows=len(rows_text), cells=cells)

    def test_match_ending_in_spaces_iterates_to_nonspace(self):
        """Pattern match where trailing chars are spaces → inner loop finds non-space char."""
        state = self._make_screen(["$  cmd"])
        # Pattern matches "$ " (dollar then two spaces); last char is space → iterate backwards
        result = _apply_prompt_pattern_substitution(state, r"^\$  ", "❯")
        # The "$" at col 0 should be replaced (last non-space in "$ ")
        assert result.cells[0][0].char == "❯"
