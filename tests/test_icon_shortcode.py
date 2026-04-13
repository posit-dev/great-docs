"""Tests for the {{< icon >}} Quarto shortcode extension."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml


def _ext_dir() -> Path:
    return Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions" / "icon"


class TestIconExtensionFiles:
    """Verify that the icon extension ships the required files."""

    def test_extension_yml_exists(self):
        assert (_ext_dir() / "_extension.yml").exists()

    def test_lua_filter_exists(self):
        assert (_ext_dir() / "icon.lua").exists()

    def test_python_bridge_exists(self):
        assert (_ext_dir() / "_icon_shortcode.py").exists()

    def test_extension_yml_declares_shortcode(self):
        ext_yml = _ext_dir() / "_extension.yml"
        data = yaml.safe_load(ext_yml.read_text())
        assert "contributes" in data
        assert "shortcodes" in data["contributes"]
        assert "icon.lua" in data["contributes"]["shortcodes"]

    def test_lua_defines_icon_function(self):
        lua_src = (_ext_dir() / "icon.lua").read_text()
        assert '["icon"]' in lua_src
        assert "function(args, kwargs)" in lua_src


class TestIconBridgeScript:
    """Tests for _icon_shortcode.py (the Python bridge)."""

    def test_help_succeeds(self):
        bridge = _ext_dir() / "_icon_shortcode.py"
        result = subprocess.run(
            [sys.executable, str(bridge), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "name" in result.stdout.lower()

    def test_known_icon_outputs_svg(self):
        bridge = _ext_dir() / "_icon_shortcode.py"
        result = subprocess.run(
            [sys.executable, str(bridge), "heart"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert result.stdout.startswith("<svg")
        assert "</svg>" in result.stdout
        assert 'class="gd-icon"' in result.stdout
        assert 'aria-hidden="true"' in result.stdout
        # fa-style inline sizing
        assert "height:1em" in result.stdout
        assert "width:1em" in result.stdout
        assert "vertical-align:-0.125em" in result.stdout
        assert "font-size:inherit" in result.stdout
        # No pixel width/height attributes
        assert 'width="' not in result.stdout
        assert 'height="' not in result.stdout

    def test_custom_size(self):
        bridge = _ext_dir() / "_icon_shortcode.py"
        result = subprocess.run(
            [sys.executable, str(bridge), "rocket", "--size", "32"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        # 32px / 16 = 2em
        assert "height:2em" in result.stdout or "height:2.0em" in result.stdout
        assert "width:2em" in result.stdout or "width:2.0em" in result.stdout
        # No pixel attributes
        assert 'width="' not in result.stdout
        assert 'height="' not in result.stdout

    def test_custom_class(self):
        bridge = _ext_dir() / "_icon_shortcode.py"
        result = subprocess.run(
            [sys.executable, str(bridge), "star", "--class", "fancy-icon"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert 'class="fancy-icon"' in result.stdout

    def test_label_replaces_aria_hidden(self):
        bridge = _ext_dir() / "_icon_shortcode.py"
        result = subprocess.run(
            [sys.executable, str(bridge), "check", "--label", "Complete"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert 'aria-label="Complete"' in result.stdout
        assert 'role="img"' in result.stdout
        assert 'aria-hidden="true"' not in result.stdout

    def test_unknown_icon_fails(self):
        bridge = _ext_dir() / "_icon_shortcode.py"
        result = subprocess.run(
            [sys.executable, str(bridge), "nonexistent-icon-xyz"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0

    def test_no_trailing_newline(self):
        """Output should not have trailing newline (inline SVG)."""
        bridge = _ext_dir() / "_icon_shortcode.py"
        result = subprocess.run(
            [sys.executable, str(bridge), "home"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert not result.stdout.endswith("\n")
