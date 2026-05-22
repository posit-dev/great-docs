"""Tests for the _term_player.manifest module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from great_docs._term_player.manifest import (
    DeltaChange,
    DeltaEntry,
    KeyframeEntry,
    Manifest,
    _compute_keyframe_times,
    _delta_change_to_dict,
    generate_manifest,
)
from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import Annotation, Chapter, Cut, Highlight, Script


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
            highlights=[Highlight(time=1.0, duration=1.5, row=5, col=10, width=20, height=1)]
        )
        j = json.loads(m.to_json())
        assert j["highlights"][0]["row"] == 5

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
# _delta_change_to_dict
# ---------------------------------------------------------------------------


class TestDeltaChangeToDict:
    def test_minimal(self):
        change = DeltaChange(row=1, col=5, char="X")
        d = _delta_change_to_dict(change)
        assert d == {"row": 1, "col": 5, "char": "X"}

    def test_with_fg_bg(self):
        change = DeltaChange(row=0, col=0, char="A", fg="#ff0000", bg="#00ff00")
        d = _delta_change_to_dict(change)
        assert d["fg"] == "#ff0000"
        assert d["bg"] == "#00ff00"

    def test_with_bold(self):
        change = DeltaChange(row=0, col=0, char="B", bold=True)
        d = _delta_change_to_dict(change)
        assert d["bold"] is True

    def test_no_optional_fields_when_empty(self):
        change = DeltaChange(row=0, col=0, char=" ")
        d = _delta_change_to_dict(change)
        assert "fg" not in d
        assert "bg" not in d
        assert "bold" not in d


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
            highlights=[Highlight(time=1.0, duration=1.0, row=0, col=0, width=5, height=1)]
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

        # First frame SVG should use the script settings
        svg = (out / "frame-000.svg").read_text()
        assert "Courier" in svg
        assert "circle" in svg  # colorful chrome has circles

    def test_manifest_json_valid(self, tmp_path: Path):
        rec = _minimal_recording(3.0)
        out = tmp_path / "json_test"
        generate_manifest(rec, output_dir=out)

        manifest_text = (out / "manifest.json").read_text()
        data = json.loads(manifest_text)
        assert data["version"] == 1
        assert "keyframes" in data
        assert "chapters" in data
