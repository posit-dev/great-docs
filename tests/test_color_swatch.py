"""Tests for the {{< color-swatch >}} Quarto shortcode extension."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from yaml12 import read_yaml


def _ext_dir() -> Path:
    return Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions" / "color-swatch"


def _helper() -> Path:
    return _ext_dir() / "_color_swatch_shortcode.py"


# ---------------------------------------------------------------------------
# Extension files
# ---------------------------------------------------------------------------


class TestColorSwatchExtensionFiles:
    """Verify that the color-swatch extension ships the required files."""

    def test_extension_yml_exists(self):
        assert (_ext_dir() / "_extension.yml").exists()

    def test_lua_filter_exists(self):
        assert (_ext_dir() / "color-swatch.lua").exists()

    def test_python_bridge_exists(self):
        assert _helper().exists()

    def test_extension_yml_declares_shortcode(self):
        ext_yml = _ext_dir() / "_extension.yml"
        data = read_yaml(ext_yml)
        assert "contributes" in data
        assert "shortcodes" in data["contributes"]
        assert "color-swatch.lua" in data["contributes"]["shortcodes"]

    def test_lua_defines_color_swatch_function(self):
        lua_src = (_ext_dir() / "color-swatch.lua").read_text()
        assert '["color-swatch"]' in lua_src
        assert "function(args, kwargs, blocks)" in lua_src


# ---------------------------------------------------------------------------
# Python helper — importable unit tests
# ---------------------------------------------------------------------------


class TestHelperImports:
    """Verify the Python helper can be imported and its core utilities work."""

    @pytest.fixture(autouse=True)
    def _import_helper(self):
        """Import the helper module dynamically."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("_color_swatch_shortcode", _helper())
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    # -- hex_to_rgb --

    def test_hex_to_rgb_six_digit(self):
        assert self.mod.hex_to_rgb("#38bdf8") == (56, 189, 248)

    def test_hex_to_rgb_three_digit(self):
        assert self.mod.hex_to_rgb("#fff") == (255, 255, 255)

    def test_hex_to_rgb_named_color(self):
        assert self.mod.hex_to_rgb("red") == (255, 0, 0)

    def test_hex_to_rgb_invalid_raises(self):
        with pytest.raises(ValueError):
            self.mod.hex_to_rgb("not-a-color")

    # -- rgb_to_hsl --

    def test_rgb_to_hsl_red(self):
        h, s, l = self.mod.rgb_to_hsl(255, 0, 0)
        assert h == 0
        assert s == 100
        assert l == 50

    def test_rgb_to_hsl_white(self):
        h, s, l = self.mod.rgb_to_hsl(255, 255, 255)
        assert s == 0
        assert l == 100

    def test_rgb_to_hsl_black(self):
        h, s, l = self.mod.rgb_to_hsl(0, 0, 0)
        assert s == 0
        assert l == 0

    # -- needs_border_ring --

    def test_ring_very_light(self):
        ring, color = self.mod.needs_border_ring("#fefefe")
        assert ring is True
        assert color.startswith("#")

    def test_ring_very_dark(self):
        ring, color = self.mod.needs_border_ring("#010101")
        assert ring is True
        assert color.startswith("#")

    def test_ring_mid_range(self):
        ring, _ = self.mod.needs_border_ring("#808080")
        assert ring is False

    # -- compute_contrast_info --

    def test_contrast_info_keys(self):
        info = self.mod.compute_contrast_info("#38bdf8")
        assert "lc_vs_white" in info
        assert "lc_vs_black" in info
        assert "ideal_text" in info
        assert "aa_normal" in info
        assert "aa_large" in info

    def test_contrast_white_on_white(self):
        info = self.mod.compute_contrast_info("#ffffff")
        assert info["lc_vs_white"] == 0.0

    def test_contrast_black_has_high_lc(self):
        info = self.mod.compute_contrast_info("#000000")
        assert info["lc_vs_white"] > 90

    # -- GD_PALETTES --

    def test_all_palettes_defined(self):
        names = {"sky", "peach", "prism", "lilac", "slate", "honey", "dusk", "mint"}
        assert names == set(self.mod.GD_PALETTES.keys())

    def test_palette_has_light_and_dark(self):
        for name, preset in self.mod.GD_PALETTES.items():
            assert "light" in preset, f"{name} missing 'light'"
            assert "dark" in preset, f"{name} missing 'dark'"
            assert len(preset["light"]) > 0
            assert len(preset["dark"]) > 0

    def test_palette_colors_have_name_and_hex(self):
        for name, preset in self.mod.GD_PALETTES.items():
            for c in preset["light"] + preset["dark"]:
                assert "name" in c, f"{name}: color missing 'name'"
                assert "hex" in c, f"{name}: color missing 'hex'"

    # -- parse_colors --

    def test_parse_colors_palette(self):
        colors = self.mod.parse_colors("", "sky")
        assert len(colors) == 4
        assert all("hex" in c for c in colors)

    def test_parse_colors_all(self):
        colors = self.mod.parse_colors("", "all")
        assert len(colors) == 8 * 4  # 8 presets × 4 colors each

    def test_parse_colors_unknown_palette(self):
        with pytest.raises(ValueError, match="Unknown palette"):
            self.mod.parse_colors("", "nonexistent")

    def test_parse_colors_yaml_body(self):
        body = '- name: Test\n  hex: "#ff0000"\n'
        colors = self.mod.parse_colors(body, "")
        assert len(colors) == 1
        assert colors[0]["hex"] == "#ff0000"

    def test_parse_colors_palette_plus_body(self):
        body = '- name: Extra\n  hex: "#abcdef"\n'
        colors = self.mod.parse_colors(body, "sky")
        assert len(colors) == 5  # 4 from sky + 1 from body

    def test_parse_colors_empty(self):
        colors = self.mod.parse_colors("", "")
        assert colors == []

    # -- render_circles --

    def test_render_circles_basic(self):
        colors = [
            {"name": "Red", "hex": "#ff0000"},
            {"name": "Blue", "hex": "#0000ff"},
        ]
        html = self.mod.render_circles(colors)
        assert "gd-color-swatch--circles" in html
        assert "#ff0000" in html
        assert "#0000ff" in html
        assert "Red" in html
        assert "Blue" in html
        assert 'role="button"' in html
        assert "data-tooltip-html" in html

    def test_render_circles_no_names(self):
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, show_names="false")
        assert "gd-swatch-name" not in html

    def test_render_circles_no_hex(self):
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, show_hex="false")
        assert "gd-swatch-hex" not in html

    def test_render_circles_inline_contrast(self):
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, show_contrast="inline")
        assert "gd-swatch-contrast" in html

    def test_render_circles_custom_size(self):
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, size="80px")
        assert "--gd-cs-size:80px" in html

    def test_render_circles_title(self):
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, title="My Palette")
        assert "My Palette" in html
        assert "gd-cs-title" in html

    # -- render_rectangles --

    def test_render_rectangles_basic(self):
        colors = [
            {"name": "Green", "hex": "#22c55e"},
            {"name": "Navy", "hex": "#1e3a5f"},
        ]
        html = self.mod.render_rectangles(colors)
        assert "gd-color-swatch--rectangles" in html
        assert "#22c55e" in html
        assert "Green" in html
        assert "gd-swatch-rect" in html
        assert "gd-swatch-aa-sample" in html

    def test_render_rectangles_no_contrast(self):
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_rectangles(colors, show_contrast="false")
        assert "gd-swatch-aa-sample" not in html

    # -- build_tooltip_html --

    def test_tooltip_html_basic(self):
        color = {"name": "Sky Blue", "hex": "#38bdf8"}
        html = self.mod.build_tooltip_html(color, "true")
        assert "Sky Blue" in html
        assert "#38bdf8" in html
        assert "RGB" in html
        assert "HSL" in html
        assert "vs White" in html
        assert "vs Black" in html
        assert "WCAG" in html

    def test_tooltip_html_no_contrast(self):
        color = {"name": "Sky Blue", "hex": "#38bdf8"}
        html = self.mod.build_tooltip_html(color, "false")
        assert "vs White" not in html
        assert "WCAG" not in html

    # -- parse_colors edge cases --

    def test_parse_colors_body_missing_hex_skipped(self):
        """Entry without 'hex' key is skipped (covers the continue branch)."""
        body = "- name: OnlyName\n  shade: light\n"
        colors = self.mod.parse_colors(body, "")
        assert colors == []

    def test_parse_colors_skips_items_that_are_not_mappings(self):
        """Keep valid colours when YAML also contains numeric or empty items"""
        body = '- 42\n-\n- name: Kept\n  hex: "#ff0000"\n'
        colors = self.mod.parse_colors(body, "")
        assert [c["name"] for c in colors] == ["Kept"]

    def test_parse_colors_unquoted_hex_names_the_entry(self):
        """Identify the invalid colour when an unquoted hex value becomes null"""
        # An unquoted `#ff0000` starts a YAML comment, leaving `hex` null.
        body = "- name: Red\n  hex: #ff0000\n"
        with pytest.raises(ValueError, match="Red"):
            self.mod.parse_colors(body, "")

    def test_parse_yaml_non_list_body_returns_empty(self):
        """YAML that parses to a non-list (e.g. a mapping) returns []."""
        body = "key: value\nanother: 42\n"
        colors = self.mod.parse_colors(body, "")
        assert colors == []

    # -- render_circles extra branches --

    def test_render_circles_description(self):
        """description kwarg is rendered into the output."""
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, description="A red swatch")
        assert "gd-cs-description" in html
        assert "A red swatch" in html

    def test_render_circles_extra_class(self):
        """extra_class kwarg is appended to the wrapper class."""
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, extra_class="my-custom")
        assert "my-custom" in html

    def test_render_circles_ring_on_very_light_color(self):
        """Very light color triggers ring attr and style."""
        colors = [{"name": "White", "hex": "#fefefe"}]
        html = self.mod.render_circles(colors)
        assert 'data-needs-ring="true"' in html
        assert "--gd-ring-color:" in html

    # -- render_rectangles extra branches --

    def test_render_rectangles_extra_class(self):
        """extra_class kwarg appended to rectangles wrapper."""
        colors = [{"name": "Green", "hex": "#22c55e"}]
        html = self.mod.render_rectangles(colors, extra_class="rect-custom")
        assert "rect-custom" in html

    def test_render_rectangles_title(self):
        """title kwarg is rendered for rectangles."""
        colors = [{"name": "Green", "hex": "#22c55e"}]
        html = self.mod.render_rectangles(colors, title="Rect Palette")
        assert "gd-cs-title" in html
        assert "Rect Palette" in html

    def test_render_rectangles_description(self):
        """description kwarg is rendered for rectangles."""
        colors = [{"name": "Green", "hex": "#22c55e"}]
        html = self.mod.render_rectangles(colors, description="Rectangle desc")
        assert "gd-cs-description" in html
        assert "Rectangle desc" in html

    def test_render_circles_no_border(self):
        """border='false' omits the bordered CSS class from circles."""
        colors = [{"name": "Red", "hex": "#ff0000"}]
        html = self.mod.render_circles(colors, border="false")
        assert "gd-color-swatch--bordered" not in html

    def test_render_rectangles_no_border(self):
        """border='false' omits the bordered CSS class from rectangles."""
        colors = [{"name": "Green", "hex": "#22c55e"}]
        html = self.mod.render_rectangles(colors, border="false")
        assert "gd-color-swatch--bordered" not in html

    def test_render_rectangles_no_names(self):
        """show_names='false' omits name span from rectangles."""
        colors = [{"name": "Green", "hex": "#22c55e"}]
        html = self.mod.render_rectangles(colors, show_names="false")
        assert "gd-swatch-rect-name" not in html

    def test_render_rectangles_no_hex(self):
        """show_hex='false' omits hex span from rectangles."""
        colors = [{"name": "Green", "hex": "#22c55e"}]
        html = self.mod.render_rectangles(colors, show_hex="false")
        assert "gd-swatch-rect-hex" not in html


