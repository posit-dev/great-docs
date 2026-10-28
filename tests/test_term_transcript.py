"""Tests for transcripts (`great-docs termshow transcript`, and the shortcode's hidden text)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from great_docs._term_player.parser import parse_termshow_str
from great_docs._term_player.script import _parse_script_data
from great_docs._term_player.transcript import (
    TRANSCRIPT_FILE,
    transcript_markdown,
    transcript_vtt,
    write_transcript,
)
from great_docs.cli import cli
from great_docs.core import GreatDocs

_EXTENSIONS = Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions"

# Delays are relative to the previous event: output at 0s, 1s, 2s and 4s
EVENTS = [
    [0.0, "o", "$ "],
    [1.0, "o", "one\r\n$ "],
    [1.0, "o", "two\r\n$ "],
    [2.0, "o", "three\r\n$ "],
]


def _recording(events=EVENTS, *, cols: int = 30, rows: int = 5):
    header = {"version": 1, "format": "termshow", "term": {"cols": cols, "rows": rows}}
    return parse_termshow_str("\n".join([json.dumps(header)] + [json.dumps(e) for e in events]))


def _md(events=EVENTS, script: dict | None = None, **term) -> str:
    script_obj = _parse_script_data(script) if script is not None else None
    return transcript_markdown(_recording(events, **term), script_obj)


def _code(md: str) -> list[str]:
    """The text of each console block."""
    return re.findall(r"```console\n(.*?)\n```", md, re.DOTALL)


def _write(tmp_path: Path, script: str | None = None) -> Path:
    source = tmp_path / "demo.termshow"
    header = {"version": 1, "format": "termshow", "term": {"cols": 30, "rows": 5}}
    source.write_text(
        "\n".join([json.dumps(header)] + [json.dumps(e) for e in EVENTS]), encoding="utf-8"
    )
    if script is not None:
        (tmp_path / "demo.termshow.yml").write_text(script, encoding="utf-8")
    return source


class TestText:
    def test_plain_text(self):
        assert _md() == "```console\n$ one\n$ two\n$ three\n```\n"

    def test_colors_and_escape_codes_are_removed(self):
        events = [[0, "o", "\x1b[1;32m$\x1b[0m \x1b]0;title\x07ls\r\n\x1b[34mdocs\x1b[0m  src\r\n"]]
        assert _code(_md(events)) == ["$ ls\ndocs  src"]

    def test_lines_that_scroll_away_are_kept(self):
        events = [[0, "o", "".join(f"line {i}\r\n" for i in range(12))]]
        assert _code(_md(events, rows=3)) == ["\n".join(f"line {i}" for i in range(12))]

    def test_cleared_screens_are_kept(self):
        events = [
            [0, "o", "first\r\n"],
            [1, "o", "\x1b[H\x1b[2Jsecond\r\n"],
            [1, "o", "\x1b[H\x1b[Jthird\r\n"],
        ]
        assert _code(_md(events)) == ["first\nsecond\nthird"]

    def test_full_screen_program_keeps_its_last_screen(self):
        events = [
            [0, "o", "$ less notes.txt\r\n"],
            [1, "o", "\x1b[?1049hpage one"],
            [1, "o", "\x1b[2J\x1b[Hpage two"],
            [1, "o", "\x1b[2J\x1b[?1049l$ done\r\n"],
        ]
        assert _code(_md(events)) == ["$ less notes.txt", "page two", "$ done"]

    def test_full_screen_program_still_running_at_the_end(self):
        events = [[0, "o", "$ top\r\n"], [1, "o", "\x1b[?1049hPID 1"]]
        assert _code(_md(events)) == ["$ top", "PID 1"]

    def test_idle_prompt_at_the_end_is_left_out(self):
        assert not _md().rstrip().endswith("$\n```")
        # Text after the cursor's line isn't a bare prompt
        assert _code(_md([[0, "o", "done"]])) == ["done"]

    def test_backticks_get_a_longer_fence(self):
        md = _md([[0, "o", "```\r\n"]])
        assert md == "````console\n```\n````\n"

    def test_nothing_shown(self):
        assert _md([]) == ""
        assert _md([[0, "o", "\r\n\r\n"]]) == ""


class TestScript:
    def test_chapters_split_the_text(self):
        md = _md(script={"chapters": [{"at": 0, "label": "Start"}, {"at": 2, "label": "More"}]})
        assert (
            md
            == "**Start**\n\n```console\n$ one\n```\n\n**More**\n\n```console\n$ two\n$ three\n```\n"
        )

    def test_markers_are_chapters_without_a_script(self):
        events = EVENTS[:2] + [[0.5, "m", "Second part"]] + EVENTS[2:]
        md = _md(events)
        assert md.index("$ one") < md.index("**Second part**") < md.index("$ two")

    def test_redrawn_text_is_not_split(self):
        # A menu redraws its first item in place after the chapter starts
        events = [
            [0, "o", "> New\r\n  Open\r\n  Quit\r\n"],
            [1, "o", "\x1b[1;1H  New\x1b[2;1H> Open"],
        ]
        md = _md(events, script={"chapters": [{"at": 0.5, "label": "Move"}]})
        assert md == "```console\n  New\n> Open\n  Quit\n```\n\n**Move**\n"

    def test_script_chapters_replace_markers(self):
        events = EVENTS[:2] + [[0.5, "m", "Marker"]] + EVENTS[2:]
        md = _md(events, script={"chapters": [{"at": 0, "label": "Chapter"}]})
        assert "Marker" not in md and md.startswith("**Chapter**")

    def test_annotations_are_notes_where_they_show(self):
        script = {"annotations": [{"at": 1, "duration": 1, "text": "Look at one"}]}
        md = _md(script=script)
        # Shown at 1s, after the output at 1s
        assert md == "```console\n$ one\n```\n\n> Look at one\n\n```console\n$ two\n$ three\n```\n"

    def test_annotation_after_the_end(self):
        md = _md(script={"annotations": [{"at": 30, "duration": 1, "text": "Bye"}]})
        assert md.endswith("```\n\n> Bye\n")

    def test_markdown_in_labels_and_notes_is_shown_as_text(self):
        script = {
            "chapters": [{"at": 0, "label": "Run *all* the `tests`"}],
            "annotations": [{"at": 1, "duration": 1, "text": "# not a heading\n<b>"}],
        }
        md = _md(script=script)
        assert "**Run \\*all\\* the \\`tests\\`**" in md
        assert "> \\# not a heading\n> \\<b\\>" in md

    def test_cuts_place_chapters_on_the_playback_timeline(self):
        chapters = [{"at": 3.5, "label": "Later"}]
        # Without the cut, 3.5s comes before "three" (at 4s)
        assert _md(script={"chapters": chapters}).index("**Later**") < _md().index("three") + 20
        # The cut takes out 2s to 3s, so "three" is at 3s and the chapter comes after it
        md = _md(script={"chapters": chapters, "cuts": [{"from": 2, "to": 3}]})
        assert md.endswith("$ three\n```\n\n**Later**\n")
        assert _code(md) == ["$ one\n$ two\n$ three"]

    def test_prompt_replacement(self):
        events = [
            [0, "o", "$ "],
            [0.5, "i", "ls\r"],
            [0, "o", "ls\r\na  b\r\n$ "],
            [0.5, "i", "pwd\r"],
            [0, "o", "pwd\r\n/home\r\n$ "],
        ]
        md = _md(events, script={"settings": {"prompt": "❯"}})
        assert _code(md) == ["❯ ls\na  b\n❯ pwd\n/home"]

    def test_prompt_pattern_without_input_events(self):
        events = [[0, "o", "% ls\r\na\r\n% "]]
        md = _md(events, script={"settings": {"prompt": ">", "prompt_pattern": r"^% "}})
        assert _code(md) == ["> ls\na"]


class TestVtt:
    def test_annotations_are_captions(self):
        script = _parse_script_data(
            {
                "annotations": [
                    {"at": 61.5, "duration": 2, "text": "Second <b> & co"},
                    {"at": 1, "duration": 2.25, "text": "First\n\nline two"},
                ]
            }
        )
        assert transcript_vtt(_recording(), script) == (
            "WEBVTT\n\n"
            "1\n00:00:01.000 --> 00:00:03.250\nFirst\nline two\n\n"
            "2\n00:01:01.500 --> 00:01:03.500\nSecond &lt;b&gt; &amp; co\n"
        )

    def test_chapters_track(self):
        script = _parse_script_data(
            {"chapters": [{"at": 1, "label": "Two"}, {"at": 0, "label": "One"}]}
        )
        assert transcript_vtt(_recording(), script, chapters=True) == (
            "WEBVTT\n\n"
            "1\n00:00:00.000 --> 00:00:01.000\nOne\n\n"
            "2\n00:00:01.000 --> 00:00:04.000\nTwo\n"
        )

    def test_chapters_from_markers_on_the_playback_timeline(self):
        events = EVENTS[:2] + [[0.5, "m", "Mid"]] + EVENTS[2:]
        script = _parse_script_data({"settings": {"speed": 2}})
        vtt = transcript_vtt(_recording(events), script, chapters=True)
        # The marker is at 1.5s and the recording ends at 4.5s
        assert "00:00:00.750 --> 00:00:02.250\nMid" in vtt

    def test_nothing_to_caption(self):
        assert transcript_vtt(_recording()) == "WEBVTT\n"
        # A chapter at the very end has no length, so it has no cue
        script = _parse_script_data({"chapters": [{"at": 4, "label": "End"}]})
        assert transcript_vtt(_recording(), script, chapters=True) == "WEBVTT\n"


class TestWrite:
    def test_written_and_removed(self, tmp_path):
        assert write_transcript(_recording(), None, tmp_path / "out")
        path = tmp_path / "out" / TRANSCRIPT_FILE
        assert "$ three" in path.read_text(encoding="utf-8")
        assert not write_transcript(_recording([]), None, tmp_path / "out")
        assert not path.exists()

    def test_render_writes_it(self, tmp_path):
        source = _write(tmp_path, "chapters:\n  - at: 0\n    label: Start\n")
        out = tmp_path / "out"
        result = CliRunner().invoke(cli, ["termshow", "render", str(source), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert (out / TRANSCRIPT_FILE).read_text(encoding="utf-8").startswith("**Start**")

    def test_build_writes_it_with_the_raw_recording_and_script(self, tmp_path):
        source_dir = tmp_path / "docs"
        (source_dir / "demos").mkdir(parents=True)
        _write(
            source_dir / "demos", "settings:\n  speed: 2\nchapters:\n  - at: 1.5\n    label: B\n"
        )
        added = []
        fake = SimpleNamespace(
            layout=SimpleNamespace(source_dir=source_dir),
            build_dir=tmp_path / "build",
            _add_project_resources=lambda res, excl: added.append(res),
        )
        log = SimpleNamespace(detail=lambda msg: None, warn=pytest.fail)
        GreatDocs._prerender_term_player(fake, log)
        out = tmp_path / "build" / "termshow" / "demos" / "demo"
        assert (out / "manifest.json").exists()
        # At double speed, 1.5s of playback is 3s of the recording: before "three"
        md = (out / TRANSCRIPT_FILE).read_text(encoding="utf-8")
        assert md.index("$ two") < md.index("**B**") < md.index("$ three")
        assert added == [["termshow/**"]]


class TestCli:
    def test_prints_markdown(self, tmp_path):
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(_write(tmp_path))])
        assert result.exit_code == 0, result.output
        assert result.stdout == "```console\n$ one\n$ two\n$ three\n```\n"

    def test_output_file(self, tmp_path):
        source = _write(tmp_path)
        out = tmp_path / "sub" / "t.md"
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(source), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert "$ three" in out.read_text(encoding="utf-8")
        assert f"Wrote {out}" in result.output

    def test_script_and_no_script(self, tmp_path):
        source = _write(tmp_path, "chapters:\n  - at: 0\n    label: Start\n")
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(source)])
        assert result.stdout.startswith("**Start**")
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(source), "--no-script"])
        assert "Start" not in result.stdout

    def test_vtt(self, tmp_path):
        source = _write(
            tmp_path,
            "chapters:\n  - at: 0\n    label: Start\n"
            "annotations:\n  - at: 1\n    duration: 1\n    text: Hi\n",
        )
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(source), "--vtt"])
        assert result.stdout == "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\nHi\n"
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(source), "--vtt-chapters"])
        assert result.stdout == "WEBVTT\n\n1\n00:00:00.000 --> 00:00:04.000\nStart\n"

    @pytest.mark.parametrize(
        "args, message",
        [
            (["--vtt"], "The recording has no annotations."),
            (["--vtt-chapters"], "The recording has no chapters."),
        ],
    )
    def test_nothing_to_write_is_reported(self, tmp_path, args, message):
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(_write(tmp_path)), *args])
        assert result.exit_code == 0
        assert message in result.stderr and message not in result.stdout

    def test_wont_overwrite_the_recording(self, tmp_path):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "transcript", str(source), "-o", str(source)])
        assert result.exit_code == 2
        assert "is the recording itself" in result.output


# ---------------------------------------------------------------------------
# The shortcode and the page's Markdown version, in a Quarto render
# ---------------------------------------------------------------------------

_QUARTO_YML = """\
project:
  type: website
