"""Tests for the _term_player.editor module (data pass and YAML serializer)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

from yaml12 import parse_yaml
import pytest

from great_docs._term_player.editor import _build_editor_data, _kept_sections, _serialize_script
from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import (
    Annotation,
    Chapter,
    Cut,
    Highlight,
    HighlightTarget,
    Script,
    Snippet,
    SpeedSegment,
    _parse_script_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_recording(**kwargs) -> Recording:
    """Create a minimal Recording for testing."""
    duration = kwargs.pop("duration", 10.0)
    defaults = {
        "events": [Event(time=duration, code="o", data="")],
        "term": TermInfo(cols=80, rows=24),
        "title": "test",
    }
    defaults.update(kwargs)
    return Recording(**defaults)


def _make_script(**kwargs) -> Script:
    """Create a Script with sensible defaults, overridable via kwargs."""
    defaults = {
        "source": "demo.termshow",
        "speed": 1.0,
        "window_chrome": "colorful",
        "font_family": None,
        "prompt": None,
        "prompt_pattern": None,
        "chapters": [],
        "annotations": [],
        "cuts": [],
        "snippets": [],
    }
    defaults.update(kwargs)
    return Script(**defaults)


# ---------------------------------------------------------------------------
# _build_editor_data
# ---------------------------------------------------------------------------


class TestBuildEditorData:
    """Tests for _build_editor_data()."""

    def test_settings_defaults_no_script(self):
        rec = _make_recording()
        data = _build_editor_data(rec, None)
        s = data["script"]["settings"]
        assert s["speed"] == 1.0
        assert s["window_chrome"] == "colorful"
        assert s["font_family"] is None
        assert s["prompt"] is None
        assert s["prompt_pattern"] is None

    def test_settings_with_all_fields(self):
        script = _make_script(
            speed=1.5,
            window_chrome="minimal",
            font_family="JetBrains Mono, monospace",
            prompt="❯",
            prompt_pattern=r"^\$ ",
        )
        data = _build_editor_data(_make_recording(), script)
        s = data["script"]["settings"]
        assert s["speed"] == 1.5
        assert s["window_chrome"] == "minimal"
        assert s["font_family"] == "JetBrains Mono, monospace"
        assert s["prompt"] == "❯"
        assert s["prompt_pattern"] == r"^\$ "

    def test_settings_prompt_none(self):
        script = _make_script(prompt=None, prompt_pattern=None)
        data = _build_editor_data(_make_recording(), script)
        s = data["script"]["settings"]
        assert s["prompt"] is None
        assert s["prompt_pattern"] is None

    def test_chapters_passed_through(self):
        script = _make_script(
            chapters=[
                Chapter(time=0.0, label="Intro"),
                Chapter(time=5.0, label="Demo"),
            ]
        )
        data = _build_editor_data(_make_recording(), script)
        chs = data["script"]["chapters"]
        assert len(chs) == 2
        assert chs[0] == {"time": 0.0, "label": "Intro"}
        assert chs[1] == {"time": 5.0, "label": "Demo"}

    def test_annotations_passed_through(self):
        script = _make_script(
            annotations=[
                Annotation(
                    time=1.0, duration=3.0, text="Hello", position="top-right", style="callout"
                ),
            ]
        )
        data = _build_editor_data(_make_recording(), script)
        anns = data["script"]["annotations"]
        assert len(anns) == 1
        assert anns[0]["text"] == "Hello"
        assert anns[0]["position"] == "top-right"

    def test_cuts_passed_through(self):
        script = _make_script(
            cuts=[
                Cut(start=2.0, end=4.0, type="ellipsis"),
            ]
        )
        data = _build_editor_data(_make_recording(), script)
        cuts = data["script"]["cuts"]
        assert len(cuts) == 1
        assert cuts[0] == {"start": 2.0, "end": 4.0, "type": "ellipsis"}

    def test_snippets_passed_through(self):
        script = _make_script(
            snippets=[
                Snippet(time=1.0, duration=5.0, text="pip install x", match="", label="Install"),
            ]
        )
        data = _build_editor_data(_make_recording(), script)
        snips = data["script"]["snippets"]
        assert len(snips) == 1
        assert snips[0]["text"] == "pip install x"
        assert snips[0]["label"] == "Install"

    def test_recording_fields(self):
        rec = _make_recording(
            events=[Event(time=0.5, code="o", data="hello"), Event(time=5.0, code="o", data="")],
            title="My Demo",
        )
        data = _build_editor_data(rec, _make_script())
        r = data["recording"]
        assert r["title"] == "My Demo"
        assert r["duration"] == 5.0
        assert r["term"] == {"cols": 80, "rows": 24}
        assert len(r["events"]) == 2
        assert r["events"][0] == {"time": 0.5, "code": "o", "data": "hello"}


# ---------------------------------------------------------------------------
# _serialize_script
# ---------------------------------------------------------------------------


class TestSerializeScript:
    """Tests for _serialize_script()."""

    def test_minimal_settings(self):
        """Only window_chrome set (speed=1.0 is default, so omitted)."""
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["source"] == "demo.termshow"
        assert parsed["settings"]["window_chrome"] == "colorful"
        assert "prompt" not in parsed["settings"]
        assert "prompt_pattern" not in parsed["settings"]
        assert "font_family" not in parsed["settings"]

    def test_prompt_serialized(self):
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": "❯",
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["settings"]["prompt"] == "❯"
        assert "prompt_pattern" not in parsed["settings"]

    def test_prompt_and_pattern_serialized(self):
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": "→",
                "prompt_pattern": r"^\$ ",
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["settings"]["prompt"] == "→"
        assert parsed["settings"]["prompt_pattern"] == r"^\$ "

    def test_font_family_single(self):
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": "JetBrains Mono",
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["settings"]["font_family"] == "JetBrains Mono"

    def test_font_family_comma_list(self):
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": "JetBrains Mono, Fira Code, monospace",
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["settings"]["font_family"] == "JetBrains Mono, Fira Code, monospace"

    def test_speed_non_default_serialized(self):
        script_data = {
            "settings": {
                "speed": 2.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["settings"]["speed"] == 2.0

    def test_speed_default_omitted(self):
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert "speed" not in parsed["settings"]

    def test_chapters_serialized_sorted(self):
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [
                {"time": 5.0, "label": "Second"},
                {"time": 0.0, "label": "First"},
            ],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["chapters"][0]["label"] == "First"
        assert parsed["chapters"][1]["label"] == "Second"

    def test_snippets_with_match(self):
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [
                {"time": 1.0, "duration": 5.0, "text": "", "match": r"\$ (.+)", "label": "cmd"},
            ],
        }
        yaml_str = _serialize_script(script_data, "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["snippets"][0]["match"] == r"\$ (.+)"
        assert parsed["snippets"][0]["label"] == "cmd"

    def test_all_settings_combined(self):
        """Full settings with every field populated."""
        script_data = {
            "settings": {
                "speed": 3.0,
                "window_chrome": "minimal",
                "font_family": "Fira Code, monospace",
                "prompt": "$",
                "prompt_pattern": r"^\$ ",
            },
            "chapters": [{"time": 0.0, "label": "Start"}],
            "annotations": [
                {
                    "time": 1.0,
                    "duration": 2.0,
                    "text": "Hi",
                    "position": "top-right",
                    "style": "callout",
                    "width": "medium",
                }
            ],
            "cuts": [{"start": 3.0, "end": 4.0, "type": "jump"}],
            "snippets": [
                {"time": 0.5, "duration": 3.0, "text": "echo hello", "match": "", "label": "Run"}
            ],
        }
        yaml_str = _serialize_script(script_data, "rec.termshow")
        parsed = parse_yaml(yaml_str)
        s = parsed["settings"]
        assert s["speed"] == 3.0
        assert s["window_chrome"] == "minimal"
        assert s["font_family"] == "Fira Code, monospace"
        assert s["prompt"] == "$"
        assert s["prompt_pattern"] == r"^\$ "
        assert len(parsed["chapters"]) == 1
        assert len(parsed["annotations"]) == 1
        assert len(parsed["cuts"]) == 1
        assert len(parsed["snippets"]) == 1

    def test_empty_script(self):
        """All None/empty produces minimal YAML."""
        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": None,
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
        }
        yaml_str = _serialize_script(script_data, "x.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["source"] == "x.termshow"
        # No chapters/annotations/cuts/snippets keys when empty
        assert parsed.get("chapters") is None
        assert parsed.get("annotations") is None
        assert parsed.get("cuts") is None
        assert parsed.get("snippets") is None


class TestKeptSections:
    """The editor doesn't edit `record:` or `steps:`, so a save keeps them as written."""

    _TEXT = (
        "source: demo.termshow\n"
        "record:\n"
        "  shell: bash --norc  # no rc files\n"
        "  cols: 90\n"
        "chapters:\n"
        "  - at: 1\n"
        "    label: Old\n"
        "steps:\n"
        "  - run: ls\n"
        "  # Pause before the next one\n"
        "  - sleep: 1\n"
        "\n"
        "  - enter\n"
    )

    def test_extracts_sections_as_written(self):
        assert _kept_sections(self._TEXT) == (
            "record:\n"
            "  shell: bash --norc  # no rc files\n"
            "  cols: 90\n"
            "\n"
            "steps:\n"
            "  - run: ls\n"
            "  # Pause before the next one\n"
            "  - sleep: 1\n"
            "\n"
            "  - enter\n"
            "\n"
        )

    def test_nothing_to_keep(self):
        assert _kept_sections("source: demo.termshow\nchapters: []\n") == ""

    def test_save_keeps_them(self):
        script_data = {"settings": {}, "chapters": [{"time": 2.0, "label": "New"}]}
        yaml_str = _serialize_script(script_data, "demo.termshow", _kept_sections(self._TEXT))
        parsed = parse_yaml(yaml_str)
        assert parsed["record"] == {"shell": "bash --norc", "cols": 90}
        assert parsed["steps"] == [{"run": "ls"}, {"sleep": 1}, "enter"]
        assert parsed["chapters"] == [{"at": 2.0, "label": "New"}]


