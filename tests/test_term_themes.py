"""Tests for named termshow themes and `settings.theme` resolution."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from great_docs._term_player import generate_manifest
from great_docs._term_player.parser import Event, Recording, TermInfo, Theme
from great_docs._term_player.script import _parse_script_data
from great_docs._term_player.themes import get_theme, resolve_theme, theme_names

_HEX = re.compile(r"^#[0-9a-f]{6}$")


class TestRegistry:
    def test_expected_themes_present(self):
        names = theme_names()
        for name in (
            "default",
            "dracula",
            "monokai",
            "nord",
            "github-dark",
            "github-light",
            "solarized-dark",
            "solarized-light",
            "catppuccin-mocha",
            "catppuccin-latte",
            "tokyo-night",
        ):
            assert name in names

    @pytest.mark.parametrize("name", theme_names())
    def test_every_theme_is_well_formed(self, name: str):
        theme = get_theme(name)
        assert _HEX.match(theme.fg)
        assert _HEX.match(theme.bg)
        assert len(theme.palette) == 16
        assert all(_HEX.match(c) for c in theme.palette)
        assert theme.fg != theme.bg

    def test_default_matches_theme_dataclass(self):
        default = get_theme("default")
        assert (default.fg, default.bg, default.palette) == (
            Theme().fg,
            Theme().bg,
            Theme().palette,
        )

    @pytest.mark.parametrize("spelling", ["Tokyo Night", "tokyo_night", " TOKYO-NIGHT "])
    def test_name_normalization(self, spelling: str):
        assert get_theme(spelling).bg == get_theme("tokyo-night").bg

    def test_unknown_name_lists_available(self):
        with pytest.raises(ValueError, match=r"Unknown termshow theme 'draculaa'.*dracula"):
            get_theme("draculaa")

    def test_returned_theme_is_a_copy(self):
        """Mutating a resolved theme must not leak into the registry."""
        get_theme("nord").palette[0] = "#000000"
        assert get_theme("nord").palette[0] == "#3b4252"


class TestResolveTheme:
    def test_name(self):
        assert resolve_theme("dracula").bg == "#282a36"

    def test_inline_overrides_base(self):
        theme = resolve_theme({"base": "nord", "bg": "#000000"})
        assert theme.bg == "#000000"
        assert theme.fg == "#d8dee9"
        assert theme.palette == get_theme("nord").palette

    def test_inline_without_base_starts_from_default(self):
        theme = resolve_theme({"fg": "#ffffff"})
        assert theme.fg == "#ffffff"
        assert theme.bg == Theme().bg

    def test_eight_color_palette_is_reused_for_brights(self):
        pal = ["#000", "#f00", "#0f0", "#ff0", "#00f", "#f0f", "#0ff", "#fff"]
        theme = resolve_theme({"palette": pal})
        assert theme.palette == pal + pal

    @pytest.mark.parametrize(
        "spec, message",
        [
            ({"bg": "black"}, "bg must be a hex color"),
            ({"fg": 123}, "fg must be a hex color"),
            ({"palette": ["#000"] * 5}, "8 or 16"),
            ({"palette": ["#000"] * 7 + ["nope"]}, r"palette\[7\]"),
            ({"base": "nope"}, "Unknown termshow theme"),
            (42, "must be a name or a mapping"),
        ],
    )
    def test_invalid_specs(self, spec, message):
        with pytest.raises(ValueError, match=message):
            resolve_theme(spec)


class TestScriptTheme:
    def test_named_theme_resolved(self):
        script = _parse_script_data({"settings": {"theme": "monokai"}})
        assert script.theme_name == "monokai"
        assert script.theme_spec == "monokai"
        assert script.theme.bg == "#272822"

    def test_inline_theme_name_uses_base(self):
        script = _parse_script_data({"settings": {"theme": {"base": "nord", "bg": "#111111"}}})
        assert script.theme_name == "nord"
        assert script.theme.bg == "#111111"

    def test_inline_theme_without_base_is_custom(self):
        script = _parse_script_data({"settings": {"theme": {"bg": "#111111"}}})
        assert script.theme_name == "custom"

    def test_no_theme(self):
        script = _parse_script_data({"settings": {}})
        assert script.theme is None
        assert script.theme_name is None

    def test_unknown_theme_raises(self):
        with pytest.raises(ValueError, match="Unknown termshow theme"):
            _parse_script_data({"settings": {"theme": "not-a-theme"}})

    def test_theme_reaches_rendered_svg(self, tmp_path: Path):
        """The resolved theme's background is what the SVG frames are painted with."""
        recording = Recording(
            term=TermInfo(cols=20, rows=4),
            events=[Event(time=0.0, code="o", data="\x1b[31mred\x1b[0m")],
        )
        script = _parse_script_data({"settings": {"theme": "dracula"}})
        manifest = generate_manifest(recording, script, output_dir=tmp_path)
        svg = (tmp_path / manifest.keyframes[-1].file).read_text()
        assert 'fill="#282a36"' in svg
        assert "#ff5555" in svg  # dracula red
        assert manifest.theme == "dracula"
