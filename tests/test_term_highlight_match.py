"""Tests for how the player places `match` highlight targets."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from great_docs._term_player import generate_manifest
from great_docs._term_player.parser import Event, Recording, TermInfo
from great_docs._term_player.script import Highlight, HighlightTarget, Script

ROOT = Path(__file__).resolve().parents[1]
_PLAYER_JS = ROOT / "great_docs" / "assets" / "_extensions" / "termshow" / "termshow.js"
_PUBLISHED_JS = ROOT / "extensions" / "termshow" / "_extensions" / "termshow" / "termshow.js"

# Runs the player with just enough of a DOM to load, then calls `locateMatch`
# for each [highlight index, time] query
_LOCATE_JS = r"""
const fs = require('fs');
const vm = require('vm');
const [playerPath, manifestPath, queriesJson] = process.argv.slice(1);
const window = { location: { protocol: 'https:' } };
const document = {
  readyState: 'complete',
  querySelectorAll: () => [],
  body: {},
  addEventListener: () => {},
};
class MutationObserver { observe() {} }
vm.runInNewContext(fs.readFileSync(playerPath, 'utf8'), { window, document, MutationObserver });
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const out = JSON.parse(queriesJson).map(
  ([i, t]) => window.Termshow.locateMatch(manifest, manifest.highlights[i], t)
);
process.stdout.write(JSON.stringify(out));
"""


def _recording() -> Recording:
    """A 4-row screen where an error line appears, then scrolls off the top."""
    return Recording(
        term=TermInfo(cols=30, rows=4),
        events=[
            Event(time=0.0, code="o", data="$ make\r\n"),
            Event(time=1.0, code="o", data="build ok\r\n"),
            Event(time=2.0, code="o", data="ERROR: disk full\r\n"),
            Event(time=3.0, code="o", data="a\r\n"),
            Event(time=4.0, code="o", data="b\r\n"),
            Event(time=5.0, code="o", data="c\r\n"),
            Event(time=6.0, code="o", data=""),
        ],
    )


HIGHLIGHTS = {
    "anchored": HighlightTarget(match=r"ERROR: (disk \w+)", group=1),
    "tracking": HighlightTarget(match=r"ERROR: (disk \w+)", group=1, track_scroll=True),
    "plain": HighlightTarget(match="build"),
    "group-after-repeat": HighlightTarget(match="o(k)", group=1),
    "invalid": HighlightTarget(match="(unclosed"),
    "absent": HighlightTarget(match="nowhere"),
}
NAMES = list(HIGHLIGHTS)


def _locate(tmp_path: Path, queries: list[tuple[str, float]], duration: float = 10.0) -> list:
    script = Script(
        highlights=[Highlight(time=0.0, duration=duration, target=t) for t in HIGHLIGHTS.values()]
    )
    generate_manifest(_recording(), script, output_dir=tmp_path)
    result = subprocess.run(
        [
            "node",
            "-e",
            _LOCATE_JS,
            str(_PLAYER_JS),
            str(tmp_path / "manifest.json"),
            json.dumps([[NAMES.index(name), t] for name, t in queries]),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def _cell(row: int, col: int, width: int) -> dict:
    return {"row": row, "col": col, "width": width, "height": 1}


def test_published_player_matches_bundled_copy():
    assert _PUBLISHED_JS.read_text(encoding="utf-8") == _PLAYER_JS.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
class TestLocateMatch:
    def test_plain_match(self, tmp_path: Path):
        assert _locate(tmp_path, [("plain", 1.5)]) == [_cell(1, 0, 5)]

    def test_group_columns(self, tmp_path: Path):
        # `group` covers only the captured text, wherever it sits in the match
        assert _locate(tmp_path, [("anchored", 2.5), ("group-after-repeat", 1.5)]) == [
            _cell(2, 7, 9),
            _cell(1, 7, 1),
        ]

    def test_hidden_until_text_appears(self, tmp_path: Path):
        assert _locate(tmp_path, [("anchored", 1.5), ("tracking", 1.5)]) == [None, None]

    def test_anchored_stays_where_text_first_appeared(self, tmp_path: Path):
        times = [2.5, 3.5, 4.5, 5.5]
        assert _locate(tmp_path, [("anchored", t) for t in times]) == [_cell(2, 7, 9)] * 4

    def test_track_scroll_follows_text_and_hides(self, tmp_path: Path):
        times = [2.5, 3.5, 4.5, 5.5]
        assert _locate(tmp_path, [("tracking", t) for t in times]) == [
            _cell(2, 7, 9),
            _cell(1, 7, 9),
            _cell(0, 7, 9),
            None,
        ]

    def test_anchor_only_searches_the_highlight_time_range(self, tmp_path: Path):
        # The error appears at 2.0, after this highlight has ended
        assert _locate(tmp_path, [("anchored", 2.5)], duration=1.5) == [None]

    def test_no_match_or_invalid_pattern(self, tmp_path: Path):
        assert _locate(tmp_path, [("invalid", 2.5), ("absent", 2.5)]) == [None, None]
