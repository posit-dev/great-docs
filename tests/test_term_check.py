"""Tests for drift detection (`termshow check`)."""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player.check import (
    MASK,
    CheckError,
    check_script,
    compare,
    mask,
    snapshots,
)
from great_docs._term_player.editor import _kept_sections
from great_docs._term_player.parser import Event, Recording, TermInfo, parse_termshow
from great_docs._term_player.validate import check_script_data
from great_docs.cli import cli

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX pseudo-terminal")


def _recording(*events: tuple[str, str], cols: int = 20, rows: int = 4) -> Recording:
    return Recording(
        term=TermInfo(cols=cols, rows=rows),
        events=[Event(i * 0.1, code, data) for i, (code, data) in enumerate(events)],
    )


# ---------------------------------------------------------------------------
# Comparing screens
# ---------------------------------------------------------------------------


class TestSnapshots:
    def test_markers_and_end(self):
        recording = _recording(
            ("o", "$ "),
            ("m", "One"),
            ("o", "ls\r\nfile\r\n$ "),
            ("m", "Two"),
            ("o", "x"),
        )
        assert [(s.where, s.text) for s in snapshots(recording)] == [
            ("marker 'One'", "$"),
            ("marker 'Two'", "$ ls\nfile\n$"),
            ("the end", "$ ls\nfile\n$ x"),
        ]

    def test_only_the_visible_screen(self):
        output = "".join(f"line {i}\r\n" for i in range(6))
        assert snapshots(_recording(("o", output)))[-1].text == "line 3\nline 4\nline 5"

    def test_resize(self):
        recording = _recording(("r", "10x2"), ("o", "a" * 12), cols=20, rows=4)
        assert snapshots(recording)[-1].text == "aaaaaaaaaa\naa"


class TestMask:
    def test_each_row(self):
        patterns = [re.compile(r"v\d+\.\d+"), re.compile(r"/tmp/\S+")]
        text = "tool v1.2 in /tmp/abc\nv3.4"
        assert mask(text, patterns) == f"tool {MASK} in {MASK}\n{MASK}"

    def test_patterns_dont_span_rows(self):
        assert mask("a\nb", [re.compile(r"a\sb")]) == "a\nb"

    def test_no_patterns(self):
        assert mask("text", []) == "text"


class TestCompare:
    def test_same_screens(self):
        a = _recording(("o", "$ "), ("m", "One"), ("o", "hi"))
        # Different timing and chunking, same screens
        b = _recording(("o", "$"), ("o", " "), ("m", "One"), ("o", "h"), ("o", "i"))
        assert compare(a, b, []) == ([], 2)

    def test_difference(self):
        old = _recording(("o", "$ ls\r\nold\r\n$ "))
        new = _recording(("o", "$ ls\r\nnew\r\n$ "))
        differences, count = compare(old, new, [], name="demo.termshow")
        assert count == 1
        assert [d.where for d in differences] == ["the end"]
        assert differences[0].lines == [
            "--- demo.termshow, at the end",
            "+++ the steps now, at the end",
            "@@ -1,3 +1,3 @@",
            " $ ls",
            "-old",
            "+new",
            " $",
        ]

    def test_reports_the_marker(self):
        old = _recording(("o", "a"), ("m", "One"), ("o", "b"))
        new = _recording(("o", "z"), ("m", "One"), ("o", "b"))
        differences, _ = compare(old, new, [])
        assert [d.where for d in differences] == ["marker 'One'", "the end"]

    def test_ignored_text(self):
        old = _recording(("o", "built in 1.2s"))
        new = _recording(("o", "built in 3.4s"))
        assert compare(old, new, [re.compile(r"[\d.]+s")]) == ([], 1)

    def test_different_markers(self):
        old = _recording(("m", "One"), ("o", "a"))
        new = _recording(("m", "One"), ("m", "Two"), ("o", "a"))
        differences, count = compare(old, new, [], name="demo.termshow")
        assert count == 1
        assert [(d.where, d.lines) for d in differences] == [
            (
                "markers",
                ["demo.termshow has markers 'One', and the steps now give markers 'One', 'Two'"],
            )
        ]

    def test_no_markers(self):
        differences, _ = compare(_recording(("o", "a")), _recording(("m", "X"), ("o", "a")), [])
        assert "has no markers" in differences[0].lines[0]


