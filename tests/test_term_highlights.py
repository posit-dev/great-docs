"""Tests for the highlights system (data model, YAML parsing, manifest serialization)."""

from __future__ import annotations

import json

import pytest

from great_docs._term_player.manifest import Manifest, generate_manifest
from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import (
    Highlight,
    HighlightTarget,
    Script,
    _parse_script_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_recording(duration: float = 3.0) -> Recording:
    return Recording(
        term=TermInfo(cols=80, rows=24),
        events=[
            Event(time=0.0, code="o", data="$ hello\r\n"),
            Event(time=1.0, code="o", data="world\r\n"),
            Event(time=duration, code="o", data="$ "),
        ],
    )


# ---------------------------------------------------------------------------
# HighlightTarget dataclass
# ---------------------------------------------------------------------------


class TestHighlightTarget:
    def test_defaults(self):
        t = HighlightTarget()
        assert t.region is None
        assert t.match is None
        assert t.group == 0
        assert t.lines is None
        assert t.track_scroll is False

    def test_region_target(self):
        t = HighlightTarget(region={"row": 3, "col": 5, "width": 20, "height": 2})
        assert t.region["row"] == 3
        assert t.region["width"] == 20

    def test_pattern_target(self):
        t = HighlightTarget(match=r"\d+\.\d+", group=1)
        assert t.match == r"\d+\.\d+"
        assert t.group == 1

    def test_lines_target(self):
        t = HighlightTarget(lines=[0, 1, 2])
        assert t.lines == [0, 1, 2]


# ---------------------------------------------------------------------------
# Highlight dataclass
# ---------------------------------------------------------------------------


class TestHighlight:
    def test_defaults(self):
        h = Highlight(
            time=1.0,
            duration=2.0,
            target=HighlightTarget(region={"row": 0, "col": 0, "width": 10, "height": 1}),
        )
        assert h.style == "outline"
        assert h.color == "#f1fa8c"
        assert h.badge_text == ""
        assert h.badge_icon == ""
        assert h.fade_in == 0.3
        assert h.fade_out == 0.3
        assert h.pulse is False

    def test_all_styles_valid(self):
        valid_styles = [
            "outline",
            "underline",
            "underline-wavy",
            "background",
            "spotlight",
            "glow",
            "box",
            "badge-before",
            "badge-after",
            "bracket",
        ]
        for style in valid_styles:
            h = Highlight(
                time=0.0,
                duration=1.0,
                target=HighlightTarget(),
                style=style,
            )
            assert h.style == style

    def test_legacy_properties(self):
        """Backward-compatible .row, .col, .width, .height properties."""
        h = Highlight(
            time=0.0,
            duration=1.0,
            target=HighlightTarget(region={"row": 5, "col": 10, "width": 20, "height": 3}),
        )
        assert h.row == 5
        assert h.col == 10
        assert h.width == 20
        assert h.height == 3

    def test_legacy_properties_no_region(self):
        """Legacy properties return 0/1 defaults when no region target."""
        h = Highlight(
            time=0.0,
            duration=1.0,
            target=HighlightTarget(match="foo"),
        )
        assert h.row == 0
        assert h.col == 0
        assert h.width == 0
        assert h.height == 1


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------


class TestHighlightParsing:
    def test_region_target(self):
        data = {
            "highlights": [
                {
                    "at": 1.5,
                    "duration": 2.0,
                    "style": "box",
                    "color": "#ff0000",
                    "target": {
                        "region": {"row": 2, "col": 5, "width": 15, "height": 1},
                    },
                }
            ]
        }
        script = _parse_script_data(data)
        assert len(script.highlights) == 1
        h = script.highlights[0]
        assert h.time == 1.5
        assert h.duration == 2.0
        assert h.style == "box"
        assert h.color == "#ff0000"
        assert h.target.region == {"row": 2, "col": 5, "width": 15, "height": 1}

    def test_pattern_target(self):
        data = {
            "highlights": [
                {
                    "at": 0.5,
                    "duration": 3.0,
                    "style": "glow",
                    "target": {"match": r"error:\s+(.+)", "group": 1},
                }
            ]
        }
        script = _parse_script_data(data)
        h = script.highlights[0]
        assert h.target.match == r"error:\s+(.+)"
        assert h.target.group == 1
        assert h.target.region is None

    def test_lines_target(self):
        data = {
            "highlights": [
                {
                    "at": 2.0,
                    "duration": 1.0,
                    "style": "background",
                    "target": {"lines": [3, 4, 5]},
                }
            ]
        }
        script = _parse_script_data(data)
        h = script.highlights[0]
        assert h.target.lines == [3, 4, 5]

    def test_legacy_region_format(self):
        """Old format with 'region' at top level (not nested in 'target')."""
        data = {
            "highlights": [
                {
                    "at": 1.0,
                    "duration": 2.0,
                    "region": {"row": 0, "col": 0, "width": 10, "height": 1},
                    "style": "outline",
                }
            ]
        }
        script = _parse_script_data(data)
        h = script.highlights[0]
        assert h.target.region == {"row": 0, "col": 0, "width": 10, "height": 1}
        assert h.style == "outline"

    def test_badge_fields(self):
        data = {
            "highlights": [
                {
                    "at": 0.0,
                    "duration": 5.0,
                    "style": "badge-before",
                    "badge_text": "NEW",
                    "badge_icon": "⭐",
                    "target": {"region": {"row": 0, "col": 0, "width": 10, "height": 1}},
                }
            ]
        }
        script = _parse_script_data(data)
        h = script.highlights[0]
        assert h.badge_text == "NEW"
        assert h.badge_icon == "⭐"

    def test_animation_fields(self):
        data = {
            "highlights": [
                {
                    "at": 1.0,
                    "duration": 2.0,
                    "fade_in": 0.5,
                    "fade_out": 1.0,
                    "pulse": True,
                    "target": {"region": {"row": 0, "col": 0, "width": 5, "height": 1}},
                }
            ]
        }
        script = _parse_script_data(data)
        h = script.highlights[0]
        assert h.fade_in == 0.5
        assert h.fade_out == 1.0
        assert h.pulse is True

    def test_track_scroll(self):
        data = {
            "highlights": [
                {
                    "at": 0.0,
                    "duration": 1.0,
                    "target": {"lines": [10], "track_scroll": True},
                }
            ]
        }
        script = _parse_script_data(data)
        h = script.highlights[0]
        assert h.target.track_scroll is True

    def test_missing_at_skipped(self):
        """Highlights without 'at' key are skipped."""
        data = {"highlights": [{"duration": 1.0, "style": "box"}]}
        script = _parse_script_data(data)
        assert len(script.highlights) == 0


# ---------------------------------------------------------------------------
# Manifest serialization
# ---------------------------------------------------------------------------


class TestHighlightManifest:
    def test_region_serialization(self):
        m = Manifest(
            highlights=[
                Highlight(
                    time=1.0,
                    duration=2.0,
                    target=HighlightTarget(region={"row": 3, "col": 5, "width": 20, "height": 2}),
                    style="box",
                    color="#00ff00",
                )
            ]
        )
        j = json.loads(m.to_json())
        hl = j["highlights"][0]
        assert hl["time"] == 1.0
        assert hl["duration"] == 2.0
        assert hl["target"]["region"] == {"row": 3, "col": 5, "width": 20, "height": 2}
        assert hl["style"] == "box"
        assert hl["color"] == "#00ff00"

    def test_pattern_serialization(self):
        m = Manifest(
            highlights=[
                Highlight(
                    time=0.0,
                    duration=1.0,
                    target=HighlightTarget(match=r"v\d+\.\d+", group=1),
                    style="underline",
                )
            ]
        )
        j = json.loads(m.to_json())
        hl = j["highlights"][0]
        assert hl["target"]["match"] == r"v\d+\.\d+"
        assert hl["target"]["group"] == 1
        assert "region" not in hl["target"]

    def test_lines_serialization(self):
        m = Manifest(
            highlights=[
                Highlight(
                    time=0.0,
                    duration=1.0,
                    target=HighlightTarget(lines=[0, 1, 2]),
                    style="background",
                )
            ]
        )
        j = json.loads(m.to_json())
        assert j["highlights"][0]["target"]["lines"] == [0, 1, 2]

    def test_badge_fields_serialized(self):
        m = Manifest(
            highlights=[
                Highlight(
                    time=0.0,
                    duration=1.0,
                    target=HighlightTarget(),
                    style="badge-before",
                    badge_text="TIP",
                )
            ]
        )
        j = json.loads(m.to_json())
        assert j["highlights"][0]["badge_text"] == "TIP"

    def test_pulse_serialized(self):
        m = Manifest(
            highlights=[
                Highlight(
                    time=0.0,
                    duration=1.0,
                    target=HighlightTarget(),
                    pulse=True,
                )
            ]
        )
        j = json.loads(m.to_json())
        assert j["highlights"][0]["pulse"] is True

    def test_default_fade_not_serialized(self):
        """Default fade_in/fade_out (0.3) should NOT be in the output."""
        m = Manifest(
            highlights=[
                Highlight(
                    time=0.0,
                    duration=1.0,
                    target=HighlightTarget(),
                )
            ]
        )
        j = json.loads(m.to_json())
        hl = j["highlights"][0]
        assert "fade_in" not in hl
        assert "fade_out" not in hl

    def test_custom_fade_serialized(self):
        m = Manifest(
            highlights=[
                Highlight(
                    time=0.0,
                    duration=1.0,
                    target=HighlightTarget(),
                    fade_in=0.5,
                    fade_out=1.0,
                )
            ]
        )
        j = json.loads(m.to_json())
        hl = j["highlights"][0]
        assert hl["fade_in"] == 0.5
        assert hl["fade_out"] == 1.0

    def test_generate_manifest_includes_highlights(self):
        rec = _minimal_recording()
        script = Script(
            highlights=[
                Highlight(
                    time=0.5,
                    duration=1.0,
                    target=HighlightTarget(region={"row": 0, "col": 0, "width": 5, "height": 1}),
                    style="spotlight",
                )
            ]
        )
        manifest = generate_manifest(rec, script)
        assert len(manifest.highlights) == 1
        assert manifest.highlights[0].style == "spotlight"
