"""Tests for bundles: a recording in one `.termshow.json` file."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player.bundle import make_bundle
from great_docs._term_player.parser import parse_termshow_str
from great_docs._term_player.validate import check_manifest_text
from great_docs.cli import cli

_EXTENSIONS = Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions"

HEADER = {
    "version": 1,
    "format": "termshow",
    "term": {"cols": 30, "rows": 5},
    "title": "Demo",
}
EVENTS = [
    [0.0, "o", "$ "],
    [1.0, "o", "echo '</script>'\r\n</script>\r\n$ "],
    [1.0, "o", "two\r\n$ "],
]
SCRIPT = "chapters:\n  - at: 0\n    label: Start\n"


def _text(events=EVENTS) -> str:
    return "\n".join([json.dumps(HEADER)] + [json.dumps(e) for e in events])


def _write(root: Path, script: str | None = SCRIPT) -> Path:
    source = root / "demo.termshow"
    source.write_text(_text(), encoding="utf-8")
    if script is not None:
        (root / "demo.termshow.yml").write_text(script, encoding="utf-8")
    return source


def _bundle() -> dict:
    _, text = make_bundle(parse_termshow_str(_text()))
    return json.loads(text)


def _problems(data) -> list[str]:
    problems = []
    text = data if isinstance(data, str) else json.dumps(data)
    check_manifest_text(text, "x.termshow.json", problems)
    return [f"{p.where}: {p.message}" if p.where else p.message for p in problems]


class TestBundle:
    def test_keyframes_have_no_files(self):
        data = _bundle()
        assert data["version"] == 2
        assert data["keyframes"][0] == {"time": 0.0, "frame": 0}
        assert all("file" not in kf for kf in data["keyframes"])

    def test_has_the_transcript(self):
        data = _bundle()
        assert "```console\n$ echo '</script>'\n</script>\n$ two\n```" in data["transcript"]

    def test_is_safe_in_a_script_element(self):
        _, text = make_bundle(parse_termshow_str(_text()))
        assert "</" not in text
        assert "<\\/script>" in text

    def test_rendered_manifest_has_no_transcript(self, tmp_path: Path):
        source = _write(tmp_path)
        out = tmp_path / "out"
        result = CliRunner().invoke(cli, ["termshow", "render", str(source), "-o", str(out)])
        assert result.exit_code == 0, result.output
        data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert "transcript" not in data
        assert all("file" in kf for kf in data["keyframes"])


class TestExport:
    def test_default_name(self, tmp_path: Path):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "--bundle"])
        assert result.exit_code == 0, result.output
        out = tmp_path / "demo.termshow.json"
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["title"] == "Demo"
        assert data["chapters"] == [{"time": 0.0, "label": "Start"}]
        assert f"✓ Exported {out} (" in result.output
        assert "Duration: 2.0s | Unique screens: 3 | Unique rows: " in result.output
        assert 'Play it with <termshow-player src="demo.termshow.json"></termshow-player>' in (
            result.output
        )

    def test_output_name_picks_the_format(self, tmp_path: Path):
        source = _write(tmp_path)
        out = tmp_path / "x.termshow.json"
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert json.loads(out.read_text(encoding="utf-8"))["version"] == 2

    @pytest.mark.parametrize(
        "args, message",
        [
            (
                ["--bundle", "-o", "x.svg"],
                "--bundle writes a .termshow.json file, but -o ends in .svg",
            ),
            (["--svg", "-o", "x.termshow.json"], "--svg writes a .svg file, but -o ends in .json"),
            (["--bundle", "--fps", "10"], "--fps only applies to"),
            (["--bundle", "--no-loop"], "--no-loop only applies to"),
        ],
    )
    def test_mismatched_options(self, tmp_path: Path, args: list[str], message: str):
        source = _write(tmp_path)
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), *args])
        assert result.exit_code == 2
        assert message in result.output

    def test_validates(self, tmp_path: Path):
        source = _write(tmp_path)
        CliRunner().invoke(cli, ["termshow", "export", str(source), "--bundle"])
        out = tmp_path / "demo.termshow.json"
        result = CliRunner().invoke(cli, ["termshow", "validate", str(out)])
        assert result.exit_code == 0, result.output
        assert f"✓ {out}: no problems" in result.output


class TestValidate:
    def test_good_bundle(self):
        assert _problems(_bundle()) == []

    def test_not_json(self):
        problems = _problems("{")
        assert len(problems) == 1
        assert problems[0].startswith("isn't valid JSON")

    def test_missing_frame_and_row(self):
        data = _bundle()
        data["keyframes"][1]["frame"] = 99
        data["frames"][0]["lines"][0] = 999
        n_frames, n_lines = len(data["frames"]), len(data["lines"])
        assert _problems(data) == [
            f"keyframes[1].frame: there's no frame 99 (there are {n_frames} frames)",
            f"frames[0].lines[0]: there's no row 999 (there are {n_lines} rows)",
        ]

    def test_keyframe_times(self):
        data = _bundle()
        data["keyframes"][0]["time"] = 0.5
        data["keyframes"][2]["time"] = 0.1
        assert _problems(data) == [
            "keyframes[0].time: the first keyframe must be at 0 (got 0.5)",
            "keyframes[2].time: keyframes must be in time order",
        ]

    def test_version_2_keyframes_need_a_frame(self):
        data = _bundle()
        del data["keyframes"][0]["frame"]
        assert any("keyframes[0]" in p and "frame" in p for p in _problems(data))

    def test_version_1_keyframes_need_a_file(self):
        data = {
            "version": 1,
            "duration": 1.0,
            "cols": 30,
            "rows": 5,
            "keyframes": [{"time": 0.0}],
        }
        assert any("keyframes[0]" in p and "file" in p for p in _problems(data))

    def test_transcript_must_be_text(self):
        data = _bundle()
        data["transcript"] = 3
        assert any(p.startswith("transcript") for p in _problems(data))

    def test_errors_are_capped(self):
        data = _bundle()
        data["frames"][0]["lines"] = [999] * 30
        problems = _problems(data)
        assert len(problems) == 21
        assert problems[-1] == "10 more errors not shown"


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
    source = _write(root)
    (root / "demos").mkdir()
    (root / "guide").mkdir()
    for out in ("guide/demo.termshow.json", "demos/shared.termshow.json"):
        result = CliRunner().invoke(cli, ["termshow", "export", str(source), "-o", str(root / out)])
        assert result.exit_code == 0, result.output
    # Next to the page, and from the project root
    (root / "guide" / "index.qmd").write_text(
        '---\ntitle: Guide\n---\n\n{{< termshow file="demo.termshow.json" >}}\n\n'
        '{{< termshow file="demos/shared.termshow.json" >}}\n',
        encoding="utf-8",
    )
    (root / "index.qmd").write_text(
        '---\ntitle: Home\n---\n\n{{< termshow file="missing.termshow.json" >}}\n',
        encoding="utf-8",
    )
    result = subprocess.run(["quarto", "render"], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return root / "_site"


class TestShortcode:
    def test_inlines_the_bundle(self, site: Path):
        page = (site / "guide" / "index.html").read_text(encoding="utf-8")
        assert page.count('<div class="gd-termshow" data-autoplay=') == 2
        assert "data-manifest" not in page
        assert "gd-termshow-poster" not in page
        assert (
            page.count('<script type="application/json" class="gd-tp-manifest">{"version":2') == 2
        )
        start = page.index('class="gd-tp-manifest">') + len('class="gd-tp-manifest">')
        manifest = json.loads(page[start : page.index("</script>", start)])
        assert manifest["title"] == "Demo"

    def test_writes_the_transcript(self, site: Path):
        page = (site / "guide" / "index.html").read_text(encoding="utf-8")
        assert 'aria-labelledby="gd-termshow-transcript-2"' in page
        assert "Transcript of the terminal recording: demo</p>" in page
        assert "Transcript of the terminal recording: shared</p>" in page
        assert "<p><strong>Start</strong></p>" in page
        assert "$ echo '&lt;/script&gt;'\n&lt;/script&gt;\n$ two</code></pre>" in page

    def test_markdown_version_has_the_transcript(self, site: Path):
        md = (site / "guide" / "index.md").read_text(encoding="utf-8")
        assert "Transcript of the terminal recording: demo\n\n**Start**" in md
        assert "Transcript of the terminal recording: shared" in md

    def test_missing_bundle(self, site: Path):
        page = (site / "index.html").read_text(encoding="utf-8")
        assert "gd-tp-manifest" not in page
        assert "gd-termshow-transcript" not in page
