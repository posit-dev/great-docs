"""Tests for `great-docs termshow validate`."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player.themes import theme_names
from great_docs._term_player.validate import (
    ERROR,
    THEME_NAMES,
    WARNING,
    Problem,
    _python_only,
    check_recording_text,
    check_script_data,
    check_timeline,
    validate,
)
from great_docs.cli import cli

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "great_docs" / "_term_player" / "schemas"
SPECS_DIR = ROOT / "test-packages" / "synthetic" / "specs"

# Output at 0s, 1s, and 3s (delays are relative to the previous event)
EVENTS = [[0.0, "o", "$ "], [1.0, "o", "echo hello\r\nhello\r\n"], [2.0, "o", "$ "]]


def _recording_text(events=EVENTS, cols: int = 40, rows: int = 6, **header) -> str:
    head = {"version": 1, "format": "termshow", "term": {"cols": cols, "rows": rows}, **header}
    return "\n".join([json.dumps(head)] + [json.dumps(e) for e in events])


def _recording_problems(text: str) -> list[Problem]:
    problems: list[Problem] = []
    check_recording_text(text, "demo.termshow", problems)
    return problems


def _script_problems(data, events=EVENTS) -> list[Problem]:
    """Structural and timeline problems for a script on a short recording."""
    problems: list[Problem] = []
    recording = check_recording_text(_recording_text(events), "demo.termshow")
    clean = check_script_data(data, "demo.termshow.yml", problems)
    check_timeline(recording, clean or {}, "demo.termshow.yml", problems)
    return problems


def _errors(problems: list[Problem]) -> list[str]:
    return [f"{p.where}: {p.message}" for p in problems if p.severity == ERROR]


def _warnings(problems: list[Problem]) -> list[str]:
    return [f"{p.where}: {p.message}" for p in problems if p.severity == WARNING]


# ---------------------------------------------------------------------------
# The recording
# ---------------------------------------------------------------------------


class TestRecording:
    def test_valid(self):
        assert _recording_problems(_recording_text()) == []

    def test_comments_and_blank_lines_allowed(self):
        text = "# a comment\n\n" + _recording_text()
        assert _recording_problems(text) == []

    def test_empty(self):
        assert "empty" in _errors(_recording_problems("\n\n"))[0]

    def test_header_not_json(self):
        assert _errors(_recording_problems("{nope\n")) == [
            "line 1: the header isn't valid JSON (Expecting property name enclosed in double quotes)"
        ]

    def test_header_fields(self):
        header = {"version": 2, "format": "asciicast", "term": {"cols": 0, "rows": "24"}}
        errors = _errors(_recording_problems(json.dumps(header)))
        assert errors == [
            "header.version: must be 1, got 2",
            "header.format: must be \"termshow\", got 'asciicast'",
            "header.term.cols: must be at least 1 (got 0)",
            "header.term.rows: must be a whole number, got '24'",
        ]

    def test_header_missing_term(self):
        errors = _errors(_recording_problems('{"version": 1, "format": "termshow"}'))
        assert errors == ["header: missing 'term'"]

    def test_header_theme_colors(self):
        text = _recording_text(cols=10).replace(
            '"rows": 6}', '"rows": 6, "theme": {"fg": "white", "palette": ["#000000"]}}'
        )
        errors = _errors(_recording_problems(text))
        assert "header.term.theme.fg: must be a hex color like '#1e1e2e', got 'white'" in errors
        assert "header.term.theme.palette: can have at most 16 entries, got 1" not in errors
        assert any(e.startswith("header.term.theme.palette:") for e in errors)

    def test_palette_string_form(self):
        palette = ":".join(["#000000"] * 16)
        text = _recording_text().replace(
            '"rows": 6}', f'"rows": 6, "theme": {{"palette": "{palette}"}}}}'
        )
        assert _recording_problems(text) == []
        bad = text.replace(palette, "#000000:#ffffff")
        assert _errors(_recording_problems(bad))

    def test_event_lines(self):
        events = [
            [0.0, "o", "$ "],
            [-1, "o", "x"],
            ["1", "o", "x"],
            [0.1, "", "x"],
            [0.1, "o", 5],
            [0.1, "r", "wide"],
            [0.1, "x", "zero"],
            [0.1, "o"],
        ]
        text = _recording_text(events) + "\n[0.1, broken"
        errors = _errors(_recording_problems(text))
        assert errors == [
            "line 3: the delay can't be negative (got -1)",
            "line 4: the delay must be a number, got '1'",
            "line 5: the event code must be a non-empty string, got ''",
            "line 6: the event data must be a string, got 5",
            "line 7: a resize event's data must look like '80x24', got 'wide'",
            "line 8: an exit event's data must be a whole number, got 'zero'",
            'line 9: an event must be [delay, code, data], got [0.1, "o"]',
            "line 10: not valid JSON (Expecting value)",
        ]

    def test_valid_resize_and_exit(self):
        events = [[0.0, "o", "$ "], [0.1, "r", "100x30"], [0.1, "x", "-1"], [0.1, "m", "Intro"]]
        assert _recording_problems(_recording_text(events)) == []

    def test_event_errors_capped(self):
        events = [[0.0, "o", "$ "]] + [[-1, "o", "x"]] * 30
        errors = _errors(_recording_problems(_recording_text(events)))
        assert len(errors) == 11
        assert errors[-1] == ": stopped after 10 bad event lines (20 unchecked)"

    def test_no_output_warns(self):
        problems = _recording_problems(_recording_text([[0.0, "m", "Start"]]))
        assert _warnings(problems) == [": the recording has no output"]

    def test_returns_recording_only_when_valid(self):
        assert check_recording_text(_recording_text(), "x").duration == pytest.approx(3.0)
        assert check_recording_text('{"version": 1}', "x") is None


# ---------------------------------------------------------------------------
# The script: structure
# ---------------------------------------------------------------------------


class TestScriptStructure:
    def test_valid(self):
        data = {
            "source": "demo.termshow",
            "settings": {"theme": "nord", "window_chrome": "colorful", "speed": 1.5},
            "chapters": [{"at": 0, "label": "Start"}, {"at": 1, "label": "Echo"}],
            "cuts": [{"from": 1.2, "to": 1.4, "type": "ellipsis"}],
            "annotations": [{"at": 0.5, "duration": 1, "text": "Hi", "position": "top"}],
            "highlights": [{"at": 1, "target": {"match": "hello"}, "style": "glow"}],
            "snippets": [{"at": 1, "duration": 1, "match": r"echo (\w+)"}],
        }
        assert _script_problems(data) == []

    def test_not_a_mapping(self):
        assert _errors(_script_problems(["a"])) == [
            ": a script must be a mapping of keys to values, got a list"
        ]

    def test_unknown_keys_suggest(self):
        errors = _errors(_script_problems({"chapter": [], "settings": {"sped": 2}}))
        assert errors == [
            ": unknown key 'chapter' (did you mean 'chapters'?)",
            "settings: unknown key 'sped' (did you mean 'speed'?)",
        ]

    def test_unknown_item_key(self):
        errors = _errors(_script_problems({"annotations": [{"at": 1, "txt": "x"}]}))
        assert errors == ["annotations[0]: unknown key 'txt' (did you mean 'text'?)"]

    def test_section_must_be_list(self):
        assert _errors(_script_problems({"cuts": {"from": 1, "to": 2}})) == [
            "cuts: must be a list, got a mapping"
        ]
        assert _errors(_script_problems({"chapters": None})) == [
            "chapters: must be a list, got null"
        ]

    def test_missing_required(self):
        errors = _errors(_script_problems({"cuts": [{"from": 1}], "chapters": [{"label": "x"}]}))
        assert errors == ["chapters[0]: missing 'at'", "cuts[0]: missing 'to'"]

    def test_types(self):
        data = {
            "settings": {"show_cursor": "yes", "line_height": 0, "prompt": 5},
            "chapters": [{"at": "1s"}],
            "annotations": [{"at": True}],
        }
        assert _errors(_script_problems(data)) == [
            "settings.show_cursor: must be true or false, got 'yes'",
            "settings.line_height: must be greater than 0 (got 0)",
            "settings.prompt: must be a string or null, got 5",
            "chapters[0].at: must be a number, got '1s'",
            "annotations[0].at: must be a number, got true",
        ]

    def test_negative_time(self):
        errors = _errors(_script_problems({"annotations": [{"at": -1, "duration": -2}]}))
        assert errors == [
            "annotations[0].at: can't be negative (got -1)",
            "annotations[0].duration: can't be negative (got -2)",
        ]

    def test_enums_suggest(self):
        data = {
            "settings": {"window_chrome": "colourful"},
            "cuts": [{"from": 1, "to": 2, "type": "skip"}],
            "annotations": [{"at": 0, "position": "top-centre", "style": "loud", "width": "huge"}],
            "highlights": [{"at": 0, "target": {"lines": [0]}, "style": "underline_wavy"}],
        }
        errors = _errors(_script_problems(data))
        assert (
            "settings.window_chrome: must be one of none, minimal, colorful; got 'colourful' (did you mean 'colorful'?)"
            in errors
        )
        assert any(
            e.startswith("cuts[0].type: must be one of jump, ellipsis; got 'skip'") for e in errors
        )
        assert any(e.startswith("annotations[0].position:") and "'top-centre'" in e for e in errors)
        assert any(e.startswith("annotations[0].style:") for e in errors)
        assert any(e.startswith("annotations[0].width:") for e in errors)
        assert any("(did you mean 'underline-wavy'?)" in e for e in errors)

    def test_speed(self):
        errors = _errors(
            _script_problems(
                {"settings": {"speed": 0}, "speed_map": [{"from": 0, "to": 1, "speed": -2}]}
            )
        )
        assert errors == [
            "settings.speed: must be greater than 0 (got 0)",
            "speed_map[0].speed: must be greater than 0 (got -2)",
        ]

    def test_from_after_to(self):
        data = {"cuts": [{"from": 2, "to": 1}], "speed_map": [{"from": 2, "to": 1, "speed": 2}]}
        assert _errors(_script_problems(data)) == [
            "cuts[0]: ends (1s) before it starts (2s)",
            "speed_map[0]: ends (1s) before it starts (2s)",
        ]

    def test_empty_span_warns(self):
        assert _warnings(_script_problems({"cuts": [{"from": 1, "to": 1}]})) == [
            "cuts[0]: is empty (from and to are the same)"
        ]


class TestThemes:
    def test_names_and_pairs(self):
        for theme in ["dracula", "auto", {"light": "github-light", "dark": "nord"}]:
            assert _script_problems({"settings": {"theme": theme}}) == [], theme

    def test_inline(self):
        theme = {"base": "nord", "bg": "#000", "palette": ["#111111"] * 8}
        assert _script_problems({"settings": {"theme": theme}}) == []

    def test_unknown_name(self):
        errors = _errors(_script_problems({"settings": {"theme": "draculla"}}))
        assert len(errors) == 1
        assert errors[0].startswith("settings.theme: must be one of auto, catppuccin-latte")
        assert errors[0].endswith("(did you mean 'dracula'?)")

    def test_loose_name_warns(self):
        problems = _script_problems({"settings": {"theme": "Tokyo Night"}})
        assert _errors(problems) == []
        assert _warnings(problems) == [
            "settings.theme: write 'tokyo-night'; the schema only allows the exact name"
        ]

    def test_inline_mistakes(self):
        theme = {"base": "auto", "fg": "red", "palette": ["#111111"] * 5, "accent": "#fff"}
        errors = _errors(_script_problems({"settings": {"theme": theme}}))
        assert any(
            e.startswith("settings.theme.base: must be one of catppuccin-latte") for e in errors
        )
        assert "settings.theme.fg: must be a hex color like '#1e1e2e', got 'red'" in errors
        assert "settings.theme.palette: must have 8 or 16 entries, got 5" in errors
        assert "settings.theme: unknown key 'accent'" in errors

    def test_pair_mistakes(self):
        errors = _errors(_script_problems({"settings": {"theme": {"light": "nord", "other": 1}}}))
        assert errors == [
            "settings.theme: a light/dark pair has only 'light' and 'dark', not 'other'",
            "settings.theme: a light/dark pair needs 'dark' too",
        ]
        errors = _errors(
            _script_problems({"settings": {"theme": {"light": "nord", "dark": "auto"}}})
        )
        assert len(errors) == 1 and errors[0].startswith("settings.theme.dark: must be one of")


class TestHighlightsAndSnippets:
    def test_target_or_region(self):
        region = {"row": 0, "col": 0, "width": 1, "height": 1}
        data = {
            "highlights": [
                {"at": 0},
                {"at": 0, "target": {"region": region}, "region": region},
                {"at": 0, "region": region},
                {"at": 0, "target": {}},
            ]
        }
        assert _errors(_script_problems(data)) == [
            "highlights[0]: needs 'target' or 'region'",
            "highlights[1]: can't have both 'target' and 'region'",
            "highlights[3].target: needs 'region', 'lines' or 'match'",
        ]

    def test_region_fields(self):
        data = {"highlights": [{"at": 0, "target": {"region": {"row": 0, "col": -1, "width": 0}}}]}
        assert _errors(_script_problems(data)) == [
            "highlights[0].target.region: missing 'height'",
            "highlights[0].target.region.col: can't be negative (got -1)",
            "highlights[0].target.region.width: must be at least 1 (got 0)",
        ]

    def test_lines(self):
        data = {
            "highlights": [
                {"at": 0, "target": {"lines": []}},
                {"at": 0, "target": {"lines": [1.5]}},
            ]
        }
        assert _errors(_script_problems(data)) == [
            "highlights[0].target.lines: can't be empty",
            "highlights[1].target.lines[0]: must be a whole number, got 1.5",
        ]

    def test_bad_regex(self):
        data = {
            "settings": {"prompt_pattern": "[$"},
            "highlights": [{"at": 0, "target": {"match": "(open"}}],
            "snippets": [{"at": 0, "match": "*x"}],
        }
        errors = _errors(_script_problems(data))
        assert len(errors) == 3
        assert all("isn't a valid regular expression" in e for e in errors)

    def test_group_out_of_range(self):
        data = {"highlights": [{"at": 1, "target": {"match": "(hel)lo", "group": 2}}]}
        assert _errors(_script_problems(data)) == [
            "highlights[0].target.group: the pattern has 1 group, so there's no group 2"
        ]

    def test_python_only_regex_warns(self):
        data = {"highlights": [{"at": 1, "target": {"match": "(?P<w>hello)"}}]}
        problems = _script_problems(data)
        assert _errors(problems) == []
        assert _warnings(problems) == [
            "highlights[0].target.match: the player matches with JavaScript regular "
            "expressions: named groups are written (?<name>...) in JavaScript"
        ]

    @pytest.mark.parametrize(
        "pattern, flagged",
        [
            ("(?P<x>a)", True),
            ("(?i)abc", True),
            (r"\Aabc\Z", True),
            ("(?>ab)", True),
            ("a++", True),
            ("(?#note)a", True),
            (r"\\A", False),
            (r"\$ (.+)", False),
            ("(?<x>a)", False),
            (r"a\++", False),
            ("(a+)+", False),
        ],
    )
    def test_python_only_patterns(self, pattern: str, flagged: bool):
        assert (_python_only(pattern) is not None) is flagged

    def test_snippet_needs_text_or_match(self):
        assert _errors(_script_problems({"snippets": [{"at": 0, "label": "x"}]})) == [
            "snippets[0]: needs 'text' or 'match'"
        ]


# ---------------------------------------------------------------------------
# The script: timing and screen content
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_after_end(self):
        data = {
            "chapters": [{"at": 0, "label": "a"}, {"at": 9, "label": "b"}],
            "annotations": [{"at": 4, "text": "late"}],
            "highlights": [{"at": 3, "target": {"lines": [0]}}],
            "snippets": [{"at": 3.5, "text": "x"}],
            "cuts": [{"from": 5, "to": 6}],
        }
        assert _warnings(_script_problems(data)) == [
            "cuts[0]: starts at 5s, after the end of the recording (3s)",
            "chapters[1]: at 9s, after the end of the recording (3s)",
            "annotations[0]: starts at 4s, after the end of the recording (3s)",
            "highlights[0]: starts at 3s, after the end of the recording (3s)",
            "snippets[0]: starts at 3.5s, after the end of the recording (3s)",
        ]

    def test_playback_items_use_played_length(self):
        # Cutting 1.5s-2.5s leaves 2s of playback, so 2.5s is past the end
        data = {"cuts": [{"from": 1.5, "to": 2.5}], "annotations": [{"at": 2.5, "text": "x"}]}
        assert _warnings(_script_problems(data)) == [
            "annotations[0]: starts at 2.5s, after the end of the recording (2s)"
        ]
        # At double speed, the 3s recording plays in 1.5s
        data = {"settings": {"speed": 2}, "chapters": [{"at": 2, "label": "x"}]}
        assert _warnings(_script_problems(data)) == [
            "chapters[0]: at 2s, after the end of the recording (1.5s)"
        ]

    def test_cuts_use_recording_length(self):
        data = {"settings": {"speed": 4}, "cuts": [{"from": 2, "to": 2.5}]}
        assert _script_problems(data) == []

    def test_whole_recording_cut(self):
        warnings = _warnings(_script_problems({"cuts": [{"from": 0, "to": 3}]}))
        assert "cuts[0]: cuts the whole recording" in warnings

    def test_overlapping_cuts_and_speed_segments(self):
        data = {
            "cuts": [{"from": 1.5, "to": 2.5}, {"from": 0.2, "to": 0.4}, {"from": 2.0, "to": 2.8}],
            "speed_map": [{"from": 0, "to": 2, "speed": 2}, {"from": 1, "to": 3, "speed": 3}],
        }
        assert _warnings(_script_problems(data)) == [
            "cuts[2]: overlaps cuts[0] (1.5s–2.5s); each moment can only be in one cut",
            "speed_map[1]: overlaps speed_map[0] (0s–2s); each moment can only be in one speed segment",
        ]

    def test_touching_spans_dont_overlap(self):
        data = {"cuts": [{"from": 0.5, "to": 1}, {"from": 1, "to": 1.5}]}
        assert _script_problems(data) == []

    def test_chapters(self):
        data = {
            "chapters": [
                {"at": 1, "label": "Echo"},
                {"at": 0, "label": "Start"},
                {"at": 0, "label": "Echo"},
                {"at": 2},
            ]
        }
        assert _warnings(_script_problems(data)) == [
            "chapters[1]: at 0s, before chapters[0] (1s); list chapters in time order",
            "chapters[2]: at the same time as chapters[1]",
            "chapters[2]: has the same label as chapters[0] ('Echo')",
            "chapters[3]: has no label",
        ]

    def test_annotations_in_same_spot(self):
        data = {
            "annotations": [
                {"at": 0, "duration": 2, "text": "a"},
                {"at": 1, "duration": 1, "text": "b"},
                {"at": 1, "duration": 1, "text": "c", "position": "top"},
                {"at": 2, "duration": 1, "text": "d"},
            ]
        }
        assert _warnings(_script_problems(data)) == [
            "annotations[1]: covers annotations[0] (bottom-right, 1s–2s); move one or change its position"
        ]

    def test_annotation_without_text_or_duration(self):
        data = {"annotations": [{"at": 0, "duration": 0, "text": "x"}, {"at": 1}]}
        assert _warnings(_script_problems(data)) == [
            "annotations[0]: has a duration of 0, so it never shows",
            "annotations[1]: has no text",
        ]

    def test_overlapping_snippets(self):
        data = {"snippets": [{"at": 0, "duration": 2, "text": "a"}, {"at": 1.5, "text": "b"}]}
        assert _warnings(_script_problems(data)) == [
            "snippets[1]: overlaps snippets[0] (1.5s–2s); only one copy button shows at a time, "
            "and the first listed wins"
        ]

    def test_entries_with_errors_skipped(self):
        # The bad annotation is reported once, as an error, and not checked for timing
        problems = _script_problems({"annotations": [{"at": 99, "position": "nowhere"}]})
        assert len(problems) == 1 and problems[0].severity == ERROR

    def test_idle_stretch(self):
        events = [[0.0, "o", "$ "], [12.0, "o", "done\r\n"]]
        warnings = _warnings(_script_problems({}, events=events))
        assert warnings == [
            ": nothing happens for 12.0s from 0s in the recording; a cut (from: 0.5, to: 11.5) "
            "would tighten it"
        ]
        assert _script_problems({"cuts": [{"from": 1, "to": 11}]}, events=events) == []
        assert _script_problems({"settings": {"speed": 2}}, events=events) == []


class TestScreen:
    def test_match_found(self):
        data = {
            "highlights": [{"at": 1, "duration": 1, "target": {"match": "hel+o", "group": 0}}],
            "snippets": [{"at": 1, "duration": 1, "match": r"echo (\w+)"}],
        }
        assert _script_problems(data) == []

    def test_match_not_on_screen(self):
        data = {
            "highlights": [{"at": 0, "duration": 0.5, "target": {"match": "hello"}}],
            "snippets": [{"at": 0, "duration": 0.5, "match": "echo", "text": "echo"}],
        }
        assert _warnings(_script_problems(data)) == [
            "highlights[0].target.match: 'hello' isn't on screen between 0s and 0.5s",
            "snippets[0].match: 'echo' isn't on screen between 0s and 0.5s "
            "(the copy button falls back to 'text')",
        ]

    def test_match_on_screen_at_start_of_window(self):
        # The screen from 1s is still up at 2s, before the next change at 3s
        data = {"highlights": [{"at": 2, "duration": 0.5, "target": {"match": "hello"}}]}
        assert _script_problems(data) == []

    def test_match_follows_cuts(self):
        # "hello" prints at 3s; cutting 0.5s-2.5s brings it forward to 1s of playback
        events = [[0.0, "o", "$ "], [3.0, "o", "hello\r\n"], [2.0, "o", "$ "]]
        data = {"highlights": [{"at": 1.2, "duration": 0.2, "target": {"match": "hello"}}]}
        assert len(_warnings(_script_problems(data, events=events))) == 1
        data["cuts"] = [{"from": 0.5, "to": 2.5}]
        assert _script_problems(data, events=events) == []

    def test_highlight_row_match_uses_cells(self):
        # Row text is built cell by cell, so spaces between spans are kept
        data = {"highlights": [{"at": 1, "target": {"match": r"^\$ echo hello$"}}]}
        assert _script_problems(data) == []

    def test_empty_group_doesnt_count(self):
        data = {"highlights": [{"at": 1, "target": {"match": "(z*)hello", "group": 1}}]}
        assert len(_warnings(_script_problems(data))) == 1

    def test_regions_outside_terminal(self):
        data = {
            "highlights": [
                {"at": 0, "target": {"region": {"row": 5, "col": 38, "width": 2, "height": 1}}},
                {"at": 0, "target": {"region": {"row": 5, "col": 38, "width": 3, "height": 1}}},
                {"at": 0, "target": {"lines": [2, 6]}},
                {"at": 0, "region": {"row": 6, "col": 0, "width": 1, "height": 1}},
            ]
        }
        assert _warnings(_script_problems(data)) == [
            "highlights[1].target: reaches outside the 40x6 terminal",
            "highlights[2].target: line 6 is below the bottom of the 6-row terminal",
            "highlights[3].region: reaches outside the 40x6 terminal",
        ]


# ---------------------------------------------------------------------------
# validate() and the CLI
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, script: str | None = None, text: str | None = None) -> Path:
    source = tmp_path / "demo.termshow"
    source.write_text(text or _recording_text(), encoding="utf-8")
    if script is not None:
        (tmp_path / "demo.termshow.yml").write_text(script, encoding="utf-8")
    return source


class TestValidate:
    def test_finds_companion_script(self, tmp_path: Path):
        source = _write(tmp_path, "settings:\n  speed: 0\n")
        problems = validate(source)
        assert [str(p) for p in problems] == [
            "demo.termshow.yml: settings.speed: must be greater than 0 (got 0)"
        ]
        assert validate(source, use_script=False) == []

    def test_explicit_script(self, tmp_path: Path):
        source = _write(tmp_path)
        other = tmp_path / "other.yml"
        other.write_text("chapters:\n  - at: 99\n    label: x\n", encoding="utf-8")
        problems = validate(source, other)
        assert [str(p) for p in problems] == [
            "other.yml: chapters[0]: at 99s, after the end of the recording (3s)"
        ]

    def test_yaml_error(self, tmp_path: Path):
        source = _write(tmp_path, "chapters: [\n")
        problems = validate(source)
        assert len(problems) == 1
        assert problems[0].file == "demo.termshow.yml"
        assert "YAML" in problems[0].message

    def test_empty_script(self, tmp_path: Path):
        assert validate(_write(tmp_path, "# nothing yet\n")) == []

    def test_bad_recording_skips_timeline(self, tmp_path: Path):
        source = _write(tmp_path, "chapters:\n  - at: 99\n    label: x\n", text='{"version": 1}')
        problems = validate(source)
        assert all(p.file == "demo.termshow" for p in problems)

    def test_asciicast(self, tmp_path: Path):
        cast = tmp_path / "demo.cast"
        cast.write_text(
            '{"version": 2, "width": 20, "height": 5}\n[0.5, "o", "hi"]\n', encoding="utf-8"
        )
        assert validate(cast) == []
        cast.write_text("not json\n", encoding="utf-8")
        assert validate(cast)[0].message.startswith("can't read this asciicast file")


class TestCli:
    def test_clean(self, tmp_path: Path):
        source = _write(tmp_path, "chapters:\n  - at: 0\n    label: Start\n")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(source)])
        assert result.exit_code == 0, result.output
        assert f"✓ {source}: no problems" in result.output

    def test_errors_fail(self, tmp_path: Path):
        source = _write(tmp_path, "annotations:\n  - at: 1\n    position: middle\n")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(source)])
        assert result.exit_code == 1
        assert "error: demo.termshow.yml: annotations[0].position: must be one of" in result.output
        assert "1 error, 0 warnings" in result.output

    def test_warnings_pass_unless_strict(self, tmp_path: Path):
        source = _write(tmp_path, "chapters:\n  - at: 41\n    label: Late\n")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(source)])
        assert result.exit_code == 0, result.output
        assert (
            "warning: demo.termshow.yml: chapters[0]: at 41s, after the end of the recording (3s)"
            in result.output
        )
        assert "0 errors, 1 warning" in result.output
        strict = CliRunner().invoke(cli, ["termshow", "validate", str(source), "--strict"])
        assert strict.exit_code == 1

    def test_no_script(self, tmp_path: Path):
        source = _write(tmp_path, "settings:\n  speed: 0\n")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(source), "--no-script"])
        assert result.exit_code == 0, result.output

    def test_script_given_directly(self, tmp_path: Path):
        _write(tmp_path, "settings:\n  speed: 0\n")
        result = CliRunner().invoke(
            cli, ["termshow", "validate", str(tmp_path / "demo.termshow.yml")]
        )
        assert result.exit_code == 1
        assert "settings.speed" in result.output

    def test_script_without_recording(self, tmp_path: Path):
        script = tmp_path / "lonely.termshow.yml"
        script.write_text("chapters: []\n", encoding="utf-8")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(script)])
        assert result.exit_code != 0
        assert "No recording" in result.output

    def test_several_files(self, tmp_path: Path):
        good = _write(tmp_path)
        bad = tmp_path / "bad.termshow"
        bad.write_text('{"version": 1, "format": "termshow"}\n', encoding="utf-8")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(good), str(bad)])
        assert result.exit_code == 1
        assert f"✓ {good}: no problems" in result.output
        assert "error: bad.termshow: header: missing 'term'" in result.output

    def test_script_option_needs_one_recording(self, tmp_path: Path):
        source = _write(tmp_path, "chapters: []\n")
        result = CliRunner().invoke(
            cli,
            [
                "termshow",
                "validate",
                str(source),
                str(source),
                "--script",
                str(tmp_path / "demo.termshow.yml"),
            ],
        )
        assert result.exit_code != 0
        assert "--script" in result.output


# ---------------------------------------------------------------------------
# Real recordings come out clean
# ---------------------------------------------------------------------------


def _tracked_docs(suffix: str) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "docs"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover
        out = ""
    return [ROOT / p for p in out.splitlines() if p.endswith(suffix)]


def _spec_recordings(tmp_path_factory) -> list[Path]:
    """Recordings (and scripts) from the synthetic test-package specs, written to disk."""
    out = tmp_path_factory.mktemp("specs")
    found = []
    for spec_path in sorted(SPECS_DIR.glob("*.py")):
        if ".termshow" not in spec_path.read_text(encoding="utf-8"):
            continue
        spec = importlib.util.spec_from_file_location(f"_spec_{spec_path.stem}", spec_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        files = module.SPEC["files"]
        for name, content in files.items():
            if name.endswith((".termshow", ".termshow.yml")):
                dest = out / spec_path.stem / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                if name.endswith(".termshow"):
                    found.append(dest)
    return found


@pytest.mark.parametrize("path", _tracked_docs(".termshow"), ids=lambda p: str(p.relative_to(ROOT)))
def test_docs_recordings_clean(path: Path):
    assert [str(p) for p in validate(path)] == []


def test_spec_recordings_clean(tmp_path_factory):
    recordings = _spec_recordings(tmp_path_factory)
    assert recordings
    problems = [f"{path.name}: {p}" for path in recordings for p in validate(path)]
    assert problems == []


# ---------------------------------------------------------------------------
# In step with the JSON Schemas
# ---------------------------------------------------------------------------


def test_theme_names_match_code():
    assert sorted(THEME_NAMES) == theme_names()


REGION = {"row": 0, "col": 0, "width": 1, "height": 1}

# Scripts on which the checks and a JSON Schema validator should agree
SCRIPT_CASES = [
    {},
    {"source": "x.termshow"},
    {"source": 5},
    {"extra": 1},
    {"settings": None},
    {"settings": {"theme": "nord", "window_chrome": "minimal", "font_family": "Mono"}},
    {"settings": {"theme": "auto"}},
    {"settings": {"theme": "neon"}},
    {"settings": {"theme": {"light": "nord", "dark": {"base": "dracula", "bg": "#000"}}}},
    {"settings": {"theme": {"light": "nord"}}},
    {"settings": {"theme": {"base": "nord", "palette": ["#000000"] * 16}}},
    {"settings": {"theme": {"palette": ["#000000"] * 9}}},
    {"settings": {"theme": {"fg": "#00000g"}}},
    {"settings": {"theme": 7}},
    {"settings": {"line_height": 1.4, "show_cursor": False, "speed": 2, "prompt": None}},
    {"settings": {"line_height": -1}},
    {"settings": {"show_cursor": 1}},
    {"settings": {"prompt_pattern": 3}},
    {"settings": {"window_chrome": "mac"}},
    {"chapters": [{"at": 0, "label": "x"}, {"at": 1.5}]},
    {"chapters": [{"label": "x"}]},
    {"chapters": [{"at": 0, "title": "x"}]},
    {"chapters": [{"at": 0, "label": 3}]},
    {"chapters": "intro"},
    {"cuts": [{"from": 0, "to": 1, "type": "ellipsis"}]},
    {"cuts": [{"from": 0, "to": 1, "type": "fade"}]},
    {"cuts": [{"from": -1, "to": 1}]},
    {"speed_map": [{"from": 0, "to": 1, "speed": 0.5}]},
    {"speed_map": [{"from": 0, "to": 1, "speed": 0}]},
    {"speed_map": [{"from": 0}]},
    {
        "annotations": [
            {"at": 0, "duration": 1, "text": "a", "style": "highlight", "width": "large"}
        ]
    },
    {"annotations": [{"at": 0, "style": "bold"}]},
    {"annotations": [{"at": 0, "duration": -1}]},
    {"annotations": [None]},
    {"highlights": [{"at": 0, "target": {"region": REGION}}]},
    {"highlights": [{"at": 0, "region": REGION}]},
    {"highlights": [{"at": 0, "target": {"lines": [0, 1], "track_scroll": True}}]},
    {"highlights": [{"at": 0, "target": {"match": "x", "group": 0}, "pulse": True}]},
    {"highlights": [{"at": 0}]},
    {"highlights": [{"at": 0, "target": {"region": REGION}, "region": REGION}]},
    {"highlights": [{"at": 0, "target": {"group": 1}}]},
    {"highlights": [{"at": 0, "target": {"lines": []}}]},
    {"highlights": [{"at": 0, "target": {"lines": [-1]}}]},
    {"highlights": [{"at": 0, "target": {"region": {**REGION, "height": 0}}}]},
    {"highlights": [{"at": 0, "target": {"region": {"row": 0, "col": 0}}}]},
    {"highlights": [{"at": 0, "target": {"match": "x", "group": -1}}]},
    {"highlights": [{"at": 0, "target": {"match": "x"}, "style": "neon"}]},
    {"highlights": [{"at": 0, "target": {"match": "x"}, "fade_in": -0.1}]},
    {"highlights": [{"at": 0, "target": {"match": "x"}, "badge_text": 1}]},
    {"snippets": [{"at": 0, "text": "x", "label": "Copy"}]},
    {"snippets": [{"at": 0, "match": "x"}]},
    {"snippets": [{"at": 0}]},
    {"snippets": [{"at": 0, "text": "x", "copy": True}]},
]

HEADER = {"version": 1, "format": "termshow", "term": {"cols": 80, "rows": 24}}

# Recording lines (header first) on which the checks and a validator should agree
RECORDING_CASES = [
    [HEADER],
    [{**HEADER, "title": "x", "timestamp": 1700000000}],
    [{**HEADER, "timestamp": 1.5}],
    [{**HEADER, "version": 2}],
    [{**HEADER, "format": "asciicast"}],
    [{"version": 1, "format": "termshow"}],
    [{**HEADER, "term": {"cols": 80}}],
    [{**HEADER, "term": {"cols": 0, "rows": 24}}],
    [{**HEADER, "term": {"cols": 80, "rows": 24, "type": 5}}],
    [{**HEADER, "term": {"cols": 80, "rows": 24, "theme": {"bg": "#123"}}}],
    [{**HEADER, "term": {"cols": 80, "rows": 24, "theme": {"bg": "blue"}}}],
    [{**HEADER, "term": {"cols": 80, "rows": 24, "theme": {"palette": ["#000000"] * 15}}}],
    [{**HEADER, "term": {"cols": 80, "rows": 24, "theme": {"palette": "#000000"}}}],
    [HEADER, [0, "o", "x"], [0.5, "r", "80x24"], [0.1, "x", "0"], [0, "m", "Intro"]],
    [HEADER, [-0.1, "o", "x"]],
    [HEADER, [0, "o"]],
    [HEADER, [0, "o", "x", "extra"]],
    [HEADER, [0, "", "x"]],
    [HEADER, [0, "o", None]],
    [HEADER, [0, "r", "80 by 24"]],
    [HEADER, [0, "x", "1.5"]],
    [HEADER, {"t": 0}],
]


def _has_errors(problems: list[Problem]) -> bool:
    return any(p.severity == ERROR for p in problems)


@pytest.mark.parametrize("data", SCRIPT_CASES, ids=lambda d: json.dumps(d)[:60])
def test_script_checks_agree_with_schema(data):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMA_DIR / "termshow-script.schema.json").read_text())
    schema_ok = jsonschema.Draft202012Validator(schema).is_valid(data)
    problems: list[Problem] = []
    check_script_data(data, "x.termshow.yml", problems)
    assert _has_errors(problems) is not schema_ok, [str(p) for p in problems]


@pytest.mark.parametrize("lines", RECORDING_CASES, ids=lambda d: json.dumps(d)[:60])
def test_recording_checks_agree_with_schema(lines):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMA_DIR / "termshow-recording.schema.json").read_text())
    defs = schema["$defs"]

    def ok(instance, pointer: str) -> bool:
        return jsonschema.Draft202012Validator(
            {"$ref": f"#/$defs/{pointer}", "$defs": defs}
        ).is_valid(instance)

    schema_ok = ok(lines[0], "header") and all(ok(e, "event") for e in lines[1:])
    problems = _recording_problems("\n".join(json.dumps(line) for line in lines))
    assert _has_errors(problems) is not schema_ok, [str(p) for p in problems]
