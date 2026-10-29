"""Tests for the `<termshow-player>` element and the `termshow assets` command."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs._term_player.parser import parse_termshow_str
from great_docs._term_player.script import _parse_script_data
from great_docs._term_player.transcript import transcript_markdown
from great_docs._term_player.web import PLAYER_DIR, PLAYER_FILES, copy_player, player_snippet
from great_docs.cli import cli

ROOT = Path(__file__).resolve().parents[1]
_PUBLISHED_DIR = ROOT / "extensions" / "termshow" / "_extensions" / "termshow"

# Loads the player with a stub DOM and a recording `customElements` registry,
# then runs the given expression against `window.Termshow` and `defined`. With
# "reduce" as the last argument, the reader prefers reduced motion.
_RUN_JS = r"""
const fs = require('fs');
const vm = require('vm');
const [playerPath, expr, motion] = process.argv.slice(1);
const defined = {};
const context = {
  window: {
    location: { protocol: 'https:' },
    matchMedia: (query) => ({
      matches: motion === 'reduce' && query.includes('prefers-reduced-motion'),
    }),
  },
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


def _run(expr: str, motion: str = "no-preference"):
    result = subprocess.run(
        ["node", "-e", _RUN_JS, str(PLAYER_DIR / "termshow.js"), expr, motion],
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


CHAPTERS = [{"time": 0, "label": "Start"}, {"time": 2, "label": "Build"}, {"time": 5, "label": ""}]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
class TestPlayback:
    @pytest.mark.parametrize(
        ("time", "label"), [(0, "Start"), (1.99, "Build"), (4, "Build"), (6, "")]
    )
    def test_chapter_at(self, time: float, label: str):
        m = json.dumps({"chapters": CHAPTERS})
        assert _run(f"Termshow.chapterAt({m}, {time})") == label

    def test_chapter_at_without_chapters(self):
        assert _run("Termshow.chapterAt({}, 3)") == ""

    @pytest.mark.parametrize(("time", "after"), [(0, 2), (1.5, 2), (2, 5), (5, None)])
    def test_next_chapter(self, time: float, after: float | None):
        assert _run(f"Termshow.nextChapterTime({json.dumps(CHAPTERS)}, {time})") == after

    @pytest.mark.parametrize(("time", "before"), [(0, 0), (2.2, 0), (3, 2), (9, 5)])
    def test_previous_chapter(self, time: float, before: float):
        # A little way into a chapter goes back to its start
        assert _run(f"Termshow.prevChapterTime({json.dumps(CHAPTERS)}, {time})") == before

    def test_no_chapters_to_jump_to(self):
        assert _run("[Termshow.nextChapterTime([], 1), Termshow.prevChapterTime([], 1)]") == [
            None,
            None,
        ]

    def test_overlays_fade(self):
        # Halfway through fading in, and fully shown in the middle
        assert _run(
            "[Termshow.fadeOpacity(0.15, 2, 0.3, 0.3), Termshow.fadeOpacity(1, 2, 0.3, 0.3)]"
        ) == [
            pytest.approx(0.5),
            1,
        ]

    def test_overlays_appear_at_once_with_reduced_motion(self):
        assert _run("Termshow.fadeOpacity(0.01, 2, 0.3, 0.3)", motion="reduce") == 1


def _css_block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    return match.group(1)


def _css_vars(block: str) -> dict[str, str]:
    return dict(re.findall(r"--gd-tp-([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def _contrast(a: str, b: str) -> float:
    def luminance(color: str) -> float:
        rgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class TestAccessibleStyles:
    css = (PLAYER_DIR / "termshow.css").read_text(encoding="utf-8")

    @pytest.mark.parametrize("theme", ["dark", "light"])
    def test_control_colors_meet_wcag_aa(self, theme: str):
        dark = _css_vars(_css_block(self.css, ".gd-termshow"))
        colors = (
            dark
            if theme == "dark"
            else {**dark, **_css_vars(_css_block(self.css, ".gd-termshow.gd-tp-light"))}
        )
        bar = colors["controls-bg"]
        # Text: 4.5:1 (the times, the speed, the chapter bar's label)
        assert _contrast(colors["fg"], bar) >= 4.5
        assert _contrast(colors["muted"], bar) >= 4.5
        assert _contrast(colors["fg"], colors["bg"]) >= 4.5
        # Parts of controls and focus rings: 3:1, the progress fill against the bar and
        # the unplayed track, and chapter markers against the bar
        assert _contrast(colors["accent"], bar) >= 3
        assert _contrast(colors["accent"], colors["progress-bg"]) >= 3
        assert _contrast(colors["chapter-color"], bar) >= 3

    def test_chapter_bar_follows_the_theme(self):
        # (A fixed white was unreadable on light themes)
        assert "color: var(--gd-tp-fg)" in _css_block(self.css, ".gd-tp-chapter-bar")

    def test_focus_is_visible(self):
        for selector in (".gd-tp-viewport:focus-visible", ".gd-tp-timeline:focus-visible"):
            assert "outline: 2px solid var(--gd-tp-accent)" in _css_block(self.css, selector)
        assert ".gd-tp-play-btn:focus-visible,\n.gd-tp-speed-btn:focus-visible" in self.css

    def test_reduced_motion_stops_animation(self):
        start = self.css.index("@media (prefers-reduced-motion: reduce)")
        block = self.css[start : self.css.index("\n}\n", start)]
        for selector in (
            ".gd-tp-annotation",
            ".gd-tp-highlight",
            ".gd-tp-cursor",
            ".gd-tp-hl-pulse",
        ):
            assert selector in block
        assert "animation: none !important" in block


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


def _transcript_html(markdown: str) -> str:
    return _run(f"Termshow.transcriptHtml({json.dumps(markdown)})")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
class TestTranscriptHtml:
    def test_label_and_text(self):
        assert _transcript_html("**Start \\<here\\>**\n\n```console\n$ ls <dir> & co\n```\n") == (
            "<p><strong>Start &lt;here&gt;</strong></p>\n"
            '<pre><code class="language-console">$ ls &lt;dir&gt; &amp; co</code></pre>'
        )

    def test_longer_fence_holds_backticks(self):
        md = "````console\n```\n$ x\n````\n"
        assert _transcript_html(md) == '<pre><code class="language-console">```\n$ x</code></pre>'

    def test_note_as_quote(self):
        assert _transcript_html("> one\n> two\n>\n> \\*three\\*\n") == (
            "<blockquote><p>one\ntwo</p><p>*three*</p></blockquote>"
        )

    def test_text_is_left_as_written(self):
        # Only a backslash before Markdown punctuation is an escape
        assert _transcript_html("a \\_b\\_ c\\d") == "<p>a _b_ c\\d</p>"

    def test_from_a_recording(self):
        recording = parse_termshow_str(
            '{"version": 1, "format": "termshow", "term": {"cols": 20, "rows": 3}}\n'
            '[0.0, "o", "$ echo *hi*\\r\\n*hi*\\r\\n"]'
        )
        script = _parse_script_data({"chapters": [{"at": 0, "label": "Say <hi>"}]})
        assert _transcript_html(transcript_markdown(recording, script)) == (
            "<p><strong>Say &lt;hi&gt;</strong></p>\n"
            '<pre><code class="language-console">$ echo *hi*\n*hi*</code></pre>'
        )
