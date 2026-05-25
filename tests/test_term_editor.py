"""Tests for the _term_player.editor module (data pass and YAML serializer)."""

from __future__ import annotations

import yaml
import pytest

from great_docs._term_player.editor import _build_editor_data, _serialize_script
from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import (
    Annotation,
    Chapter,
    Cut,
    Script,
    Snippet,
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
        "idle_time_limit": None,
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
        assert s["idle_time_limit"] is None
        assert s["speed"] == 1.0
        assert s["window_chrome"] == "colorful"
        assert s["font_family"] is None
        assert s["prompt"] is None
        assert s["prompt_pattern"] is None

    def test_settings_with_all_fields(self):
        script = _make_script(
            idle_time_limit=2.0,
            speed=1.5,
            window_chrome="simple",
            font_family="JetBrains Mono, monospace",
            prompt="❯",
            prompt_pattern=r"^\$ ",
        )
        data = _build_editor_data(_make_recording(), script)
        s = data["script"]["settings"]
        assert s["idle_time_limit"] == 2.0
        assert s["speed"] == 1.5
        assert s["window_chrome"] == "simple"
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
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["source"] == "demo.termshow"
        assert parsed["settings"]["window_chrome"] == "colorful"
        assert "prompt" not in parsed["settings"]
        assert "prompt_pattern" not in parsed["settings"]
        assert "font_family" not in parsed["settings"]

    def test_prompt_serialized(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["settings"]["prompt"] == "❯"
        assert "prompt_pattern" not in parsed["settings"]

    def test_prompt_and_pattern_serialized(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["settings"]["prompt"] == "→"
        assert parsed["settings"]["prompt_pattern"] == r"^\$ "

    def test_font_family_single(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["settings"]["font_family"] == "JetBrains Mono"

    def test_font_family_comma_list(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["settings"]["font_family"] == "JetBrains Mono, Fira Code, monospace"

    def test_speed_non_default_serialized(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["settings"]["speed"] == 2.0

    def test_speed_default_omitted(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert "speed" not in parsed["settings"]

    def test_idle_time_limit_serialized(self):
        script_data = {
            "settings": {
                "idle_time_limit": 2.5,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["settings"]["idle_time_limit"] == 2.5

    def test_chapters_serialized_sorted(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["chapters"][0]["label"] == "First"
        assert parsed["chapters"][1]["label"] == "Second"

    def test_snippets_with_match(self):
        script_data = {
            "settings": {
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["snippets"][0]["match"] == r"\$ (.+)"
        assert parsed["snippets"][0]["label"] == "cmd"

    def test_all_settings_combined(self):
        """Full settings with every field populated."""
        script_data = {
            "settings": {
                "idle_time_limit": 1.5,
                "speed": 3.0,
                "window_chrome": "simple",
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
        parsed = yaml.safe_load(yaml_str)
        s = parsed["settings"]
        assert s["idle_time_limit"] == 1.5
        assert s["speed"] == 3.0
        assert s["window_chrome"] == "simple"
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
                "idle_time_limit": None,
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
        parsed = yaml.safe_load(yaml_str)
        assert parsed["source"] == "x.termshow"
        # No chapters/annotations/cuts/snippets keys when empty
        assert parsed.get("chapters") is None
        assert parsed.get("annotations") is None
        assert parsed.get("cuts") is None
        assert parsed.get("snippets") is None


# ---------------------------------------------------------------------------
# Round-trip: _build_editor_data → _serialize_script → yaml.safe_load
# ---------------------------------------------------------------------------


class TestEditorRoundTrip:
    """Test that data passes through build → serialize → parse intact."""

    def test_settings_round_trip(self):
        script = _make_script(
            idle_time_limit=2.0,
            speed=1.5,
            window_chrome="simple",
            font_family="Cascadia Code",
            prompt="❯",
            prompt_pattern=r"^\$ ",
        )
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = yaml.safe_load(yaml_str)
        s = parsed["settings"]
        assert s["idle_time_limit"] == 2.0
        assert s["speed"] == 1.5
        assert s["window_chrome"] == "simple"
        assert s["font_family"] == "Cascadia Code"
        assert s["prompt"] == "❯"
        assert s["prompt_pattern"] == r"^\$ "

    def test_prompt_round_trip_none(self):
        script = _make_script(prompt=None, prompt_pattern=None)
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = yaml.safe_load(yaml_str)
        assert "prompt" not in parsed["settings"]
        assert "prompt_pattern" not in parsed["settings"]

    def test_font_family_round_trip_list(self):
        script = _make_script(font_family="JetBrains Mono, Fira Code, monospace")
        data = _build_editor_data(_make_recording(), script)
        yaml_str = _serialize_script(data["script"], "demo.termshow")
        parsed = yaml.safe_load(yaml_str)
        assert parsed["settings"]["font_family"] == "JetBrains Mono, Fira Code, monospace"

    def test_full_round_trip(self):
        script = _make_script(
            idle_time_limit=1.0,
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
        parsed = yaml.safe_load(yaml_str)

        assert parsed["settings"]["prompt"] == ">"
        assert parsed["settings"]["font_family"] == "Menlo"
        assert len(parsed["chapters"]) == 2
        assert parsed["chapters"][0]["label"] == "Start"
        assert len(parsed["annotations"]) == 1
        assert parsed["annotations"][0]["text"] == "Note"
        assert len(parsed["cuts"]) == 1
        assert len(parsed["snippets"]) == 1
        assert parsed["snippets"][0]["text"] == "echo hi"
