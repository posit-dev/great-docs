from __future__ import annotations

import io
import json
from pathlib import Path

from great_docs._build import passes
from great_docs._build.log import BuildLog
from great_docs._contribution import Contribution
from great_docs._term_player.prerender import (
    Prerendered,
    load_recording,
    render_recording,
    render_recordings,
)
from great_docs._term_player.transcript import TRANSCRIPT_FILE
from great_docs._website import quarto_yml
from great_docs.core import GreatDocs

# Delays are relative to the previous event: output at 0s, 1s, 2s and 4s
EVENTS = [
    [0.0, "o", "$ "],
    [1.0, "o", "one\r\n$ "],
    [1.0, "o", "two\r\n$ "],
    [2.0, "o", "three\r\n$ "],
]


def _write(directory: Path, name: str = "demo", script: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / f"{name}.termshow"
    header = {"version": 1, "format": "termshow", "term": {"cols": 30, "rows": 5}}
    source.write_text(
        "\n".join([json.dumps(header)] + [json.dumps(e) for e in EVENTS]), encoding="utf-8"
    )
    if script is not None:
        (directory / f"{name}.termshow.yml").write_text(script, encoding="utf-8")
    return source


def test_transcript_has_the_raw_recording_and_the_script(tmp_path):
    source = _write(
        tmp_path, script="settings:\n  speed: 2\nchapters:\n  - at: 1.5\n    label: B\n"
    )
    recording, script = load_recording(source)
    render_recording(recording, script, tmp_path / "out")
    assert (tmp_path / "out" / "manifest.json").exists()
    # At double speed, 1.5s of playback is 3s of the recording: before "three"
    md = (tmp_path / "out" / TRANSCRIPT_FILE).read_text(encoding="utf-8")
    assert md.index("$ two") < md.index("**B**") < md.index("$ three")


def test_same_name_in_two_directories_renders_twice(tmp_path):
    source_dir = tmp_path / "docs"
    recordings = [_write(source_dir / "a"), _write(source_dir / "b")]
    done = render_recordings(recordings, source_dir, tmp_path / "build", report=print)
    assert done.count == 2
    for name in ("a", "b"):
        assert (tmp_path / "build" / "termshow" / name / "demo" / "manifest.json").exists()


def test_a_broken_recording_is_reported_and_the_rest_render(tmp_path):
    broken = tmp_path / "broken.termshow"
    broken.write_text("not json\n", encoding="utf-8")
    reported: list[str] = []
    done = render_recordings(
        [broken, _write(tmp_path)], tmp_path, tmp_path / "build", report=reported.append
    )
    assert done.count == 1
    assert len(reported) == 1
    assert reported[0].startswith("termshow: failed to render broken.termshow: ")


def test_build_step_registers_the_output_as_a_resource(tmp_path: Path):
    (tmp_path / "great-docs.yml").write_text("{}\n", encoding="utf-8")
    _write(tmp_path / "demos")
    docs = GreatDocs(project_path=str(tmp_path))
    stream = io.StringIO()
    passes.terminal_recordings(docs.layout, BuildLog(stream=stream))
    assert (docs.build_dir / "termshow" / "demos" / "demo" / "manifest.json").exists()
    assert quarto_yml.read(docs.build_dir)["project"]["resources"] == ["termshow/**"]
    assert "Pre-rendered 1 terminal recording(s)" in stream.getvalue()


def test_no_rendered_recording_contributes_nothing():
    assert Prerendered(count=0, manifest_bytes=0).contribution == Contribution()


def test_build_step_leaves_out_recordings_that_are_not_documentation(tmp_path):
    (tmp_path / "great-docs.yml").write_text("{}\n", encoding="utf-8")
    _write(tmp_path / "demos")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "pyvenv.cfg").write_text("", encoding="utf-8")
    for foreign in (".git", ".venv", "venv/lib", "node_modules/tool", "great-docs-v1/demos"):
        _write(tmp_path / foreign)
    docs = GreatDocs(project_path=str(tmp_path))
    passes.terminal_recordings(docs.layout, BuildLog(stream=io.StringIO()))
    rendered = docs.build_dir / "termshow"
    found = sorted(
        p.parent.relative_to(rendered).as_posix() for p in rendered.rglob("manifest.json")
    )
    assert found == ["demos/demo"]
