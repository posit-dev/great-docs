"""Tests for the APCA contrast module and navbar_color configuration."""

import tempfile
from pathlib import Path

import pytest

from great_docs.contrast import (
    parse_color,
    ideal_text_color,
    navbar_color_css,
    _relative_luminance_apca,
    _apca_contrast,
)
from great_docs import Config


class TestParseColor:
    """Tests for CSS color parsing."""

    def test_hex_6digit(self):
        assert parse_color("#FF0000") == (255, 0, 0)
        assert parse_color("#00ff00") == (0, 255, 0)
        assert parse_color("#0000FF") == (0, 0, 255)

    def test_hex_3digit(self):
        assert parse_color("#F00") == (255, 0, 0)
        assert parse_color("#0f0") == (0, 255, 0)

    def test_hex_8digit_alpha(self):
        # Alpha channel should be ignored for RGB extraction
        assert parse_color("#FF000080") == (255, 0, 0)

    def test_hex_4digit_alpha(self):
        assert parse_color("#F008") == (255, 0, 0)

    def test_named_colors(self):
        assert parse_color("white") == (255, 255, 255)
        assert parse_color("black") == (0, 0, 0)
        assert parse_color("red") == (255, 0, 0)
        assert parse_color("steelblue") == (70, 130, 180)

    def test_named_color_case_insensitive(self):
        assert parse_color("White") == (255, 255, 255)
        assert parse_color("BLACK") == (0, 0, 0)
        assert parse_color("SteelBlue") == (70, 130, 180)

    def test_whitespace_stripped(self):
        assert parse_color("  #FF0000  ") == (255, 0, 0)
        assert parse_color(" white ") == (255, 255, 255)

    def test_invalid_color_raises(self):
        with pytest.raises(ValueError, match="Unrecognized color"):
            parse_color("notacolor")

    def test_invalid_hex_raises(self):
        with pytest.raises(ValueError, match="Unrecognized color"):
            parse_color("#GG0000")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_color("")

    @pytest.mark.parametrize("color", ["#12345", "#1234567"])
    def test_hex_of_unsupported_length_raises(self, color):
        # The pattern accepts three to eight hex digits; only lengths 3, 4, 6 and 8
        # have supported channel layouts.
        with pytest.raises(ValueError, match="Unrecognized color"):
            parse_color(color)


class TestAPCALuminance:
    """Tests for APCA relative luminance calculation."""

    def test_white_highest_luminance(self):
        lum_white = _relative_luminance_apca(255, 255, 255)
        lum_black = _relative_luminance_apca(0, 0, 0)
        assert lum_white > lum_black

    def test_black_near_zero(self):
        lum = _relative_luminance_apca(0, 0, 0)
        assert lum < 0.05

    def test_mid_gray(self):
        lum = _relative_luminance_apca(128, 128, 128)
        assert 0.1 < lum < 0.5


class TestAPCAContrast:
    """Tests for APCA contrast calculation."""

    def test_max_contrast_white_on_black(self):
        lum_white = _relative_luminance_apca(255, 255, 255)
        lum_black = _relative_luminance_apca(0, 0, 0)
        contrast = _apca_contrast(lum_white, lum_black)
        # White text on black background should give strong negative contrast
        assert abs(contrast) > 100

    def test_max_contrast_black_on_white(self):
        lum_white = _relative_luminance_apca(255, 255, 255)
        lum_black = _relative_luminance_apca(0, 0, 0)
        contrast = _apca_contrast(lum_black, lum_white)
        # Black text on white background should give strong positive contrast
        assert contrast > 100

    def test_no_contrast_same_color(self):
        lum = _relative_luminance_apca(128, 128, 128)
        contrast = _apca_contrast(lum, lum)
        assert contrast == 0.0


class TestIdealTextColor:
    """Tests for APCA-based text color selection."""

    def test_dark_bg_gets_light_text(self):
        # Dark backgrounds should get white text
        assert ideal_text_color("#000000") == "#FFFFFF"
        assert ideal_text_color("#1a1a1a") == "#FFFFFF"
        assert ideal_text_color("#333333") == "#FFFFFF"
        assert ideal_text_color("navy") == "#FFFFFF"
        assert ideal_text_color("darkgreen") == "#FFFFFF"

    def test_light_bg_gets_dark_text(self):
        # Light backgrounds should get black text
        assert ideal_text_color("#FFFFFF") == "#000000"
        assert ideal_text_color("#e3f2fd") == "#000000"
        assert ideal_text_color("#fafafa") == "#000000"
        assert ideal_text_color("white") == "#000000"
        assert ideal_text_color("lightyellow") == "#000000"

    def test_mid_tone_colors(self):
        # Just verify it returns one of the two options
        result = ideal_text_color("#808080")
        assert result in ("#FFFFFF", "#000000")

    def test_custom_light_dark(self):
        result = ideal_text_color("#000000", light="#EEEEEE", dark="#111111")
        assert result == "#EEEEEE"

    def test_red_bg(self):
        result = ideal_text_color("red")
        assert result in ("#FFFFFF", "#000000")

    def test_yellow_bg_gets_dark_text(self):
        # Yellow is perceptually bright
        assert ideal_text_color("yellow") == "#000000"

    def test_blue_bg_gets_light_text(self):
        # Pure blue is perceptually dark
        assert ideal_text_color("blue") == "#FFFFFF"


class TestNavbarColorCSS:
    """Tests for CSS generation from navbar color."""

    def test_dark_bg_css(self):
        css = navbar_color_css("#1a1a1a")
        assert "--gd-navbar-bg: #1a1a1a" in css
        assert "--gd-navbar-text: #FFFFFF" in css

    def test_light_bg_css(self):
        css = navbar_color_css("#e3f2fd")
        assert "--gd-navbar-bg: #e3f2fd" in css
        assert "--gd-navbar-text: #000000" in css

    def test_named_color_css(self):
        css = navbar_color_css("steelblue")
        assert "--gd-navbar-bg: #4682b4" in css

    def test_custom_text_colors(self):
        css = navbar_color_css("#000000", light_text="#F0F0F0", dark_text="#101010")
        assert "--gd-navbar-text: #F0F0F0" in css


class TestNavbarColorConfig:
    """Tests for navbar_color config property."""

    def test_navbar_color_none_by_default(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = Config(Path(tmp_dir))
            assert config.navbar_color is None

    def test_navbar_color_string(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("navbar_color: '#2c3e50'\n")
            config = Config(Path(tmp_dir))
            assert config.navbar_color == {"light": "#2c3e50", "dark": "#2c3e50"}

    def test_navbar_color_dict(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("navbar_color:\n  light: '#e3f2fd'\n  dark: '#1a237e'\n")
            config = Config(Path(tmp_dir))
            result = config.navbar_color
            assert result == {"light": "#e3f2fd", "dark": "#1a237e"}

    def test_navbar_color_dict_single_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("navbar_color:\n  dark: '#1a237e'\n")
            config = Config(Path(tmp_dir))
            result = config.navbar_color
            assert result == {"dark": "#1a237e"}
            assert "light" not in result

    def test_navbar_color_ignored_when_navbar_style_set(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("navbar_style: sky\nnavbar_color: '#2c3e50'\n")
            config = Config(Path(tmp_dir))
            assert config.navbar_color is None
            assert config.navbar_style == "sky"

    def test_navbar_color_false(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("navbar_color: false\n")
            config = Config(Path(tmp_dir))
            assert config.navbar_color is None