# ---------------------------------------------------------------------------
# main() entry-point tests (in-process, no subprocess)
# ---------------------------------------------------------------------------


class TestColorSwatchMain:
    """Call main() directly with patched sys.argv / stdin to cover the CLI code."""

    @pytest.fixture(autouse=True)
    def _import_helper(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("_color_swatch_shortcode", _helper())
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def _run(self, args, stdin_text=None):
        """Invoke main() with patched env; return (stdout, stderr, exit_code)."""
        import io
        from unittest.mock import patch

        fake_stdin = io.StringIO(stdin_text if stdin_text is not None else "")
        fake_stdin.isatty = lambda: stdin_text is None
        fake_stdout = io.StringIO()
        fake_stderr = io.StringIO()
        argv = [str(_helper())] + args
        code = 0
        with (
            patch("sys.argv", argv),
            patch("sys.stdin", fake_stdin),
            patch("sys.stdout", fake_stdout),
            patch("sys.stderr", fake_stderr),
        ):
            try:
                self.mod.main()
            except SystemExit as exc:
                code = exc.code
        return fake_stdout.getvalue(), fake_stderr.getvalue(), code

    def test_main_circles_palette(self):
        out, _, code = self._run(["--palette", "sky"])
        assert code == 0
        assert "gd-color-swatch--circles" in out

    def test_main_rectangles_mode(self):
        out, _, code = self._run(["--palette", "sky", "--mode", "rectangles"])
        assert code == 0
        assert "gd-color-swatch--rectangles" in out

    def test_main_stdin_yaml(self):
        body = '- name: StdinColor\n  hex: "#aabbcc"\n'
        out, _, code = self._run([], stdin_text=body)
        assert code == 0
        assert "StdinColor" in out

    def test_main_file_input_absolute(self, tmp_path):
        f = tmp_path / "colors.yaml"
        f.write_text('- name: FileColor\n  hex: "#ff0000"\n')
        out, _, code = self._run(["--file", str(f)])
        assert code == 0
        assert "FileColor" in out

    def test_main_file_input_relative(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "colors.yaml"
        f.write_text('- name: RelColor\n  hex: "#00ff00"\n')
        out, _, code = self._run(["--file", "colors.yaml"])
        assert code == 0
        assert "RelColor" in out

    def test_main_no_colors_exits_nonzero(self):
        """No colors → error message to stderr and exit 1."""
        _, err, code = self._run([])
        assert code == 1
        assert "no colors" in err

    def test_main_unsupported_mode_exits_nonzero(self):
        """Unknown mode → error message and exit 1."""
        _, err, code = self._run(["--palette", "sky", "--mode", "gradient"])
        assert code == 1
        assert "unsupported mode" in err

    def test_main_exception_exits_nonzero(self):
        """Exception (e.g. unknown palette) → error message and exit 1."""
        _, err, code = self._run(["--palette", "nonexistent"])
        assert code == 1
        assert "color-swatch error" in err


class TestColorSwatchCLI:
    """Test the helper as a subprocess (simulates how Lua calls it)."""

    def test_help_succeeds(self):
        result = subprocess.run(
            [sys.executable, str(_helper()), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "palette" in result.stdout.lower()

    def test_palette_sky_circles(self):
        result = subprocess.run(
            [sys.executable, str(_helper()), "--palette", "sky"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "gd-color-swatch--circles" in result.stdout
        assert "Sky" in result.stdout

    def test_palette_sky_rectangles(self):
        result = subprocess.run(
            [sys.executable, str(_helper()), "--palette", "sky", "--mode", "rectangles"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "gd-color-swatch--rectangles" in result.stdout

    def test_stdin_yaml(self):
        yaml_body = '- name: Test Red\n  hex: "#ff0000"\n'
        result = subprocess.run(
            [sys.executable, str(_helper())],
            input=yaml_body,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "Test Red" in result.stdout
        assert "#ff0000" in result.stdout

    def test_unknown_palette_fails(self):
        result = subprocess.run(
            [sys.executable, str(_helper()), "--palette", "nonexistent"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0

    def test_no_input_fails(self):
        result = subprocess.run(
            [sys.executable, str(_helper())],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0

    def test_unsupported_mode_fails(self):
        result = subprocess.run(
            [sys.executable, str(_helper()), "--palette", "sky", "--mode", "gradient"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
