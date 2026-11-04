"""
Quarto project defaults, site settings and extension filters
"""

import copy
from pathlib import Path
from typing import Any

import pytest

from great_docs import GreatDocs
from great_docs._layout import Layout
from great_docs._website import inline_data, quarto_defaults, quarto_yml
from tests.support import make_run, write_config


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
        for _ in range(2):
            quarto_defaults.register_site(quarto_config, config, layout, report=print)
            assert quarto_config["format"]["html"]["theme"] == expected

    def test_site_table_widths_win(self, tmp_path: Path):
        quarto_config, _ = _register_site(tmp_path, "site:\n  tbl-colwidths: auto\n")
        assert quarto_config["format"]["html"]["tbl-colwidths"] == "auto"

    def test_second_update_changes_nothing(self, tmp_path: Path):
        settings = "site:\n  syntax-definitions: mine.xml\ninclude_in_header: '<meta x>'\n"
        once, _ = _register_site(tmp_path, settings)
        twice, _ = _register_site(tmp_path, settings, copy.deepcopy(once))
        assert twice == once
        assert once["format"]["html"]["syntax-definitions"] == ["mine.xml", "pythonsignature.xml"]
        assert once["format"]["html"]["include-in-header"] == [{"text": "<meta x>"}]

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
    def test_filters_follow_the_users_and_inventory_is_published(self):
        quarto_config: dict[str, Any] = {
            "project": {"resources": "data.csv"},
            "filters": ["mine", "details"],
        }
        quarto_defaults.register_extensions(quarto_config)
        quarto_defaults.register_extensions(quarto_config)
        assert quarto_config["filters"] == [
            "mine",
            "details",
            "output-title",
            "gd-lightbox",
            "interlinks",
        ]
        assert quarto_config["project"]["resources"] == ["data.csv", "objects.inv"]


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

        # The build's second update must preserve entries added during the first.
        for _ in range(2):
            quarto_defaults.register_site(quarto_config, config, layout, report=print)
            headers = quarto_config["format"]["html"]["include-in-header"]
            if {"text": "<style>great-docs</style>"} not in headers:
                headers.append({"text": "<style>great-docs</style>"})
            quarto_defaults.register_site_includes(quarto_config, config)

        html = quarto_config["format"]["html"]
        assert html["include-after-body"] == [data, reader, "<script>mine()</script>"]
        assert html["include-in-header"] == [
            {"text": "<style>great-docs</style>"},
            {"text": "<style>mine</style>"},
        ]

    def test_data_added_between_updates_survives(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        write_config(tmp_path, "tags:\n  enabled: true\n" + self.SETTINGS)
        docs = GreatDocs(project_path=str(tmp_path))
        docs.build_dir.mkdir(parents=True)
        quarto_yml.write_initial(docs.build_dir)

        # The build adds tag data between updates, before the script that reads it.
        docs._update_quarto_config(make_run())
        with quarto_yml.edit(docs.build_dir) as quarto_config:
            inline_data.add(quarto_config, "__GD_TAGS_DATA__", {}, before="page-tags.js")
        docs._update_quarto_config(make_run())

        html = quarto_yml.read(docs.build_dir)["format"]["html"]
        after_body = [str(entry) for entry in html["include-after-body"]]
        data = next(i for i, entry in enumerate(after_body) if "__GD_TAGS_DATA__" in entry)
        assert "page-tags.js" in after_body[data + 1]
        assert after_body[-1] == "<script>mine()</script>"
        assert html["include-in-header"][-1] == {"text": "<style>mine</style>"}
