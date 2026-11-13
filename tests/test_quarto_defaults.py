"""
Quarto project defaults, site settings and extension filters
"""

from pathlib import Path
from typing import Any

import pytest

from great_docs._project.layout import Layout
from great_docs._website import quarto_defaults
from tests.support import write_config


def _initial() -> dict[str, Any]:
    return {"project": {"type": "website"}, "format": {"html": {"theme": "flatly"}}}


def _register_site(
    root: Path, settings: str = "", quarto_config: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[str]]:
    config = write_config(root, settings)
    quarto_config = quarto_config if quarto_config is not None else _initial()
    reports: list[str] = []
    quarto_defaults.register_site(quarto_config, config, Layout.make(root), report=reports.append)
    return quarto_config, reports


class TestRegister:
    def test_freeze_mode_restores_the_cache_before_rendering(self, tmp_path: Path):
        quarto_config = _initial()
        config = write_config(tmp_path)
        quarto_defaults.register(quarto_config, config, Layout.make(tmp_path))
        assert quarto_config["project"]["output-dir"] == "_site"
        assert quarto_config["project"]["pre-render"] == "scripts/restore-freeze.py"
        assert quarto_config["execute"] == {"freeze": "auto"}

    def test_freeze_cache_alone_restores_without_freezing(self, tmp_path: Path):
        (tmp_path / "_freeze").mkdir()
        quarto_config = _initial()
        config = write_config(
            tmp_path, "freeze:\n  mode: false\npre_render: [tools/a.py, other/a.py, b.py]\n"
        )
        quarto_defaults.register(quarto_config, config, Layout.make(tmp_path))
        assert quarto_config["project"]["pre-render"] == [
            "scripts/restore-freeze.py",
            "scripts/a.py",
            "scripts/b.py",
        ]
        assert "execute" not in quarto_config

    def test_no_freeze_and_no_scripts(self, tmp_path: Path):
        quarto_config = _initial()
        config = write_config(tmp_path, "freeze:\n  mode: false\n")
        quarto_defaults.register(quarto_config, config, Layout.make(tmp_path))
        assert quarto_config == {
            "project": {"type": "website", "output-dir": "_site"},
            "format": {"html": {"theme": "flatly"}},
        }