filters:
  - markdown-pages
website:
  title: Site
"""


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("quarto") is None:
        pytest.skip("Quarto is not installed")
    root = tmp_path_factory.mktemp("site")
    for name in ("termshow", "markdown-pages"):
        shutil.copytree(_EXTENSIONS / name, root / "_extensions" / name)
    (root / "_quarto.yml").write_text(_QUARTO_YML, encoding="utf-8")
    script = "chapters:\n  - at: 0\n    label: Start <here>\n"
    source = _write(root, script)
    for name in ("demo", "silent"):
        result = CliRunner().invoke(
            cli, ["termshow", "render", str(source), "-o", str(root / "termshow" / name)]
        )
        assert result.exit_code == 0, result.output
    # A recording rendered before transcripts existed
    (root / "termshow" / "silent" / TRANSCRIPT_FILE).unlink()
    (root / "index.qmd").write_text(
        '---\ntitle: Demo\n---\n\nBefore.\n\n{{< termshow file="demo" >}}\n\nAfter.\n',
        encoding="utf-8",
    )
    (root / "old.qmd").write_text(
        '---\ntitle: Old\n---\n\n{{< termshow file="silent" >}}\n', encoding="utf-8"
    )
    subprocess.run(["quarto", "render"], cwd=root, check=True, capture_output=True)
    return root / "_site"


def test_transcript_follows_the_player(site: Path):
    page = (site / "index.html").read_text(encoding="utf-8")
    player = page.index('<div class="gd-termshow"')
    transcript = page.index('<div class="gd-termshow-transcript"')
    # After the player's element, which the player empties when it starts
    assert page.index("</div>", player) < transcript
    assert 'aria-labelledby="gd-termshow-transcript-1"' in page
    assert "<p><strong>Start &lt;here&gt;</strong></p>" in page
    assert '<pre><code class="language-console">$ one\n$ two\n$ three</code></pre>' in page


def test_transcript_is_not_a_page(site: Path):
    assert not list(site.rglob("*transcript*.html"))


def test_markdown_version_has_the_transcript(site: Path):
    md = (site / "index.md").read_text(encoding="utf-8")
    assert "Transcript of the terminal recording: demo\n\n**Start \\<here\\>**" in md
    assert re.search(r"``` ?console\n\$ one\n\$ two\n\$ three\n```", md)
    assert md.index("Before.") < md.index("$ one") < md.index("After.")
    # The poster and the no-JavaScript message give way to the transcript
    assert "frame-000.svg" not in md and "requires JavaScript" not in md


def test_without_a_transcript_the_player_is_unchanged(site: Path):
    assert "gd-termshow-transcript" not in (site / "old.html").read_text(encoding="utf-8")
    md = (site / "old.md").read_text(encoding="utf-8")
    assert "frame-000.svg" in md and "Transcript" not in md