# ---------------------------------------------------------------------------
# The `check` section
# ---------------------------------------------------------------------------


class TestCheckSection:
    def _errors(self, check) -> list[str]:
        problems = []
        check_script_data({"check": check}, "demo.termshow.yml", problems)
        return [str(p).split(": ", 1)[1] for p in problems]

    def test_valid(self):
        assert self._errors({"ignore": [r"v\d+", "/tmp/.*"]}) == []

    @pytest.mark.parametrize(
        ("check", "message"),
        [
            ({"ignor": []}, "check: unknown key 'ignor' (did you mean 'ignore'?)"),
            ({"ignore": "x"}, "check.ignore: must be a list, got 'x'"),
            ({"ignore": [""]}, "check.ignore[0]: can't be empty"),
            ({"ignore": ["ok", "("]}, "check.ignore[1]: isn't a valid regular expression"),
            (3, "check: must be a mapping, got 3"),
        ],
    )
    def test_mistakes(self, check, message: str):
        assert any(e.startswith(message) for e in self._errors(check))

    def test_editor_keeps_it(self):
        text = "chapters: []\ncheck:\n  ignore:\n    - 'v\\d+'\n"
        assert _kept_sections(text) == "check:\n  ignore:\n    - 'v\\d+'\n\n"


# ---------------------------------------------------------------------------
# Running a check
# ---------------------------------------------------------------------------

_SCRIPT = """\
record:
  typing_delay: 0
  typing_jitter: 0
steps:
  - marker: Greeting
  - run: echo "hello $(cat name.txt)"
  - marker: Version
  - run: echo "version $(cat version.txt)"
"""


def _project(tmp_path: Path, name: str = "world", version: str = "1.0") -> Path:
    (tmp_path / "name.txt").write_text(name + "\n", encoding="utf-8")
    (tmp_path / "version.txt").write_text(version + "\n", encoding="utf-8")
    script = tmp_path / "demo.termshow.yml"
    if not script.exists():
        script.write_text(_SCRIPT, encoding="utf-8")
    return script


def _record(script: Path) -> None:
    result = CliRunner().invoke(cli, ["termshow", "record", "--steps", str(script)])
    assert result.exit_code == 0, result.output


