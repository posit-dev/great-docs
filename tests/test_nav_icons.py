from __future__ import annotations

from pathlib import Path

import pytest

from great_docs._icons import LUCIDE_ICONS, get_icon_svg, list_icons
from great_docs.config import Config


def _make_config(tmp_path: Path, yaml_text: str) -> Config:
    (tmp_path / "great-docs.yml").write_text(yaml_text, encoding="utf-8")
    return Config(tmp_path)


class TestLucideIcons:
    """Tests for the Lucide icon data module."""

    def test_icon_dict_is_nonempty(self):
        assert len(LUCIDE_ICONS) > 50

    def test_all_values_are_lists_of_strings(self):
        for name, children in LUCIDE_ICONS.items():
            assert isinstance(children, list), f"{name}: expected list"
            for child in children:
                assert isinstance(child, str), f"{name}: child not str"
                assert child.startswith("<"), f"{name}: child missing '<'"

    def test_list_icons_sorted(self):
        names = list_icons()
        assert names == sorted(names)
        assert len(names) == len(LUCIDE_ICONS)


class TestGetIconSvg:
    """Tests for get_icon_svg()."""

    def test_known_icon_returns_svg(self):
        svg = get_icon_svg("book")
        assert svg is not None
        assert svg.startswith("<svg")
        assert 'class="gd-nav-icon"' in svg
        assert 'aria-hidden="true"' in svg
        assert "stroke-width" in svg
        assert "</svg>" in svg

    def test_unknown_icon_returns_empty(self):
        assert get_icon_svg("nonexistent-icon-xyz") == ""

    def test_custom_size(self):
        svg = get_icon_svg("home", size=24)
        assert svg is not None
        assert 'width="24"' in svg
        assert 'height="24"' in svg

    def test_custom_css_class(self):
        svg = get_icon_svg("home", css_class="my-icon")
        assert svg is not None
        assert 'class="my-icon"' in svg

    def test_default_size_is_16(self):
        svg = get_icon_svg("home")
        assert svg is not None
        assert 'width="16"' in svg
        assert 'height="16"' in svg

    def test_viewbox_is_24(self):
        svg = get_icon_svg("home")
        assert svg is not None
        assert 'viewBox="0 0 24 24"' in svg

    def test_svg_contains_icon_paths(self):
        svg = get_icon_svg("book")
        assert svg is not None
        # The <svg> should contain the child elements from LUCIDE_ICONS
        for child in LUCIDE_ICONS["book"]:
            assert child in svg

    @pytest.mark.parametrize(
        "icon_name",
        ["home", "book-open", "code-2", "rocket", "chef-hat", "history", "settings"],
    )
    def test_common_icons_exist(self, icon_name: str):
        svg = get_icon_svg(icon_name)
        assert svg is not None, f"Icon '{icon_name}' should exist"


class TestNavIconsConfig:
    """Tests for Config.nav_icons, nav_icons_navbar, nav_icons_sidebar."""

    def test_default_is_none(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.nav_icons is None

    def test_false_is_none(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "nav_icons: false\n")
        assert cfg.nav_icons is None

    def test_navbar_only(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    User Guide: book-open\n    Reference: code-2\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        assert "navbar" in icons
        assert icons["navbar"]["User Guide"] == "book-open"
        assert icons["navbar"]["Reference"] == "code-2"

    def test_sidebar_only(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "nav_icons:\n  sidebar:\n    Getting Started: rocket\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        assert "sidebar" in icons
        assert icons["sidebar"]["Getting Started"] == "rocket"

    def test_both_navbar_and_sidebar(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    Recipes: chef-hat\n  sidebar:\n    Quick Start: rocket\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        assert icons["navbar"]["Recipes"] == "chef-hat"
        assert icons["sidebar"]["Quick Start"] == "rocket"

    def test_empty_dict_returns_none(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "nav_icons:\n  foo: bar\n")
        # No 'navbar' or 'sidebar' keys -> None
        assert cfg.nav_icons is None

    def test_nav_icons_navbar_property(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    Changelog: history\n",
        )
        assert cfg.nav_icons_navbar == {"Changelog": "history"}

    def test_nav_icons_sidebar_property(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "nav_icons:\n  sidebar:\n    Config: settings\n",
        )
        assert cfg.nav_icons_sidebar == {"Config": "settings"}

    def test_nav_icons_navbar_empty_when_not_configured(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.nav_icons_navbar == {}

    def test_nav_icons_sidebar_empty_when_not_configured(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.nav_icons_sidebar == {}

    def test_values_coerced_to_strings(self, tmp_path: Path):
        # Ensure non-string YAML values get coerced
        cfg = _make_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    123: home\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        # Key "123" should be a string
        assert "123" in icons["navbar"]