class TestRegisterSite:
    def test_site_settings_and_great_docs_defaults(self, tmp_path: Path):
        quarto_config, reports = _register_site(tmp_path, "site:\n  theme: cosmo\n  toc-depth: 3\n")
        html = quarto_config["format"]["html"]
        assert html["theme"] == ["cosmo", "great-docs.scss"]
        assert html["toc-depth"] == 3
        assert html["toc-title"] == "On this page"
        assert html["code-copy"] is False
        assert quarto_config["lightbox"] is False
        assert html["html-table-processing"] == "none"
        assert html["tbl-colwidths"] is False
        assert html["mermaid"] == {"theme": "default"}
        assert html["syntax-definitions"] == ["pythonsignature.xml"]
        assert html["shift-heading-level-by"] == -1
        assert reports == []

    @pytest.mark.parametrize(
        ("themes", "expected"),
        [
            ("[cosmo, custom.scss]", ["cosmo", "great-docs.scss", "custom.scss"]),
            ("[custom.scss]", ["great-docs.scss", "custom.scss"]),
            ("[cosmo, a.scss, b.css]", ["cosmo", "great-docs.scss", "a.scss", "b.css"]),
            ("[cosmo, great-docs.scss, custom.scss]", ["cosmo", "great-docs.scss", "custom.scss"]),
        ],
    )
    def test_users_style_files_follow_great_docs_theme(
        self, tmp_path: Path, themes: str, expected: list[str]
    ):
        config = write_config(tmp_path, f"site:\n  theme: {themes}\n")
        layout = Layout.make(tmp_path)
        quarto_config = _initial()
        quarto_defaults.register_site(quarto_config, config, layout, report=print)
        assert quarto_config["format"]["html"]["theme"] == expected

    def test_light_and_dark_themes_each_get_great_docs_theme(self, tmp_path: Path):
        config = write_config(
            tmp_path, "site:\n  theme:\n    light: [flatly, light.scss]\n    dark: darkly\n"
        )
        layout = Layout.make(tmp_path)
        quarto_config = _initial()
        for _ in range(2):
            quarto_defaults.register_site(quarto_config, config, layout, report=print)
            assert quarto_config["format"]["html"]["theme"] == {
                "light": ["flatly", "great-docs.scss", "light.scss"],
                "dark": ["darkly", "great-docs.scss"],
            }

    def test_site_table_widths_win(self, tmp_path: Path):
        quarto_config, _ = _register_site(tmp_path, "site:\n  tbl-colwidths: auto\n")
        assert quarto_config["format"]["html"]["tbl-colwidths"] == "auto"

    def test_bibliography_and_style_by_basename(self, tmp_path: Path):
        quarto_config, reports = _register_site(
            tmp_path, "bibliography: refs/a.bib\ncsl: styles/apa.csl\n"
        )
        assert quarto_config["bibliography"] == "a.bib"
        assert quarto_config["csl"] == "apa.csl"
        assert reports == ["Using bibliography: a.bib"]

    def test_header_include_file_is_staged(self, tmp_path: Path):
        (tmp_path / "head.html").write_text("<meta name='x'>", encoding="utf-8")
        quarto_config, _ = _register_site(tmp_path, "include_in_header:\n  - file: head.html\n")
        assert quarto_config["format"]["html"]["include-in-header"] == [
            {"file": "_includes/head.html"}
        ]
        staged = tmp_path / "great-docs" / "_includes" / "head.html"
        assert staged.read_text(encoding="utf-8") == "<meta name='x'>"

    def test_missing_header_include_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Header include file not found"):
            _register_site(tmp_path, "include_in_header:\n  - file: missing.html\n")


class TestRegisterExtensions:
    def test_filters_run_in_order_and_inventory_is_published(self):
        quarto_config: dict[str, Any] = {"project": {"resources": "data.csv"}}
        quarto_defaults.register_extensions(quarto_config, has_api_reference=True)
        assert quarto_config["filters"] == [
            "output-title",
            "details",
            "gd-lightbox",
            "interlinks",
        ]
        assert quarto_config["project"]["resources"] == ["data.csv", "objects.inv"]

    def test_site_without_api_reference_publishes_no_inventory(self):
        quarto_config: dict[str, Any] = {"project": {"resources": ["data.csv"]}}
        quarto_defaults.register_extensions(quarto_config, has_api_reference=False)
        assert quarto_config["filters"] == [
            "output-title",
            "details",
            "gd-lightbox",
            "interlinks",
        ]
        assert quarto_config["project"]["resources"] == ["data.csv"]


class TestSiteIncludes:
    """Site include entries that follow and preserve the build's entries"""

    SETTINGS = (
        "site:\n"
        "  include-in-header:\n    - text: <style>mine</style>\n"
        "  include-after-body: <script>mine()</script>\n"
    )

    def test_users_entries_follow_great_docs_entries(self, tmp_path: Path):
        data = {"text": "<script>window.__GD_TAGS_DATA__={};</script>"}
        reader = {"text": '<script src="page-tags.js"></script>'}
        quarto_config = _initial()
        quarto_config["format"]["html"]["include-after-body"] = [data, reader]
        config = write_config(tmp_path, self.SETTINGS)
        layout = Layout.make(tmp_path)

        quarto_defaults.register_site(quarto_config, config, layout, report=print)
        quarto_config["format"]["html"]["include-in-header"].append(
            {"text": "<style>great-docs</style>"}
        )
        quarto_defaults.register_site_includes(quarto_config, config)

        html = quarto_config["format"]["html"]
        assert html["include-after-body"] == [data, reader, "<script>mine()</script>"]
        assert html["include-in-header"] == [
            {"text": "<style>great-docs</style>"},
            {"text": "<style>mine</style>"},
        ]