@posix_only
class TestCheckScript:
    def test_up_to_date(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        result = check_script(script)
        assert not result.drifted
        assert result.snapshots == 3
        assert result.recording_path == tmp_path / "demo.termshow"

    def test_drifted(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        _project(tmp_path, name="there")
        result = check_script(script)
        assert [d.where for d in result.differences] == ["marker 'Version'", "the end"]
        assert "+hello there" in result.differences[0].lines

    def test_ignore_from_script_and_caller(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        _project(tmp_path, name="there", version="2.0")
        script.write_text(_SCRIPT + "check:\n  ignore:\n    - 'version \\d.*'\n", encoding="utf-8")
        assert check_script(script).differences[0].where == "marker 'Version'"
        assert not check_script(script, ignore=["hello .*"]).drifted

    def test_uses_the_recordings_size(self, tmp_path: Path):
        script = _project(tmp_path)
        result = CliRunner().invoke(
            cli, ["termshow", "record", "--steps", str(script), "--cols", "40", "--rows", "8"]
        )
        assert result.exit_code == 0, result.output
        result = check_script(script)
        assert not result.drifted
        assert (result.recording.term.cols, result.recording.term.rows) == (40, 8)

    def test_not_recorded_yet(self, tmp_path: Path):
        script = _project(tmp_path)
        with pytest.raises(CheckError, match="doesn't exist yet. Record it with"):
            check_script(script)

    def test_not_a_script_name(self, tmp_path: Path):
        path = tmp_path / "steps.yml"
        path.write_text(_SCRIPT, encoding="utf-8")
        with pytest.raises(CheckError, match="isn't named NAME.termshow.yml"):
            check_script(path)

    def test_mistake_in_check_section(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        script.write_text(_SCRIPT + "check:\n  ignore: ['(']\n", encoding="utf-8")
        with pytest.raises(CheckError, match=r"check.ignore\[0\]"):
            check_script(script)


@posix_only
class TestCheckCommand:
    def test_up_to_date(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        result = CliRunner().invoke(cli, ["termshow", "check", str(script)])
        assert result.exit_code == 0, result.output
        assert f"✓ {tmp_path / 'demo.termshow'} is up to date (3 screens compared)" in (
            result.output
        )

    def test_drifted(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        _project(tmp_path, name="there")
        result = CliRunner().invoke(cli, ["termshow", "check", str(script)])
        assert result.exit_code == 1
        assert "has drifted:" in result.output
        assert "  -hello world" in result.output
        assert "  +hello there" in result.output

    def test_recording_path_and_ignore_option(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        _project(tmp_path, name="there")
        recording = tmp_path / "demo.termshow"
        result = CliRunner().invoke(
            cli, ["termshow", "check", str(recording), "--ignore", "hello .*"]
        )
        assert result.exit_code == 0, result.output

    def test_update(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        _project(tmp_path, name="there")
        result = CliRunner().invoke(cli, ["termshow", "check", str(script), "--update"])
        assert result.exit_code == 0, result.output
        assert f"↻ Recorded {tmp_path / 'demo.termshow'} again" in result.output
        recording = parse_termshow(tmp_path / "demo.termshow")
        assert "hello there" in "".join(e.data for e in recording.events)
        assert CliRunner().invoke(cli, ["termshow", "check", str(script)]).exit_code == 0

    def test_several_scripts(self, tmp_path: Path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        good, bad = _project(tmp_path / "a"), _project(tmp_path / "b")
        _record(good)
        _record(bad)
        _project(tmp_path / "b", name="there")
        missing = tmp_path / "c.termshow.yml"
        missing.write_text(_SCRIPT, encoding="utf-8")
        result = CliRunner().invoke(cli, ["termshow", "check", str(good), str(bad), str(missing)])
        assert result.exit_code == 1
        assert "1 of 3 up to date, 1 drifted, 1 couldn't be checked" in result.output

    def test_failed_step(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        script.write_text(_SCRIPT + "  - wait_for: never\n    timeout: 0.3\n", encoding="utf-8")
        result = CliRunner().invoke(cli, ["termshow", "check", str(script)])
        assert result.exit_code == 1
        assert "steps[4] (wait_for: never): 'never' didn't appear" in result.output
        assert '  │ $ echo "version $(cat version.txt)"' in result.output

    def test_bad_ignore_option(self, tmp_path: Path):
        script = _project(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "check", str(script), "--ignore", "("])
        assert result.exit_code == 2
        assert "isn't a valid regular expression" in result.output


def _check_json(*args: str) -> tuple[int, dict]:
    result = CliRunner().invoke(cli, ["termshow", "check", "--json", *args])
    # Progress goes to stderr, so stdout is only the JSON
    return result.exit_code, json.loads(result.stdout)


@posix_only
class TestCheckJson:
    def test_up_to_date(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        code, data = _check_json(str(script))
        assert code == 0
        assert data == {
            "version": 1,
            "summary": {"up_to_date": 1, "drifted": 0, "updated": 0, "failed": 0},
            "results": [
                {
                    "script": script.as_posix(),
                    "recording": (tmp_path / "demo.termshow").as_posix(),
                    "status": "up_to_date",
                    "compared": 3,
                    "differences": [],
                }
            ],
        }

    def test_drifted(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        _project(tmp_path, name="there")
        code, data = _check_json(str(script))
        assert code == 1
        assert data["summary"]["drifted"] == 1
        (result,) = data["results"]
        assert result["status"] == "drifted"
        assert [d["at"] for d in result["differences"]] == ["marker 'Version'", "the end"]
        assert "+hello there" in result["differences"][0]["diff"]

    def test_updated(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        _project(tmp_path, name="there")
        code, data = _check_json(str(script), "--update")
        assert code == 0
        assert data["summary"] == {"up_to_date": 0, "drifted": 0, "updated": 1, "failed": 0}
        assert data["results"][0]["differences"]
        assert check_script(script).drifted is False

    def test_failed(self, tmp_path: Path):
        missing = _project(tmp_path)
        code, data = _check_json(str(missing))
        assert code == 1
        (result,) = data["results"]
        assert result["status"] == "failed"
        assert result["recording"] is None
        assert "doesn't exist yet" in result["error"]
        assert "screen" not in result

    def test_failed_step_has_the_screen(self, tmp_path: Path):
        script = _project(tmp_path)
        _record(script)
        script.write_text(_SCRIPT + "  - wait_for: never\n    timeout: 0.3\n", encoding="utf-8")
        code, data = _check_json(str(script))
        assert code == 1
        assert "'never' didn't appear" in data["results"][0]["error"]
        assert 'echo "version $(cat version.txt)"' in data["results"][0]["screen"]

    def test_several_scripts(self, tmp_path: Path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        good, bad = _project(tmp_path / "a"), _project(tmp_path / "b")
        _record(good)
        _record(bad)
        _project(tmp_path / "b", name="there")
        code, data = _check_json(str(good), str(bad))
        assert code == 1
        assert data["summary"] == {"up_to_date": 1, "drifted": 1, "updated": 0, "failed": 0}
        assert [r["status"] for r in data["results"]] == ["up_to_date", "drifted"]


# ---------------------------------------------------------------------------
# The CI recipe in the guide
# ---------------------------------------------------------------------------

_GUIDE = Path(__file__).resolve().parents[1] / "docs/user_guide/41-terminal-recordings.qmd"


def _guide_block(opening: str) -> str:
    text = _GUIDE.read_text(encoding="utf-8")
    return re.search(re.escape(opening) + r"\n(.*?)^```", text, re.S | re.M)[1]


class TestGuideWorkflow:
    def _workflow(self) -> dict:
        from yaml12 import parse_yaml

        return parse_yaml(_guide_block('```{.yaml filename=".github/workflows/demos.yml"}'))

    def _commands(self) -> list[list[str]]:
        commands = []
        for job in self._workflow()["jobs"].values():
            for step in job["steps"]:
                for line in step.get("run", "").splitlines():
                    words = shlex.split(line.strip())
                    if words[:1] == ["great-docs"]:
                        commands.append(words[1:])
        return commands

    def test_jobs(self):
        workflow = self._workflow()
        assert set(workflow["on"]) == {"pull_request", "schedule", "workflow_dispatch"}
        assert set(workflow["jobs"]) == {"check", "update"}
        assert workflow["jobs"]["update"]["permissions"] == {
            "contents": "write",
            "pull-requests": "write",
        }

    def test_commands_exist(self):
        commands = self._commands()
        assert [c[:2] for c in commands] == [
            ["termshow", "check"],
            ["termshow", "check"],
            ["termshow", "export"],
        ]
        assert "--update" in commands[1]
        for words in commands:
            group = cli.commands[words[0]]
            command = group.commands[words[1]]
            options = {o for p in command.params for o in getattr(p, "opts", [])}
            for word in words[2:]:
                if word.startswith("-"):
                    assert word in options, f"{' '.join(words)}: no option {word}"

    def test_actionlint(self, tmp_path: Path):
        actionlint = shutil.which("actionlint")
        if actionlint is None:
            pytest.skip("actionlint isn't installed")
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        workflow = workflows / "demos.yml"
        workflow.write_text(
            _guide_block('```{.yaml filename=".github/workflows/demos.yml"}'), encoding="utf-8"
        )
        result = subprocess.run(
            [actionlint, str(workflow)], cwd=tmp_path, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr


@posix_only
def test_guide_json_example_matches(tmp_path: Path):
    text = _GUIDE.read_text(encoding="utf-8")
    blocks = re.findall(r"^```json\n(.*?)^```", text, re.S | re.M)
    (example,) = [json.loads(b) for b in blocks if '"summary"' in b]
    script = _project(tmp_path)
    _record(script)
    _project(tmp_path, name="there")
    _, data = _check_json(str(script))
    assert set(example) == set(data)
    assert set(example["summary"]) == set(data["summary"])
    assert set(example["results"][0]) == set(data["results"][0])
    assert set(example["results"][0]["differences"][0]) == set(data["results"][0]["differences"][0])