# ---------------------------------------------------------------------------
# Round-trip: _build_editor_data → _serialize_script → parse_yaml
# ---------------------------------------------------------------------------


class TestEditorRoundTrip:
    """Test that data passes through build → serialize → parse intact."""

    def test_settings_round_trip(self):
        script = _make_script(
            speed=1.5,
            window_chrome="minimal",
            font_family="Cascadia Code",
            prompt="❯",
            prompt_pattern=r"^\$ ",
        )
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = parse_yaml(yaml_str)
        s = parsed["settings"]
        assert s["speed"] == 1.5
        assert s["window_chrome"] == "minimal"
        assert s["font_family"] == "Cascadia Code"
        assert s["prompt"] == "❯"
        assert s["prompt_pattern"] == r"^\$ "

    def test_prompt_round_trip_none(self):
        script = _make_script(prompt=None, prompt_pattern=None)
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert "prompt" not in parsed["settings"]
        assert "prompt_pattern" not in parsed["settings"]

    def test_font_family_round_trip_list(self):
        script = _make_script(font_family="JetBrains Mono, Fira Code, monospace")
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["settings"]["font_family"] == "JetBrains Mono, Fira Code, monospace"

    def test_theme_name_round_trip(self):
        """A named theme survives open → save in the editor."""
        script = _parse_script_data({"settings": {"theme": "dracula"}})
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        reparsed = _parse_script_data(parse_yaml(yaml_str))
        assert reparsed.theme_name == "dracula"
        assert reparsed.theme.bg == "#282a36"

    def test_inline_theme_round_trip(self):
        """An inline theme mapping survives open → save with its colors intact."""
        spec = {"base": "nord", "bg": "#000000"}
        script = _parse_script_data({"settings": {"theme": spec}})
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        reparsed = _parse_script_data(parse_yaml(yaml_str))
        assert reparsed.theme_spec == spec
        assert reparsed.theme.bg == "#000000"
        assert reparsed.theme.fg == "#d8dee9"

    @pytest.mark.parametrize(
        "spec",
        [
            "auto",
            {
                "light": "catppuccin-latte",
                "dark": {"base": "catppuccin-mocha", "cursor": "#ff0000"},
            },
        ],
    )
    def test_theme_pair_round_trip(self, spec):
        """A light/dark pair survives open → save with both sides intact."""
        script = _parse_script_data({"settings": {"theme": spec}})
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        reparsed = _parse_script_data(parse_yaml(yaml_str))
        assert reparsed.theme_spec == spec
        assert reparsed.theme == script.theme
        assert reparsed.dark_theme == script.dark_theme

    def test_line_height_and_show_cursor_round_trip(self):
        script = _make_script(line_height=1.2, show_cursor=False)
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = parse_yaml(yaml_str)
        assert parsed["settings"]["line_height"] == 1.2
        assert parsed["settings"]["show_cursor"] is False

    def test_default_settings_omit_settings_block(self):
        """No `settings:` key is written when every setting is at its default."""
        script = _make_script(window_chrome=None)
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        assert "settings" not in parse_yaml(yaml_str)

    def test_full_round_trip(self):
        script = _make_script(
            speed=2.0,
            window_chrome="colorful",
            font_family="Menlo",
            prompt=">",
            chapters=[Chapter(time=0.0, label="Start"), Chapter(time=5.0, label="End")],
            annotations=[
                Annotation(
                    time=1.0, duration=3.0, text="Note", position="top-right", style="subtle"
                )
            ],
            cuts=[Cut(start=2.0, end=3.0, type="ellipsis")],
            snippets=[Snippet(time=0.5, duration=4.0, text="echo hi", label="Run")],
        )
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = parse_yaml(yaml_str)

        assert parsed["settings"]["prompt"] == ">"
        assert parsed["settings"]["font_family"] == "Menlo"
        assert len(parsed["chapters"]) == 2
        assert parsed["chapters"][0]["label"] == "Start"
        assert len(parsed["annotations"]) == 1
        assert parsed["annotations"][0]["text"] == "Note"
        assert len(parsed["cuts"]) == 1
        assert len(parsed["snippets"]) == 1
        assert parsed["snippets"][0]["text"] == "echo hi"


