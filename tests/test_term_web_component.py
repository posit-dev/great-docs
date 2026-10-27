"""Tests for the `<termshow-player>` element and the `termshow assets` command."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player.web import PLAYER_DIR, PLAYER_FILES, copy_player, player_snippet
from great_docs.cli import cli

ROOT = Path(__file__).resolve().parents[1]
_PUBLISHED_DIR = ROOT / "extensions" / "termshow" / "_extensions" / "termshow"

# Loads the player with a stub DOM and a recording `customElements` registry,
# then runs the given expression against `window.Termshow` and `defined`
_RUN_JS = r"""
const fs = require('fs');
const vm = require('vm');
const [playerPath, expr] = process.argv.slice(1);
const defined = {};
const context = {
  window: { location: { protocol: 'https:' } },
  document: {
    readyState: 'complete',
    querySelectorAll: () => [],
    body: {},
    addEventListener: () => {},
  },
  MutationObserver: class { observe() {} },
  HTMLElement: class {},
  customElements: {
    get: (name) => defined[name],
    define: (name, cls) => { defined[name] = cls; },
  },
  defined,
};
vm.runInNewContext(fs.readFileSync(playerPath, 'utf8'), context);
const out = vm.runInNewContext(expr, Object.assign(context, { Termshow: context.window.Termshow }));
process.stdout.write(JSON.stringify(out));
"""


def _run(expr: str):
    result = subprocess.run(
        ["node", "-e", _RUN_JS, str(PLAYER_DIR / "termshow.js"), expr],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def _options(attrs: dict[str, str]):
    return _run(f"const a = {json.dumps(attrs)}; Termshow.readOptions((n) => n in a ? a[n] : null)")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
class TestElement:
    def test_defines_element_with_shortcode_attributes(self):
        assert _run("defined['termshow-player'].observedAttributes") == [
            "src",
            "autoplay",
            "loop",
            "speed",
            "pause-on-chapters",
            "poster",
            "controls",
            "theme",
        ]

    def test_defaults(self):
        assert _options({}) == {
            "autoplay": False,
            "speed": 1.0,
            "pauseOnChapters": False,
            "loop": False,
            "poster": 0,
            "controls": True,
            "theme": "auto",
        }

    def test_flags_are_on_when_present(self):
        # `<termshow-player autoplay loop>`, as well as the shortcode's "true"
        opts = _options({"autoplay": "", "loop": "true", "pause-on-chapters": "yes"})
        assert opts["autoplay"] and opts["loop"] and opts["pauseOnChapters"]

    def test_false_turns_flags_off(self):
        opts = _options({"autoplay": "false", "controls": "false"})
        assert not opts["autoplay"]
        assert not opts["controls"]

    def test_values(self):
        opts = _options({"speed": "1.5", "poster": "4.25", "theme": "light"})
        assert (opts["speed"], opts["poster"], opts["theme"]) == (1.5, 4.25, "light")

    @pytest.mark.parametrize(
        ("src", "url"),
        [
            ("termshow/demo", "termshow/demo/manifest.json"),
            ("termshow/demo/", "termshow/demo/manifest.json"),
            ("https://example.com/demo/manifest.json", "https://example.com/demo/manifest.json"),
            ("demo.termshow.json?v=2", "demo.termshow.json?v=2"),
            ("", None),
        ],
    )
    def test_manifest_url(self, src: str, url: str | None):
        assert _run(f"Termshow.manifestUrlFor({json.dumps(src)})") == url


class TestPlayerFiles:
    def test_copies_script_styles_and_fonts(self, tmp_path: Path):
        files = copy_player(tmp_path / "player")
        assert sorted(f.name for f in files) == sorted(PLAYER_FILES)
        for f in files:
            assert f.read_bytes() == (PLAYER_DIR / f.name).read_bytes()

    def test_every_font_the_stylesheet_loads_is_copied(self):
        css = (PLAYER_DIR / "termshow.css").read_text(encoding="utf-8")
        urls = set(re.findall(r"url\((?!\"?data:)\"?([^\")]+)\"?\)", css))
        assert urls and urls <= set(PLAYER_FILES)

    def test_styles_display_element_as_block(self):
        css = (PLAYER_DIR / "termshow.css").read_text(encoding="utf-8")
        assert re.search(r"termshow-player\s*\{\s*display:\s*block;", css)

    def test_published_copy_matches(self):
        for name in PLAYER_FILES:
            assert (_PUBLISHED_DIR / name).read_bytes() == (PLAYER_DIR / name).read_bytes(), name

    def test_snippet(self):
        assert player_snippet("player/", src="termshow/install") == (
            '<link rel="stylesheet" href="player/termshow.css">\n'
            '<script src="player/termshow.js"></script>\n'
            "\n"
            '<termshow-player src="termshow/install"></termshow-player>'
        )

    def test_cli(self, tmp_path: Path):
        dest = tmp_path / "site" / "player"
        result = CliRunner().invoke(cli, ["termshow", "assets", str(dest)])
        assert result.exit_code == 0, result.output
        assert sorted(p.name for p in dest.iterdir()) == sorted(PLAYER_FILES)
        assert f'<script src="{dest.as_posix()}/termshow.js"></script>' in result.output
        assert "<termshow-player" in result.output
