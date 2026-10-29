"""Tests for scripted recordings (`steps:` and `termshow record --steps`)."""

from __future__ import annotations

import json
import re
import shlex
import shutil
import sys
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player.parser import parse_termshow
from great_docs._term_player.steps import (
    ACTIONS,
    DEFAULT_ENV,
    KEPT_ENV,
    KEYS,
    WORDS,
    RecordSettings,
    Step,
    StepsError,
    key_sequence,
    load_steps,
    record_steps,
    shell_env,
)
from great_docs._term_player.validate import check_script_data, validate
from great_docs.cli import cli

_SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "great_docs/_term_player/schemas/termshow-script.schema.json"
    ).read_text(encoding="utf-8")
)

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX pseudo-terminal")


def _write(tmp_path: Path, text: str, name: str = "demo.termshow.yml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _fast(**kwargs) -> RecordSettings:
    """Settings that type instantly, for quick tests."""
    return RecordSettings(typing_delay=0, typing_jitter=0, timeout=5, **kwargs)


def _output(recording) -> str:
    return "".join(e.data for e in recording.events if e.code == "o")


def _errors(data: dict) -> list[str]:
    problems = []
    check_script_data(data, "demo.termshow.yml", problems)
    return [str(p).split(": ", 1)[1] for p in problems]


# ---------------------------------------------------------------------------
# Reading the steps
# ---------------------------------------------------------------------------


class TestLoadSteps:
    def test_defaults(self, tmp_path: Path):
        settings, steps = load_steps(_write(tmp_path, "steps:\n  - run: ls\n"))
        assert settings == RecordSettings(cwd=tmp_path.resolve())
        assert steps == [Step("run", "ls")]

    def test_record_settings(self, tmp_path: Path):
        (tmp_path / "work").mkdir()
        path = _write(
            tmp_path,
            "record:\n"
            "  shell: bash --norc\n"
            "  cols: 100\n"
            "  cwd: work\n"
            "  env: {NAME: demo, COUNT: 3, DEBUG: true}\n"
            "  typing_delay: 0.1\n"
            "steps:\n  - enter\n",
        )
        settings, _ = load_steps(path)
        assert settings.shell == "bash --norc"
        assert settings.cols == 100
        assert settings.cwd == (tmp_path / "work").resolve()
        assert settings.env == {"NAME": "demo", "COUNT": "3", "DEBUG": "true"}
        assert settings.typing_delay == 0.1

    def test_steps(self, tmp_path: Path):
        path = _write(
            tmp_path,
            "steps:\n"
            "  - type: ls\n"
            "  - enter\n"
            "  - key: up\n    count: 2\n"
            "  - wait_for: done\n    screen: true\n"
            "  - hide\n",
        )
        _, steps = load_steps(path)
        assert steps == [
            Step("type", "ls"),
            Step("enter"),
            Step("key", "up", {"count": 2}),
            Step("wait_for", "done", {"screen": True}),
            Step("hide"),
        ]
        assert [s.describe() for s in steps[:3]] == ["type: ls", "enter", "key: up"]

    def test_errors_in_steps_stop_recording(self, tmp_path: Path):
        path = _write(tmp_path, "steps:\n  - typ: ls\n")
        with pytest.raises(StepsError, match=r"steps\[0\]: unknown key 'typ'"):
            load_steps(path)

    def test_errors_elsewhere_dont(self, tmp_path: Path):
        path = _write(tmp_path, "settings:\n  speed: 0\nsteps:\n  - enter\n")
        _, steps = load_steps(path)
        assert steps == [Step("enter")]

    def test_no_steps(self, tmp_path: Path):
        with pytest.raises(StepsError, match="no steps"):
            load_steps(_write(tmp_path, "chapters: []\n"))


class TestKeys:
    @pytest.mark.parametrize(
        ("name", "sequence"),
        [
            ("enter", "\r"),
            ("up", "\x1b[A"),
            ("ctrl+c", "\x03"),
            ("ctrl+d", "\x04"),
            ("alt+b", "\x1bb"),
        ],
    )
    def test_sequences(self, name: str, sequence: str):
        assert key_sequence(name) == sequence

    @pytest.mark.parametrize("name", ["f1", "ctrl+1", "shift+a", "Enter"])
    def test_unknown(self, name: str):
        assert key_sequence(name) is None

    def test_schema_lists_every_key(self):
        pattern = _SCHEMA["$defs"]["keyName"]["pattern"]
        names = [*KEYS, "ctrl+a", "ctrl+z", "alt+a"]
        assert all(re.search(pattern, name) for name in names)
        assert set(re.findall(r"[a-z]+", pattern.split("(?:ctrl")[0])) == set(KEYS)


class TestSchemaMatchesCode:
    def test_actions(self):
        step = _SCHEMA["$defs"]["step"]["oneOf"]
        assert step[0]["enum"] == list(WORDS)
        assert [b["required"][0] for b in step[1]["oneOf"]] == list(ACTIONS)
        options = {o for opts in ACTIONS.values() for o in opts}
        assert set(step[1]["properties"]) == set(ACTIONS) | options

    def test_record_settings(self):
        fields = set(RecordSettings.__dataclass_fields__)
        assert set(_SCHEMA["$defs"]["record"]["properties"]) == fields

    def test_defaults(self):
        props = _SCHEMA["$defs"]["record"]["properties"]
        defaults = RecordSettings()
        for name, prop in props.items():
            if "default" in prop:
                assert prop["default"] == getattr(defaults, name), name

    def test_kept_env_is_documented(self):
        description = _SCHEMA["$defs"]["record"]["properties"]["inherit_env"]["description"]
        for name in (*KEPT_ENV, "LC_*"):
            assert name in description


class TestShellEnv:
    ENVIRON = {
        "PATH": "/usr/bin",
        "HOME": "/home/me",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "PYTHONSTARTUP": "/editor/pythonrc.py",
        "CI": "true",
        "NO_COLOR": "1",
        "COLUMNS": "200",
        "PS1": "% ",
    }

    def test_only_kept_variables(self):
        env = shell_env(RecordSettings(), self.ENVIRON)
        assert env == {
            "PATH": "/usr/bin",
            "HOME": "/home/me",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            **DEFAULT_ENV,
        }

    def test_inherit_env(self):
        env = shell_env(RecordSettings(inherit_env=True), self.ENVIRON)
        assert env["PYTHONSTARTUP"] == "/editor/pythonrc.py"
        assert env["CI"] == "true"
        assert "COLUMNS" not in env
        assert env["PS1"] == DEFAULT_ENV["PS1"]

    def test_record_env_goes_on_top(self):
        settings = RecordSettings(env={"PS1": "> ", "CI": "1", "PATH": "/opt/bin"})
        env = shell_env(settings, self.ENVIRON)
        assert (env["PS1"], env["CI"], env["PATH"]) == ("> ", "1", "/opt/bin")

    def test_current_environment(self, monkeypatch):
        monkeypatch.setenv("TERMSHOW_TEST_LEAK", "1")
        assert "TERMSHOW_TEST_LEAK" not in shell_env(RecordSettings())
        assert shell_env(RecordSettings(inherit_env=True))["TERMSHOW_TEST_LEAK"] == "1"

    def test_loaded_from_the_script(self, tmp_path: Path):
        script = _write(tmp_path, "record:\n  inherit_env: true\nsteps:\n  - enter\n")
        assert load_steps(script)[0].inherit_env is True
        assert _errors({"record": {"inherit_env": "yes"}}) == [
            "record.inherit_env: must be true or false, got 'yes'"
        ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid(self):
        data = {
            "record": {"shell": "bash --norc", "env": {"A": 1}, "prompt_pattern": r"\$ $"},
            "steps": [
                "enter",
                "hide",
                {"run": "ls", "timeout": 3, "delay": 0.1},
                {"key": "ctrl+c", "count": 2},
                {"wait_for": "done", "screen": True},
                {"sleep": 1},
                {"marker": "Install"},
            ],
        }
        assert _errors(data) == []

    @pytest.mark.parametrize(
        ("step", "message"),
        [
            ("entr", "must be one of enter, hide, show; got 'entr' (did you mean 'enter'?)"),
            ({"type": "ls", "count": 2}, "goes with 'key', not 'type'"),
            ({"run": "ls", "screen": True}, "goes with 'wait_for', not 'run'"),
            ({"run": "a", "type": "b"}, "can't have both 'type' and 'run'"),
            ({"key": "Ctrl+C"}, "keys are written in lower case: 'ctrl+c'"),
            ({"key": "f1"}, "must be a key like 'enter', 'up', or 'ctrl+c', got 'f1'"),
            ({"wait_for": "("}, "isn't a valid regular expression"),
            ({"sleep": -1}, "can't be negative"),
            (3, "must be a string or a mapping, got 3"),
        ],
    )
    def test_step_mistakes(self, step, message: str):
        assert any(message in e for e in _errors({"steps": [step]}))

    @pytest.mark.parametrize(
        ("record", "message"),
        [
            ({"colz": 80}, "unknown key 'colz' (did you mean 'cols'?)"),
            ({"typing_jitter": 2}, "can't be more than 1"),
            ({"env": {"A": [1]}}, "record.env.A: must be a string or a number or true or false"),
            ({"prompt_pattern": "("}, "isn't a valid regular expression"),
            ({"shell": 'bash "x'}, "can't be split into words"),
        ],
    )
    def test_record_mistakes(self, record: dict, message: str):
        assert any(message in e for e in _errors({"record": record}))

    def test_jsonschema_agrees(self):
        jsonschema = pytest.importorskip("jsonschema")
        validator = jsonschema.Draft202012Validator(_SCHEMA)
        good = {"record": {"cols": 90}, "steps": ["enter", {"key": "tab", "count": 2}]}
        assert list(validator.iter_errors(good)) == []
        for bad in [{"steps": ["entr"]}, {"steps": [{"run": "a", "type": "b"}]}, {"steps": [{}]}]:
            assert list(validator.iter_errors(bad)), bad


class TestCursorLine:
    """The text a `wait_for` without `screen: true` is matched against."""

    def _line(self, output: str) -> str:
        from great_docs._term_player.steps import _Session

        session = _Session(RecordSettings(cols=20, rows=2))
        session.emulator.feed(output)
        return session.cursor_line()

    def test_keeps_spaces_before_the_cursor(self):
        assert self._line("$ ") == "$ "

    def test_text_after_the_cursor(self):
        assert self._line("$ hello\x1b[1;3H") == "$ hello"

    def test_wide_char_before_the_prompt(self):
        assert self._line("🐍 $ ") == "🐍 $ "

    def test_wide_char_after_the_cursor(self):
        assert self._line("$ 🎉\x1b[1;3H") == "$ 🎉"


# ---------------------------------------------------------------------------
# Running the steps
# ---------------------------------------------------------------------------


@posix_only
class TestRecordSteps:
    def test_runs_commands(self):
        recording = record_steps(_fast(), [Step("run", "echo hello")])
        assert "hello\r\n" in _output(recording)
        assert [e.data for e in recording.events if e.code == "i"] == ["echo hello"]
        assert recording.events[-1].code == "x" and recording.events[-1].data == "0"
        times = [e.time for e in recording.events]
        assert times == sorted(times)

    def test_terminal_size_and_header(self):
        settings = _fast(cols=100, rows=30)
        recording = record_steps(settings, [Step("run", "stty size")], title="size")
        assert "30 100" in _output(recording)
        assert (recording.term.cols, recording.term.rows) == (100, 30)
        assert recording.term.type == "xterm-256color"
        assert recording.title == "size"

    def test_env_and_cwd(self, tmp_path: Path):
        settings = _fast(cwd=tmp_path, env={"GREETING": "hi there"})
        recording = record_steps(settings, [Step("run", "echo $GREETING"), Step("run", "pwd")])
        assert "hi there" in _output(recording)
        assert str(tmp_path.resolve()) in _output(recording).replace("\r\n", "")

    def test_clean_environment(self, monkeypatch):
        monkeypatch.setenv("TERMSHOW_TEST_LEAK", "leaked")
        step = Step("run", 'echo "[${TERMSHOW_TEST_LEAK:-clean}] [$SHELL]"')
        output = _output(record_steps(_fast(), [step]))
        assert f"[clean] [{shutil.which('sh')}]" in output
        output = _output(record_steps(_fast(inherit_env=True), [step]))
        assert "[leaked]" in output

    def test_typing_takes_time(self):
        settings = RecordSettings(typing_delay=0.05, typing_jitter=0)
        recording = record_steps(settings, [Step("type", "abcdef")])
        echoes = [e.time for e in recording.events if e.code == "o" and e.data in "abcdef"]
        assert echoes[-1] - echoes[0] >= 0.2

    def test_jitter_is_the_same_every_run(self):
        steps = [Step("type", "abcd")]
        a, b = (record_steps(RecordSettings(typing_delay=0.02), steps) for _ in range(2))
        gaps = [[round(x, 1) for x in _gaps(r)] for r in (a, b)]
        assert gaps[0] == gaps[1]

    def test_wait_for_screen(self):
        steps = [
            Step("type", "sleep 0.3; echo READY"),
            Step("enter"),
            Step("wait_for", "^READY$", {"screen": True}),
        ]
        assert "READY" in _output(record_steps(_fast(), steps))

    def test_wait_for_timeout(self):
        steps = [Step("run", "echo hi"), Step("wait_for", "never", {"timeout": 0.3})]
        with pytest.raises(StepsError) as info:
            record_steps(_fast(), steps)
        assert str(info.value) == (
            "steps[1] (wait_for: never): 'never' didn't appear on the cursor's line within 0.3s"
        )
        assert info.value.screen == "$ echo hi\nhi\n$"

    def test_key_presses(self):
        steps = [
            Step("type", "sleep 5"),
            Step("enter"),
            Step("sleep", 0.2),
            Step("key", "ctrl+c"),
            Step("wait_for", r"\$ $"),
        ]
        start = time.monotonic()
        record_steps(_fast(), steps)
        assert time.monotonic() - start < 4

    def test_hidden_steps_take_no_time(self):
        steps = [
            Step("hide"),
            Step("sleep", 0.4),
            Step("run", "echo secret"),
            Step("show"),
            Step("run", "echo shown"),
        ]
        start = time.monotonic()
        recording = record_steps(_fast(), steps)
        elapsed = time.monotonic() - start
        assert recording.duration < elapsed - 0.3
        hidden = [e.time for e in recording.events if "secret" in e.data]
        assert len(set(hidden)) == 1
        # Hidden output is still sent, so the screen matches what the shell printed
        assert "secret" in _output(recording)

    def test_markers(self):
        recording = record_steps(_fast(), [Step("marker", "Install"), Step("run", "true")])
        assert [(e.code, e.data) for e in recording.events if e.code == "m"] == [("m", "Install")]

    def test_custom_shell_and_prompt(self, tmp_path: Path):
        program = tmp_path / "repl.py"
        program.write_text(
            "while True:\n"
            "    try:\n        line = input('> ')\n"
            "    except EOFError:\n        break\n"
            "    print(line.upper())\n",
            encoding="utf-8",
        )
        settings = _fast(
            shell=f"{shlex.quote(sys.executable)} -u {shlex.quote(str(program))}",
            prompt_pattern="> $",
        )
        recording = record_steps(settings, [Step("run", "hello")])
        assert "HELLO" in _output(recording)
        assert recording.events[-1].data == "0"

    def test_exit_ends_the_session(self):
        recording = record_steps(_fast(), [Step("run", "echo bye"), Step("run", "exit 3")])
        assert recording.events[-1].data == "3"

    def test_steps_after_exit_fail(self):
        with pytest.raises(StepsError, match=r"steps\[1\] \(run: ls\): the shell has exited"):
            record_steps(_fast(), [Step("run", "exit"), Step("run", "ls")])

    def test_shell_that_cant_start(self):
        with pytest.raises(StepsError) as info:
            record_steps(_fast(shell="no-such-shell-here"), [Step("enter")])
        assert str(info.value).startswith("while starting 'no-such-shell-here'")
        assert "no-such-shell-here" in info.value.screen

    def test_progress(self):
        seen = []
        record_steps(
            _fast(), [Step("enter"), Step("run", "true")], on_step=lambda i, s: seen.append(i)
        )
        assert seen == [0, 1]


def _gaps(recording) -> list[float]:
    echoes = [e.time for e in recording.events if e.code == "o" and len(e.data) == 1]
    return [b - a for a, b in zip(echoes, echoes[1:])]


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------

_SCRIPT = """\
record:
  typing_delay: 0
  typing_jitter: 0
steps:
  - marker: Greeting
  - run: echo hello
  - sleep: 0.2
chapters:
  - at: 0
    label: Start
"""


@posix_only
class TestRecordCommand:
    def test_records_next_to_script(self, tmp_path: Path):
        script = _write(tmp_path, _SCRIPT)
        result = CliRunner().invoke(cli, ["termshow", "record", "--steps", str(script)])
        assert result.exit_code == 0, result.output
        output = tmp_path / "demo.termshow"
        assert f"✓ Recorded {output}" in result.output
        assert "1/3 marker: Greeting" in result.output
        recording = parse_termshow(output)
        assert recording.title == "demo"
        assert "hello" in _output(recording)
        # The new recording and its script check out together
        assert validate(output) == []

    def test_output_path(self, tmp_path: Path):
        script = _write(tmp_path, _SCRIPT, name="steps.yml")
        result = CliRunner().invoke(
            cli, ["termshow", "record", str(tmp_path / "out"), "--steps", str(script)]
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "out.termshow").exists()

    def test_output_needed_for_other_names(self, tmp_path: Path):
        script = _write(tmp_path, _SCRIPT, name="steps.yml")
        result = CliRunner().invoke(cli, ["termshow", "record", "--steps", str(script)])
        assert result.exit_code == 2
        assert "isn't named NAME.termshow.yml" in result.output

    def test_options_override_script(self, tmp_path: Path):
        script = _write(tmp_path, _SCRIPT.replace("echo hello", "stty size"))
        result = CliRunner().invoke(
            cli, ["termshow", "record", "--steps", str(script), "--cols", "90", "--rows", "20"]
        )
        assert result.exit_code == 0, result.output
        recording = parse_termshow(tmp_path / "demo.termshow")
        assert recording.term.cols == 90
        assert "20 90" in _output(recording)

    def test_failed_step(self, tmp_path: Path):
        text = _SCRIPT.replace("chapters:", "  - wait_for: never\n    timeout: 0.3\nchapters:")
        script = _write(tmp_path, text)
        result = CliRunner().invoke(cli, ["termshow", "record", "--steps", str(script)])
        assert result.exit_code == 1
        assert "✗ steps[3] (wait_for: never): 'never' didn't appear" in result.output
        assert "  │ $ echo hello" in result.output
        assert not (tmp_path / "demo.termshow").exists()

    def test_invalid_steps(self, tmp_path: Path):
        script = _write(tmp_path, "steps:\n  - key: f1\n")
        result = CliRunner().invoke(cli, ["termshow", "record", "--steps", str(script)])
        assert result.exit_code == 1
        assert "steps[0].key: must be a key" in result.output

    def test_output_required_without_steps(self):
        result = CliRunner().invoke(cli, ["termshow", "record"])
        assert result.exit_code == 2
        assert "Missing argument 'OUTPUT'" in result.output


class TestValidateCommand:
    def test_script_not_recorded_yet(self, tmp_path: Path):
        script = _write(tmp_path, "steps:\n  - run: ls\n")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(script)])
        assert result.exit_code == 0, result.output
        assert f"✓ {script} (not recorded yet): no problems" in result.output

    def test_script_not_recorded_yet_with_errors(self, tmp_path: Path):
        script = _write(tmp_path, "steps:\n  - run: ls\n    count: 2\n")
        result = CliRunner().invoke(cli, ["termshow", "validate", str(script)])
        assert result.exit_code == 1
        assert "steps[0].count: goes with 'key', not 'run'" in result.output