# ---------------------------------------------------------------------------
# _serialize_script
# ---------------------------------------------------------------------------


class TestSerializeScriptMissingBranches:
    def _base_data(self) -> dict:
        return {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
            "highlights": [],
        }

    def test_annotation_non_medium_width(self):
        """Annotation width != 'medium' emits a width: line."""
        data = self._base_data()
        data["annotations"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "text": "Look!",
                "position": "top-right",
                "style": "callout",
                "width": "wide",
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "width: wide" in result

    def test_annotation_medium_width_omitted(self):
        """Annotation with width='medium' (default) does NOT emit width:."""
        data = self._base_data()
        data["annotations"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "text": "Look!",
                "position": "top-right",
                "style": "callout",
                "width": "medium",
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "width:" not in result

    def test_all_none_settings_skips_settings_block(self):
        """When all settings values are None, the settings: block is omitted."""
        data = self._base_data()
        data["settings"] = {
            "speed": None,
            "window_chrome": None,
            "font_family": None,
            "prompt": None,
            "prompt_pattern": None,
        }
        result = _serialize_script(data, "demo.termshow")
        assert "settings:" not in result

    def test_snippet_with_text_only(self):
        """Snippet with text but no match or label."""
        data = self._base_data()
        data["snippets"] = [
            {"time": 2.0, "duration": 3.0, "text": "echo hello", "match": "", "label": ""},
        ]
        result = _serialize_script(data, "demo.termshow")
        parsed = parse_yaml(result)
        assert parsed["snippets"][0]["text"] == "echo hello"
        assert "match" not in result or "match: ''" not in result

    def test_snippet_with_match_only(self):
        """Snippet with match but no text."""
        data = self._base_data()
        data["snippets"] = [
            {"time": 2.0, "duration": 3.0, "text": "", "match": "def my_func", "label": ""},
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "match: 'def my_func'" in result
        assert "text:" not in result

    def test_snippet_with_all_fields(self):
        """Snippet with text, match and label all set."""
        data = self._base_data()
        data["snippets"] = [
            {
                "time": 2.0,
                "duration": 3.0,
                "text": "pip install x",
                "match": "install",
                "label": "Install cmd",
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert 'text: "pip install x"' in result
        assert "match: 'install'" in result
        assert 'label: "Install cmd"' in result

    def test_highlight_with_custom_color(self):
        """Highlight with a non-default color emits color: line."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "outline",
                "color": "#ff0000",
                "target": {},
                "badge_text": "",
                "pulse": False,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "color: '#ff0000'" in result

    def test_highlight_default_color_omitted(self):
        """Highlight with default color (#f1fa8c) does NOT emit color:."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "outline",
                "color": "#f1fa8c",
                "target": {},
                "badge_text": "",
                "pulse": False,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "color:" not in result

    def test_highlight_target_with_region(self):
        """Highlight target with region dict emits region YAML inline."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "box",
                "color": "#f1fa8c",
                "target": {"region": {"row": 3, "col": 5, "width": 20, "height": 2}},
                "badge_text": "",
                "pulse": False,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "region:" in result
        assert "row: 3" in result

    def test_highlight_target_with_match_and_group(self):
        """Highlight target with match + group."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "outline",
                "color": "#f1fa8c",
                "target": {"match": "ERROR", "group": 1},
                "badge_text": "",
                "pulse": False,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "match: 'ERROR'" in result
        assert "group: 1" in result

    def test_highlight_target_match_without_group(self):
        """Highlight target with match but group=0 omits the group line."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "outline",
                "color": "#f1fa8c",
                "target": {"match": "ERROR", "group": 0},
                "badge_text": "",
                "pulse": False,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "match: 'ERROR'" in result
        assert "group:" not in result

    def test_highlight_target_with_lines_and_track_scroll(self):
        """Highlight target with lines list and track_scroll."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "outline",
                "color": "#f1fa8c",
                "target": {"lines": [5, 6, 7], "track_scroll": True},
                "badge_text": "",
                "pulse": False,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "lines:" in result
        assert "track_scroll: true" in result

    def test_highlight_with_badge_text(self):
        """Highlight with badge_text emits badge_text: line."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "outline",
                "color": "#f1fa8c",
                "target": {},
                "badge_text": "✦ note",
                "pulse": False,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert 'badge_text: "✦ note"' in result

    def test_highlight_with_pulse(self):
        """Highlight with pulse=True emits pulse: true."""
        data = self._base_data()
        data["highlights"] = [
            {
                "time": 1.0,
                "duration": 2.0,
                "style": "outline",
                "color": "#f1fa8c",
                "target": {},
                "badge_text": "",
                "pulse": True,
            },
        ]
        result = _serialize_script(data, "demo.termshow")
        assert "pulse: true" in result


# ---------------------------------------------------------------------------
# EditorHandler HTTP methods
# ---------------------------------------------------------------------------


class TestEditorHandler:
    """Unit tests for EditorHandler using a mock transport layer."""

    def _make_handler(self, method: str, path: str, body: bytes = b"") -> "EditorHandler":
        """Create an EditorHandler instance with a fake socket."""
        import io
        from great_docs._term_player.editor import EditorHandler

        class FakeSocket:
            def makefile(self, *a, **k):
                return io.BytesIO(body)

        class FakeRequest(FakeSocket):
            pass

        # Build a minimal HTTP request
        content_length = len(body)
        request_line = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {content_length}\r\n\r\n"
        raw = request_line.encode() + body

        rfile = io.BytesIO(raw)
        wfile = io.BytesIO()

        handler = EditorHandler.__new__(EditorHandler)
        handler.rfile = rfile
        handler.wfile = wfile
        handler.headers = {"Content-Length": str(content_length)}
        handler.path = path
        handler.server = None

        # Pre-read past the HTTP headers in rfile to simulate BaseHTTPRequestHandler state
        handler.rfile = io.BytesIO(body)

        handler.editor_data = {
            "recording": {
                "title": "test",
                "duration": 5.0,
                "term": {"cols": 80, "rows": 24},
                "events": [],
            },
            "script": {
                "settings": {},
                "chapters": [],
                "annotations": [],
                "cuts": [],
                "snippets": [],
                "highlights": [],
            },
        }
        handler.source_path = "demo.termshow"
        import tempfile
        from pathlib import Path

        handler.script_path = Path(tempfile.mktemp(suffix=".termshow.yml"))

        # Track writes
        handler._response_data = wfile
        handler._sent_responses = []

        def mock_send_response(code, msg=None):
            handler._sent_responses.append(code)

        def mock_send_header(key, val):
            pass

        def mock_end_headers():
            pass

        def mock_send_error(code, msg=None):
            handler._sent_responses.append(f"error-{code}")

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers
        handler.send_error = mock_send_error

        return handler

    def test_do_get_root_calls_serve_editor_page(self):
        """GET / triggers _serve_editor_page."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import _get_editor_html

        handler = self._make_handler("GET", "/")
        called = []
        original = (
            handler._serve_editor_page.__func__
            if hasattr(handler._serve_editor_page, "__func__")
            else None
        )

        import io

        handler.wfile = io.BytesIO()
        with patch.object(type(handler), "_serve_editor_page", lambda self: called.append(True)):
            handler.do_GET()
        assert called

    def test_do_get_api_data_returns_json(self):
        """GET /api/data calls _json_response with editor_data."""
        from unittest.mock import patch
        import io

        handler = self._make_handler("GET", "/api/data")
        handler.wfile = io.BytesIO()
        called_with = []

        with patch.object(
            type(handler), "_json_response", lambda self, d, **kw: called_with.append(d)
        ):
            handler.do_GET()
        assert len(called_with) == 1
        assert "recording" in called_with[0]

    def test_do_get_unknown_path_sends_404(self):
        """GET /unknown sends a 404 error."""
        from unittest.mock import patch
        import io

        handler = self._make_handler("GET", "/unknown-path")
        handler.wfile = io.BytesIO()
        handler.do_GET()
        assert any("error-404" in str(r) for r in handler._sent_responses)

    def test_do_post_api_save_success(self, tmp_path):
        """POST /api/save with valid JSON saves YAML and responds {ok: true}."""
        import json, io

        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
            "highlights": [],
        }
        body = json.dumps(script_data).encode()
        handler = self._make_handler("POST", "/api/save", body)
        handler.script_path = tmp_path / "demo.termshow.yml"
        handler.wfile = io.BytesIO()
        responses = []
        handler._json_response = lambda d, **kw: responses.append(d)
        handler.do_POST()
        assert handler.script_path.exists()
        assert responses[0]["ok"] is True

    def test_do_post_api_save_exception(self):
        """POST /api/save with invalid JSON returns {ok: false, error: ...}."""
        import io

        handler = self._make_handler("POST", "/api/save", b"not-json{{{")
        handler.wfile = io.BytesIO()
        responses = []
        handler._json_response = lambda d, **kw: responses.append((d, kw))
        handler.do_POST()
        assert responses[0][0]["ok"] is False
        assert "error" in responses[0][0]

    def test_do_post_api_preview_yaml_success(self):
        """POST /api/preview-yaml returns the YAML string."""
        import json, io

        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
            "highlights": [],
        }
        body = json.dumps(script_data).encode()
        handler = self._make_handler("POST", "/api/preview-yaml", body)
        handler.wfile = io.BytesIO()
        responses = []
        handler._json_response = lambda d, **kw: responses.append(d)
        handler.do_POST()
        assert "yaml" in responses[0]
        assert "source:" in responses[0]["yaml"]

    def test_do_post_api_preview_yaml_exception(self):
        """POST /api/preview-yaml with bad JSON returns error."""
        import io

        handler = self._make_handler("POST", "/api/preview-yaml", b"{{bad}}")
        handler.wfile = io.BytesIO()
        responses = []
        handler._json_response = lambda d, **kw: responses.append(d)
        handler.do_POST()
        assert "error" in responses[0]

    def test_do_post_api_preview_success(self):
        """POST /api/preview calls _generate_preview_html and writes the result."""
        import json, io
        from unittest.mock import patch

        script_data = {
            "settings": {
                "speed": 1.0,
                "window_chrome": "colorful",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
            "highlights": [],
        }
        body = json.dumps(script_data).encode()
        handler = self._make_handler("POST", "/api/preview", body)
        handler.wfile = io.BytesIO()

        with patch(
            "great_docs._term_player.editor._generate_preview_html",
            return_value="<html>preview</html>",
        ):
            handler.do_POST()

        assert handler._sent_responses[0] == 200

    def test_do_post_api_preview_exception(self):
        """POST /api/preview failure returns a JSON error."""
        import json, io
        from unittest.mock import patch

        body = json.dumps(
            {
                "settings": {},
                "chapters": [],
                "annotations": [],
                "cuts": [],
                "snippets": [],
                "highlights": [],
            }
        ).encode()
        handler = self._make_handler("POST", "/api/preview", body)
        handler.wfile = io.BytesIO()
        responses = []
        handler._json_response = lambda d, **kw: responses.append(d)

        with patch(
            "great_docs._term_player.editor._generate_preview_html",
            side_effect=RuntimeError("preview failed"),
        ):
            handler.do_POST()

        assert "error" in responses[0]

    def test_do_post_unknown_path_sends_404(self):
        """POST /other sends a 404 error."""
        import io

        handler = self._make_handler("POST", "/unknown-endpoint", b"")
        handler.wfile = io.BytesIO()
        handler.do_POST()
        assert any("error-404" in str(r) for r in handler._sent_responses)

    def test_json_response_writes_json(self):
        """_json_response serializes data and calls send_response(200)."""
        import io

        handler = self._make_handler("GET", "/")
        handler.wfile = io.BytesIO()
        handler._json_response({"key": "value"})
        assert 200 in handler._sent_responses

    def test_serve_editor_page_writes_html(self):
        """_serve_editor_page writes 200 response with HTML body."""
        import io

        handler = self._make_handler("GET", "/")
        handler.wfile = io.BytesIO()
        handler._serve_editor_page()
        assert 200 in handler._sent_responses

    def test_log_message_suppressed(self):
        """log_message does nothing (no output)."""
        import io

        handler = self._make_handler("GET", "/")
        handler.wfile = io.BytesIO()
        # Should not raise
        handler.log_message("test %s", "arg")


# ---------------------------------------------------------------------------
# serve_editor
# ---------------------------------------------------------------------------


class TestServeEditor:
    def _make_termshow(self, tmp_path) -> "Path":
        from pathlib import Path
        from great_docs._term_player.parser import Recording, TermInfo, Event
        import json

        p = tmp_path / "demo.termshow"
        header = json.dumps(
            {"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 24}, "title": "Demo"}
        )
        event = json.dumps([0.5, "o", "hello"])
        p.write_text(header + "\n" + event + "\n")
        return p

    def test_source_not_found_raises(self, tmp_path):
        """Missing source file raises FileNotFoundError."""
        from great_docs._term_player.editor import serve_editor
        import pytest

        with pytest.raises(FileNotFoundError):
            serve_editor(tmp_path / "nonexistent.termshow")

    def test_serve_no_browser_no_script(self, tmp_path):
        """serve_editor with no_browser=True starts the server then gets interrupted."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import serve_editor

        src = self._make_termshow(tmp_path)
        mock_server = MagicMock()
        mock_server.serve_forever.side_effect = KeyboardInterrupt

        with patch("great_docs._term_player.editor.HTTPServer", return_value=mock_server):
            serve_editor(src, no_browser=True)

        mock_server.shutdown.assert_called_once()

    def test_serve_with_existing_script(self, tmp_path):
        """serve_editor loads an existing .yml script if present."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import serve_editor

        src = self._make_termshow(tmp_path)
        script_path = tmp_path / "demo.termshow.yml"
        script_path.write_text("source: demo.termshow\n")

        mock_server = MagicMock()
        mock_server.serve_forever.side_effect = KeyboardInterrupt

        with patch("great_docs._term_player.editor.HTTPServer", return_value=mock_server):
            serve_editor(src, no_browser=True)

        mock_server.shutdown.assert_called_once()

    def test_serve_opens_browser(self, tmp_path):
        """serve_editor with no_browser=False schedules a browser open."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import serve_editor

        src = self._make_termshow(tmp_path)
        mock_server = MagicMock()
        mock_server.serve_forever.side_effect = KeyboardInterrupt
        mock_timer = MagicMock()

        with patch("great_docs._term_player.editor.HTTPServer", return_value=mock_server):
            with patch(
                "great_docs._term_player.editor.threading.Timer", return_value=mock_timer
            ) as mock_timer_cls:
                serve_editor(src, no_browser=False)

        mock_timer_cls.assert_called_once()
        mock_timer.start.assert_called_once()


# ---------------------------------------------------------------------------
# _generate_preview_html
# ---------------------------------------------------------------------------


class TestGeneratePreviewHtml:
    def _make_editor_data(self) -> dict:
        return {
            "recording": {
                "title": "Demo",
                "duration": 5.0,
                "term": {"cols": 80, "rows": 24},
                "events": [{"time": 0.5, "code": "o", "data": "hello"}],
            },
            "script": {
                "settings": {},
                "chapters": [],
                "annotations": [],
                "cuts": [],
                "snippets": [],
                "highlights": [],
            },
        }

    def _make_script_data(self) -> dict:
        return {
            "settings": {
                "speed": 1.0,
                "window_chrome": "none",
                "font_family": None,
                "prompt": None,
                "prompt_pattern": None,
            },
            "chapters": [],
            "annotations": [],
            "cuts": [],
            "snippets": [],
            "highlights": [],
        }

    def test_success_path(self, tmp_path):
        """Happy path: Quarto renders and returns the HTML content."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import _generate_preview_html

        editor_data = self._make_editor_data()
        script_data = self._make_script_data()

        expected_html = "<html><body>preview</body></html>"

        def fake_generate_manifest(recording, script, output_dir):
            # Write a fake manifest so the function continues
            pass

        def fake_run(cmd, **kw):
            # Create the expected output file in the temp dir
            cwd = kw.get("cwd", str(tmp_path))
            from pathlib import Path

            output_dir = Path(cwd)
            site_dir = output_dir / "_site"
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "preview.html").write_text(expected_html)
            r = MagicMock()
            r.returncode = 0
            return r

        with (
            patch("great_docs._term_player.editor.generate_manifest", fake_generate_manifest),
            patch("subprocess.run", fake_run),
        ):
            result = _generate_preview_html(editor_data, script_data)

        assert result == expected_html

    def test_quarto_failure_raises(self):
        """If Quarto returns non-zero, RuntimeError is raised."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import _generate_preview_html
        import pytest

        editor_data = self._make_editor_data()
        script_data = self._make_script_data()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "quarto error"

        with (
            patch("great_docs._term_player.editor.generate_manifest"),
            patch("subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(RuntimeError, match="Quarto render failed"):
                _generate_preview_html(editor_data, script_data)

    def test_missing_html_output_raises(self):
        """If rendered HTML not found, RuntimeError is raised."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import _generate_preview_html
        import pytest

        editor_data = self._make_editor_data()
        script_data = self._make_script_data()

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("great_docs._term_player.editor.generate_manifest"),
            patch("subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(RuntimeError, match="Rendered HTML not found"):
                _generate_preview_html(editor_data, script_data)

    def test_with_complex_script_data(self, tmp_path):
        """Script with chapters, cuts, highlights and annotations is reconstructed properly."""
        from unittest.mock import patch, MagicMock
        from great_docs._term_player.editor import _generate_preview_html

        editor_data = self._make_editor_data()
        script_data = {
            "settings": {
                "speed": 1.5,
                "window_chrome": "colorful",
                "font_family": "Mono",
                "prompt": "❯",
                "prompt_pattern": r"^\$ ",
            },
            "chapters": [{"time": 1.0, "label": "Start"}],
            "annotations": [
                {
                    "time": 2.0,
                    "duration": 1.0,
                    "text": "Note",
                    "position": "top",
                    "width": "medium",
                    "style": "callout",
                }
            ],
            "cuts": [{"start": 3.0, "end": 4.0, "type": "remove"}],
            "snippets": [{"time": 1.0, "duration": 2.0, "text": "cmd", "match": "", "label": ""}],
            "highlights": [
                {
                    "time": 1.0,
                    "duration": 1.0,
                    "style": "box",
                    "color": "#ff0000",
                    "target": {
                        "region": {"row": 0, "col": 0, "width": 10, "height": 1},
                        "match": None,
                        "group": 0,
                        "lines": None,
                        "track_scroll": False,
                    },
                    "badge_text": "!",
                    "badge_icon": "",
                    "fade_in": 0.3,
                    "fade_out": 0.3,
                    "pulse": True,
                }
            ],
        }
        expected_html = "<html>ok</html>"

        def fake_run(cmd, **kw):
            from pathlib import Path

            cwd = Path(kw["cwd"])
            site_dir = cwd / "_site"
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "preview.html").write_text(expected_html)
            r = MagicMock()
            r.returncode = 0
            return r

        with (
            patch("great_docs._term_player.editor.generate_manifest"),
            patch("subprocess.run", fake_run),
        ):
            result = _generate_preview_html(editor_data, script_data)

        assert result == expected_html


# ---------------------------------------------------------------------------
# _get_editor_html
# ---------------------------------------------------------------------------


class TestGetEditorHtml:
    def test_returns_string(self):
        """_get_editor_html returns the HTML string."""
        from great_docs._term_player.editor import _get_editor_html

        result = _get_editor_html()
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Round-trip of real scripts: load → editor data → save → load
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA = _ROOT / "great_docs" / "_term_player" / "schemas" / "termshow-script.schema.json"


def _real_scripts() -> dict[str, str]:
    """Every script in the docs, plus those embedded in the synthetic specs."""
    found: dict[str, str] = {}
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "docs"], cwd=_ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover
        tracked = []
    for rel in tracked:
        if rel.endswith(".termshow.yml"):
            found[rel] = (_ROOT / rel).read_text(encoding="utf-8")
    for spec_path in sorted((_ROOT / "test-packages" / "synthetic" / "specs").glob("*.py")):
        if "termshow" not in spec_path.read_text(encoding="utf-8"):
            continue
        spec = importlib.util.spec_from_file_location(f"_spec_{spec_path.stem}", spec_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for value in vars(module).values():
            if isinstance(value, dict) and isinstance(value.get("files"), dict):
                for name, content in value["files"].items():
                    if name.endswith(".termshow.yml"):
                        found[f"{spec_path.stem}:{name}"] = content
    return found


def _save_and_reload(script: Script) -> tuple[str, Script]:
    data = _build_editor_data(_make_recording(), script)
    # The browser sends the script back as JSON
    script_data = json.loads(json.dumps(data["script"]))
    yaml_str = _serialize_script(script_data, script.source)
    return yaml_str, _parse_script_data(parse_yaml(yaml_str))


def _schema_errors(yaml_str: str) -> list[str]:
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(json.loads(_SCHEMA.read_text()))
    return [e.message for e in validator.iter_errors(parse_yaml(yaml_str))]


def test_real_scripts_found():
    assert len(_real_scripts()) >= 3


@pytest.mark.parametrize("key", sorted(_real_scripts()))
def test_real_script_survives_editor_save(key: str):
    script = _parse_script_data(parse_yaml(_real_scripts()[key]))
    yaml_str, reloaded = _save_and_reload(script)
    assert reloaded == script
    assert _schema_errors(yaml_str) == []


def test_every_field_survives_editor_save():
    script = _make_script(
        speed=1.25,
        window_chrome="minimal",
        line_height=1.3,
        show_cursor=False,
        prompt="❯",
        prompt_pattern=r"^\$ ",
        chapters=[Chapter(time=0.125, label="Intro")],
        annotations=[Annotation(time=1.0, duration=2.0, text="Hi", width="large")],
        cuts=[Cut(start=2.0, end=3.5, type="ellipsis")],
        speed_map=[SpeedSegment(start=4.0, end=6.0, speed=3.0)],
        snippets=[Snippet(time=0.5, duration=4.0, text="echo hi", match=r"\$ (.+)", label="Run")],
        highlights=[
            Highlight(
                time=1.0,
                duration=2.0,
                target=HighlightTarget(region={"row": 1, "col": 2, "width": 3, "height": 2}),
                style="badge-after",
                color="#ff79c6",
                badge_text="1",
                badge_icon="★",
                fade_in=0.0,
                fade_out=0.75,
                pulse=True,
            ),
            Highlight(
                time=2.0,
                duration=1.0,
                target=HighlightTarget(match=r"(done) in \d+s", group=1, track_scroll=True),
            ),
            Highlight(time=3.0, duration=1.0, target=HighlightTarget(lines=[0, 1])),
        ],
    )
    yaml_str, reloaded = _save_and_reload(script)
    assert reloaded == script
    assert _schema_errors(yaml_str) == []


@pytest.mark.parametrize(
    "text",
    [
        'say "hi"',
        "it's",
        "two\nlines",
        r"back\slash \n not a newline",
        "tab\there",
        "# not a comment",
        "key: value",
        "{braces} [brackets] & *star",
        "trailing space ",
        "\x1b[1mbold\x1b[0m",
    ],
)
def test_awkward_strings_survive_editor_save(text: str):
    script = _make_script(
        prompt=text,
        prompt_pattern=text,
        font_family=text,
        chapters=[Chapter(time=0.0, label=text)],
        annotations=[Annotation(time=0.0, duration=1.0, text=text)],
        snippets=[Snippet(time=0.0, duration=1.0, text=text, match=text, label=text)],
        highlights=[
            Highlight(
                time=0.0,
                duration=1.0,
                target=HighlightTarget(match=text),
                badge_text=text,
                badge_icon=text,
            )
        ],
    )
    _, reloaded = _save_and_reload(script)
    assert reloaded == script
