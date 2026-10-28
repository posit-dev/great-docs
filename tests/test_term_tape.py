"""Tests for converting VHS tapes to Termshow scripts (`termshow import-tape`)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from yaml12 import parse_yaml

from great_docs._term_player.parser import parse_termshow
from great_docs._term_player.steps import KEYS, load_steps
from great_docs._term_player.tape import (
    DEFAULT_SHELL,
    VHS_PROMPT,
    VHS_PROMPT_PATTERN,
    TapeError,
    _scalar,
    convert_tape,
    parse_tape,
)
from great_docs._term_player.tape import KEYS as TAPE_KEYS
from great_docs._term_player.validate import check_script_text
from great_docs.cli import cli

_SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "great_docs/_term_player/schemas/termshow-script.schema.json"
    ).read_text(encoding="utf-8")
)

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX pseudo-terminal")

# A tape using most of what VHS has
SAMPLE = """\
# A VHS demo
Output demo.gif
Require echo

Set Shell "sh"
Set FontSize 32
Set Width 1200
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 10ms
Set WindowBar Colorful
Env GREETING "hello there"

Hide
Type "cd /tmp"
Enter
Show

Type "echo $GREETING"
Sleep 100ms
Enter
Wait
Type@5ms 'printf "a\\nb\\n"'
Enter
Wait@3s
Type "sleep 0.2; echo done"
Enter
Wait+Screen@5s /^done/
Type "abc"
Backspace 3
Ctrl+C
Ctrl+Alt+Delete
Copy "echo pasted"
Paste
Enter
Wait
Screenshot shot.png
Sleep 200ms
"""


def _steps(tape: str) -> list:
    return parse_tape(tape).steps


def _data(tape: str) -> dict:
    """The converted script, read back from its YAML."""
    return parse_yaml(parse_tape(tape).to_yaml())


def _problems(text: str) -> list[str]:
    problems = []
    check_script_text(text, "demo.termshow.yml", problems)
    return [str(p) for p in problems]


# Steps --------------------------------------------------------------------------------------


class TestSteps:
    def test_type(self):
        assert _steps('Type "ls -l"') == [{"type": "ls -l"}]

    @pytest.mark.parametrize("quoted", ['"it\'s"', "'say \"hi\"'", "`a \"b\" 'c'`"])
    def test_quotes(self, quoted):
        expected = quoted[1:-1]
        assert _steps(f"Type {quoted}") == [{"type": expected}]

    def test_type_joins_strings(self):
        assert _steps('Type "echo " "hi"') == [{"type": "echo hi"}]

    def test_type_speed(self):
        assert _steps('Type@500ms "x"') == [{"type": "x", "delay": 0.5}]

    def test_enter(self):
        assert _steps("Enter") == ["enter"]

    def test_enter_with_count_or_speed(self):
        assert _steps("Enter 2") == [{"key": "enter", "count": 2}]
        assert _steps("Enter@100ms") == [{"key": "enter", "delay": 0.1}]

    @pytest.mark.parametrize("vhs,key", sorted(TAPE_KEYS.items()))
    def test_keys(self, vhs, key):
        assert key in KEYS
        expected = "enter" if key == "enter" else {"key": key}
        assert _steps(vhs) == [expected]

    def test_key_count_and_speed(self):
        assert _steps("Backspace@50ms 3") == [{"key": "backspace", "count": 3, "delay": 0.05}]

    def test_ctrl_and_alt(self):
        assert _steps("Ctrl+C\nAlt+b") == [{"key": "ctrl+c"}, {"key": "alt+b"}]

    @pytest.mark.parametrize("combo", ["Ctrl+Alt+Delete", "Shift+Tab", "Ctrl+@", "Alt+Enter"])
    def test_combos_not_converted(self, combo):
        script = parse_tape(combo)
        assert script.steps == []
        assert script.skipped[0].text == combo

    @pytest.mark.parametrize(
        "time,seconds", [("500ms", 0.5), ("2s", 2), ("1.5", 1.5), ("3", 3), ("1m", 60)]
    )
    def test_sleep(self, time, seconds):
        assert _steps(f"Sleep {time}") == [{"sleep": seconds}]

    def test_hide_and_show(self):
        assert _steps("Hide\nShow") == ["hide", "show"]

    def test_wait_for_the_prompt(self):
        assert _steps("Wait") == [{"wait_for": VHS_PROMPT_PATTERN}]

    def test_wait_for_a_pattern(self):
        assert _steps("Wait /done/") == [{"wait_for": "done"}]
        assert _steps("Wait+Line /a b/") == [{"wait_for": "a b"}]

    def test_wait_on_the_screen_with_timeout(self):
        assert _steps("Wait+Screen@10s /ok/") == [{"wait_for": "ok", "screen": True, "timeout": 10}]

    def test_wait_uses_wait_pattern(self):
        assert _steps("Set WaitPattern /\\$ $/\nWait") == [{"wait_for": "\\$ $"}]

    def test_copy_and_paste(self):
        assert _steps('Copy "hello"\nPaste\nPaste') == [{"type": "hello"}] * 2

    def test_paste_without_copy(self):
        script = parse_tape("Paste")
        assert script.steps == []
        assert script.skipped[0].reason == "nothing was copied before it"

    def test_comments_and_blank_lines(self):
        assert _steps("# comment\n\n   \n  Enter  \n") == ["enter"]


class TestRun:
    def test_type_enter_wait_becomes_run(self):
        assert _steps('Type "ls"\nEnter\nWait') == [{"run": "ls"}]

    def test_run_keeps_speed_and_timeout(self):
        assert _steps('Type@20ms "ls"\nEnter\nWait@3s') == [
            {"run": "ls", "delay": 0.02, "timeout": 3}
        ]

    @pytest.mark.parametrize(
        "tape",
        [
            'Type "ls"\nEnter\nWait /x/',
            'Type "ls"\nEnter\nWait+Screen',
            'Type "ls"\nSleep 1\nEnter\nWait',
            'Type "ls"\nEnter 2\nWait',
            'Set WaitPattern /x/\nType "ls"\nEnter\nWait',
        ],
    )
    def test_not_collapsed(self, tape):
        assert not any(isinstance(s, dict) and "run" in s for s in _steps(tape))


# Settings -----------------------------------------------------------------------------------


class TestSettings:
    def test_defaults(self):
        script = parse_tape('Type "x"')
        assert script.record == {
            "shell": DEFAULT_SHELL,
            "env": {"PS1": VHS_PROMPT},
            "prompt_pattern": VHS_PROMPT_PATTERN,
        }
        assert script.settings == {}

    @pytest.mark.parametrize(
        "shell,expected",
        [
            ("bash", "bash --noprofile --norc"),
            ('"zsh"', "zsh -f"),
            ("fish", "fish --no-config"),
            ("sh", "sh"),
            ('"nu --no-config-file"', "nu --no-config-file"),
        ],
    )
    def test_shell(self, shell, expected):
        assert parse_tape(f"Set Shell {shell}").record["shell"] == expected

    def test_env(self):
        env = parse_tape('Env NAME "a b"\nEnv OTHER plain').record["env"]
        assert env == {"PS1": VHS_PROMPT, "NAME": "a b", "OTHER": "plain"}

    def test_timing(self):
        record = parse_tape("Set TypingSpeed 75ms\nSet WaitTimeout 30s").record
        assert record["typing_delay"] == 0.075
        assert record["timeout"] == 30

    @pytest.mark.parametrize(
        "name,expected",
        [
            ('"Catppuccin Mocha"', "catppuccin-mocha"),
            ("Dracula", "dracula"),
            ('"TokyoNight"', "tokyo-night"),
            ('"rose_pine"', "rose-pine"),
        ],
    )
    def test_theme_names(self, name, expected):
        assert parse_tape(f"Set Theme {name}").settings["theme"] == expected

    def test_unknown_theme(self):
        script = parse_tape('Set Theme "Builtin Pastel Dark"')
        assert "theme" not in script.settings
        assert "not one of Termshow's themes" in script.skipped[0].reason

    def test_theme_colors(self):
        names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
        colors = {n: f"#00000{i}" for i, n in enumerate(names)}
        colors |= {f"bright{n.title()}": f"#11111{i}" for i, n in enumerate(names)}
        colors |= {"foreground": "#ffffff", "background": "#000000", "cursor": "#ff0000"}
        theme = parse_tape(f"Set Theme {json.dumps(colors)}").settings["theme"]
        assert theme["fg"] == "#ffffff"
        assert theme["bg"] == "#000000"
        assert theme["cursor"] == "#ff0000"
        assert theme["palette"][5] == "#000005"
        assert theme["palette"][13] == "#111115"

    def test_incomplete_theme_colors(self):
        script = parse_tape('Set Theme {"foreground": "#ffffff"}')
        assert "theme" not in script.settings
        assert script.skipped

    def test_render_settings(self):
        settings = parse_tape(
            'Set WindowBar Rings\nSet LineHeight 1.2\nSet FontFamily "Fira Code"\n'
            "Set PlaybackSpeed 2"
        ).settings
        assert settings == {
            "window_chrome": "minimal",
            "line_height": 1.2,
            "font_family": "Fira Code",
            "speed": 2,
        }

    @pytest.mark.parametrize("bar,chrome", [("Colorful", "colorful"), ("RingsRight", "minimal")])
    def test_window_bars(self, bar, chrome):
        assert parse_tape(f"Set WindowBar {bar}").settings["window_chrome"] == chrome


# What isn't converted -----------------------------------------------------------------------


class TestNotConverted:
    @pytest.mark.parametrize(
        "line",
        [
            "Output demo.gif",
            "Require git",
            "Source other.tape",
            "Screenshot out.png",
            "Set Width 1200",
            "Set Height 600",
            "Set FontSize 22",
            "Set Padding 20",
            "Set Framerate 60",
            "Set CursorBlink false",
            "Set Something 1",
            "Set WindowBar Fancy",
            "ScrollUp 3",
        ],
    )
    def test_listed(self, line):
        script = parse_tape(f"Enter\n{line}\n")
        assert script.steps == ["enter"]
        assert [(s.line, s.text) for s in script.skipped] == [(2, line)]

    def test_listed_in_the_script(self):
        text = parse_tape("Output demo.gif\nType 'x'\nSet Width 900").to_yaml("demo.tape")
        assert "# Converted from demo.tape" in text
        assert "#   line 1: Output demo.gif" in text
        assert "#   line 3: Set Width 900 (VHS sizes the terminal in pixels" in text

    def test_output_names_the_export_command(self):
        (gif,) = parse_tape('Output "demo.gif"').skipped
        assert gif.reason.endswith("`termshow export -o demo.gif` makes the GIF")
        (frames,) = parse_tape("Output frames/").skipped
        assert "makes a GIF, a video, or an SVG" in frames.reason

    def test_header_without_names(self):
        text = parse_tape("Output demo.gif\nEnter").to_yaml()
        assert text.startswith("# Not converted:\n#   line 1: Output demo.gif")
        assert parse_tape("Enter").to_yaml().startswith("record:\n")


class TestErrors:
    @pytest.mark.parametrize(
        "line,message",
        [
            ("Type", "Type needs a string"),
            ("Type ls", "Type needs a string"),
            ("Sleep", "Sleep needs a time"),
            ("Sleep soon", "isn't a time"),
            ("Type@fast 'x'", "isn't a time"),
            ("Backspace two", "isn't a number of times"),
            ("Backspace 0", "isn't a number of times"),
            ("Wait done", "between slashes"),
            ("Wait+Page", "Wait+Screen or Wait+Line"),
            ("Sleep+Screen 1", "doesn't take +Screen"),
            ("Sleep@1s 1", "doesn't take @1s"),
            ("Env NAME", "Env needs a name and a value"),
            ("Set Shell", "Set needs an option and a value"),
            ("Set LineHeight tall", "isn't a number"),
            ("Set Theme {oops", "JSON object"),
            ("Copy", "Copy needs a string"),
        ],
    )
    def test_line_number(self, line, message):
        with pytest.raises(TapeError, match=re.escape(message)) as info:
            parse_tape(f"# first\nEnter\n{line}\n")
        assert info.value.line == 3
        assert str(info.value).startswith("line 3: ")


# The YAML -----------------------------------------------------------------------------------


class TestYaml:
    @pytest.mark.parametrize(
        "text",
        [
            "ls -l",
            "echo $HOME",
            "it's",
            'say "hi"',
            "a: b",
            "x #y",
            "- item",
            "true",
            "No",
            "null",
            "~",
            "123",
            ".5",
            "1e3",
            "trailing ",
            " leading",
            "",
            "tab\there",
            "new\nline",
            "\x1b[A",
            "{a}",
            "[a]",
            "*star",
            "&anchor",
            "!tag",
            "%pct",
            "@at",
            "`tick`",
            "a, b",
            "path/to/file.txt",
            "café ☕",
        ],
    )
    def test_strings_round_trip(self, text):
        assert parse_yaml(f"value: {_scalar(text)}") == {"value": text}

    def test_numbers(self):
        assert _scalar(0.5) == "0.5"
        assert _scalar(3.0) == "3"
        assert _scalar(True) == "true"

    def test_sample_round_trips(self):
        script = parse_tape(SAMPLE)
        data = parse_yaml(script.to_yaml())
        assert data["steps"] == script.steps
        assert data["record"] == script.record
        assert data["settings"] == script.settings

    def test_sample_conversion(self):
        data = _data(SAMPLE)
        assert data["settings"] == {"theme": "catppuccin-mocha", "window_chrome": "colorful"}
        assert data["record"]["shell"] == "sh"
        assert data["record"]["env"]["GREETING"] == "hello there"
        assert data["steps"][:4] == ["hide", {"type": "cd /tmp"}, "enter", "show"]
        assert {"run": 'printf "a\\nb\\n"', "delay": 0.005, "timeout": 3} in data["steps"]
        assert {"run": "echo pasted"} in data["steps"]
        assert {"key": "ctrl+c"} in data["steps"]

    @pytest.mark.parametrize(
        "tape",
        [
            SAMPLE,
            'Type "x"',
            "Set Shell zsh\nSet Theme Nord\nSet WindowBar Rings\nEnter 3\nAlt+f",
            'Set WaitPattern /\\$ $/\nEnv PS1 "$ "\nType "ls"\nEnter\nWait@2s',
        ],
    )
    def test_valid_scripts(self, tape):
        assert _problems(parse_tape(tape).to_yaml("demo.tape", "demo.termshow.yml")) == []

    def test_guide_example(self):
        """The tape in the guide converts to the script shown next to it."""
        guide = Path(__file__).resolve().parents[1] / "docs/user_guide/41-terminal-recordings.qmd"
        text = guide.read_text(encoding="utf-8")
        tape = re.search(r'```\{\.text filename="demo\.tape"\}\n(.*?)```', text, re.S)[1]
        script = re.search(r'```\{\.yaml filename="demo\.termshow\.yml"\}\n(.*?)```', text, re.S)[1]
        # The guide leaves out the comments at the top
        converted = re.sub(r"\A(#.*\n)+\n", "", parse_tape(tape).to_yaml("demo.tape"))
        assert converted == script

    def test_matches_schema(self):
        jsonschema = pytest.importorskip("jsonschema")
        validator = jsonschema.Draft202012Validator(_SCHEMA)
        assert list(validator.iter_errors(_data(SAMPLE))) == []


# Recording ----------------------------------------------------------------------------------


@posix_only
class TestRecording:
    def test_sample_records(self, tmp_path):
        tape = tmp_path / "demo.tape"
        tape.write_text(SAMPLE, encoding="utf-8")
        script = tmp_path / "demo.termshow.yml"
        script.write_text(convert_tape(tape).to_yaml(), encoding="utf-8")

        result = CliRunner().invoke(cli, ["termshow", "record", "--steps", str(script)])
        assert result.exit_code == 0, result.output
        output = "".join(
            e.data for e in parse_termshow(tmp_path / "demo.termshow").events if e.code == "o"
        )
        assert "hello there" in output
        assert "a\r\nb" in output
        assert "pasted" in output

    def test_loads_as_steps(self, tmp_path):
        script = tmp_path / "demo.termshow.yml"
        script.write_text(parse_tape(SAMPLE).to_yaml(), encoding="utf-8")
        settings, steps = load_steps(script)
        assert settings.env["PS1"] == VHS_PROMPT
        assert steps[0].action == "hide"


# The command --------------------------------------------------------------------------------


class TestCli:
    def _tape(self, tmp_path: Path, text: str = 'Type "echo hi"\nEnter\nWait\n') -> Path:
        tape = tmp_path / "demo.tape"
        tape.write_text(text, encoding="utf-8")
        return tape

    def test_default_output(self, tmp_path):
        tape = self._tape(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "import-tape", str(tape)])
        assert result.exit_code == 0, result.output
        script = tmp_path / "demo.termshow.yml"
        assert parse_yaml(script.read_text(encoding="utf-8"))["steps"] == [{"run": "echo hi"}]
        assert "(1 step)" in result.output
        assert "record --steps" in result.output

    @pytest.mark.parametrize("output", ["out.termshow.yml", "out.termshow", "out"])
    def test_output_names(self, tmp_path, output):
        tape = self._tape(tmp_path)
        result = CliRunner().invoke(
            cli, ["termshow", "import-tape", str(tape), str(tmp_path / "sub" / output)]
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "sub" / "out.termshow.yml").exists()

    def test_refuses_to_overwrite(self, tmp_path):
        tape = self._tape(tmp_path)
        script = tmp_path / "demo.termshow.yml"
        script.write_text("mine", encoding="utf-8")
        result = CliRunner().invoke(cli, ["termshow", "import-tape", str(tape)])
        assert result.exit_code == 1
        assert "already exists" in result.output
        assert script.read_text(encoding="utf-8") == "mine"

        result = CliRunner().invoke(cli, ["termshow", "import-tape", str(tape), "--force"])
        assert result.exit_code == 0, result.output
        assert "echo hi" in script.read_text(encoding="utf-8")

    def test_lists_what_was_not_converted(self, tmp_path):
        tape = self._tape(tmp_path, "Output demo.gif\nSet FontSize 30\nEnter\n")
        result = CliRunner().invoke(cli, ["termshow", "import-tape", str(tape)])
        assert result.exit_code == 0, result.output
        assert "Not converted:" in result.output
        assert "line 1: Output demo.gif" in result.output
        assert "line 2: Set FontSize 30" in result.output

    def test_bad_tape(self, tmp_path):
        tape = self._tape(tmp_path, "Enter\nSleep\n")
        result = CliRunner().invoke(cli, ["termshow", "import-tape", str(tape)])
        assert result.exit_code == 1
        assert "demo.tape, line 2: Sleep needs a time" in result.output
        assert not (tmp_path / "demo.termshow.yml").exists()

    @posix_only
    def test_record(self, tmp_path):
        tape = self._tape(tmp_path, 'Set Shell sh\nType "echo hi"\nEnter\nWait\n')
        result = CliRunner().invoke(cli, ["termshow", "import-tape", str(tape), "--record"])
        assert result.exit_code == 0, result.output
        assert "✓ Recorded" in result.output
        recording = parse_termshow(tmp_path / "demo.termshow")
        assert "hi" in "".join(e.data for e in recording.events if e.code == "o")
