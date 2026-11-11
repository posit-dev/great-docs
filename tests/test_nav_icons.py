from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from great_docs._website.icons import LUCIDE_ICONS, get_icon_svg, list_icons
from great_docs._website.navigation import icons
from great_docs.config import Config
from tests.support import write_config


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
        cfg = write_config(tmp_path, "nav_icons: false\n")
        assert cfg.nav_icons is None

    def test_navbar_only(self, tmp_path: Path):
        cfg = write_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    User Guide: book-open\n    Reference: code-2\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        assert "navbar" in icons
        assert icons["navbar"]["User Guide"] == "book-open"
        assert icons["navbar"]["Reference"] == "code-2"

    def test_sidebar_only(self, tmp_path: Path):
        cfg = write_config(
            tmp_path,
            "nav_icons:\n  sidebar:\n    Getting Started: rocket\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        assert "sidebar" in icons
        assert icons["sidebar"]["Getting Started"] == "rocket"

    def test_both_navbar_and_sidebar(self, tmp_path: Path):
        cfg = write_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    Recipes: chef-hat\n  sidebar:\n    Quick Start: rocket\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        assert icons["navbar"]["Recipes"] == "chef-hat"
        assert icons["sidebar"]["Quick Start"] == "rocket"

    def test_empty_dict_returns_none(self, tmp_path: Path):
        cfg = write_config(tmp_path, "nav_icons:\n  foo: bar\n")
        # No 'navbar' or 'sidebar' keys -> None
        assert cfg.nav_icons is None

    def test_nav_icons_navbar_property(self, tmp_path: Path):
        cfg = write_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    Changelog: history\n",
        )
        assert cfg.nav_icons_navbar == {"Changelog": "history"}

    def test_nav_icons_sidebar_property(self, tmp_path: Path):
        cfg = write_config(
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
        cfg = write_config(
            tmp_path,
            "nav_icons:\n  navbar:\n    123: home\n",
        )
        icons = cfg.nav_icons
        assert icons is not None
        # Key "123" should be a string
        assert "123" in icons["navbar"]


def _icon_data(quarto_config: dict[str, Any]) -> list[dict[str, dict[str, str]]]:
    after_body = quarto_config["format"]["html"]["include-after-body"]
    pattern = r'<script id="gd-nav-icons-data" type="application/json">(.*?)</script>'
    return [json.loads(m) for e in after_body for m in re.findall(pattern, e["text"])]


def test_register_embeds_icons_and_script(tmp_path: Path):
    config = write_config(
        tmp_path, "nav_icons:\n  navbar:\n    Reference: book\n  sidebar:\n    Intro: rocket\n"
    )
    quarto_config: dict[str, Any] = {"format": {"html": {}}}

    icons.register(quarto_config, config, report=print)

    assert _icon_data(quarto_config) == [
        {
            "navbar": {"Reference": get_icon_svg("book")},
            "sidebar": {"Intro": get_icon_svg("rocket")},
        }
    ]
    (entry,) = quarto_config["format"]["html"]["include-after-body"]
    script = (resources.files("great_docs") / "assets" / "nav-icons.js").read_text(encoding="utf-8")
    assert entry["text"].endswith(f"<script>{script}</script>")


def test_register_reports_and_skips_unknown_icons(tmp_path: Path):
    config = write_config(tmp_path, "nav_icons:\n  navbar:\n    Reference: no-such-icon\n")
    quarto_config: dict[str, Any] = {"format": {"html": {}}}
    reports: list[str] = []

    icons.register(quarto_config, config, report=reports.append)

    assert reports == ["Warning: Unknown nav icon 'no-such-icon' for 'Reference'"]
    assert "include-after-body" not in quarto_config["format"]["html"]
