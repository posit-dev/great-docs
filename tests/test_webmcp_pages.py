"""Tests for preparing authored pages for the WebMCP tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from great_docs._build import generated
from great_docs._build.steps import Skipped
from great_docs._project.layout import Layout
from great_docs._website.ai_agents import webmcp_pages
from great_docs._yaml import add_body_class, split_front_matter
from tests.support import write_config, write_pyproject

CLASS = webmcp_pages.NO_WEBMCP_CLASS


def _classes(content: str) -> list[str]:
    front_matter, _ = split_front_matter(content)
    return " ".join(front_matter.strings("body-classes")).split()


class TestAddBodyClass:
    def test_a_page_without_front_matter_gains_a_block(self):
        content = add_body_class("# Title\n\nText.\n", CLASS)

        assert content == f'---\nbody-classes: "{CLASS}"\n---\n\n# Title\n\nText.\n'

    def test_a_page_without_body_classes_gains_the_option(self):
        content = add_body_class("---\ntitle: Intro # the title\n---\n\nText.\n", CLASS)

        assert content == f'---\ntitle: Intro # the title\nbody-classes: "{CLASS}"\n---\n\nText.\n'

    def test_an_empty_block_gains_the_option(self):
        content = add_body_class("---\n---\n\nText.\n", CLASS)

        assert _classes(content) == [CLASS]

    @pytest.mark.parametrize(
        "line",
        ["body-classes: wide dark", 'body-classes: "wide dark"', "body-classes: 'wide dark'"],
    )
    def test_a_string_value_keeps_its_classes_and_the_other_lines(self, line: str):
        source = f"---\n# comment\ntitle: Intro\n{line}\ntoc: false\n---\n\nText.\n"

        content = add_body_class(source, CLASS)

        assert _classes(content) == ["wide", "dark", CLASS]
        assert content.startswith("---\n# comment\ntitle: Intro\n")
        assert "toc: false\n---\n\nText.\n" in content

    def test_a_list_value_becomes_a_string(self):
        source = "---\ntitle: Intro\nbody-classes:\n  - wide\n  - dark\n---\n\nText.\n"

        content = add_body_class(source, CLASS)

        assert _classes(content) == ["wide", "dark", CLASS]
        assert split_front_matter(content)[0].string("title") == "Intro"
        assert content.endswith("---\n\nText.\n")

    def test_a_block_scalar_is_rewritten_rather_than_broken(self):
        source = "---\nbody-classes: >\n  wide\n  dark\n---\n\nText.\n"

        content = add_body_class(source, CLASS)

        assert _classes(content) == ["wide", "dark", CLASS]

    def test_a_page_that_has_the_class_is_unchanged(self):
        source = f"---\nbody-classes: wide {CLASS}\n---\n\nText.\n"

        assert add_body_class(source, CLASS) == source

    def test_invalid_front_matter_is_unchanged(self):
        source = "---\ntitle: [unclosed\n---\n\nText.\n"

        assert add_body_class(source, CLASS) == source


def _project(tmp_path: Path, settings: dict[str, object]) -> Layout:
    write_pyproject(tmp_path, "example")
    write_config(tmp_path, settings)
    layout = Layout.make(tmp_path)
    layout.build_dir.mkdir()
    return layout


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestPrepare:
    def test_the_step_is_skipped_when_webmcp_is_off(self, tmp_path: Path):
        layout = _project(tmp_path, {})
        _write(layout.build_dir / "user-guide" / "intro.qmd", "---\nwebmcp: false\n---\n")

        outcome = generated.webmcp_pages(layout.load_config(), layout)

        assert outcome == Skipped("WebMCP not enabled")
        assert not (layout.build_dir / webmcp_pages.FACTS_FILE).exists()
        assert CLASS not in (layout.build_dir / "user-guide" / "intro.qmd").read_text()

    def test_an_opted_out_page_gains_the_class_and_others_are_untouched(self, tmp_path: Path):
        layout = _project(tmp_path, {"webmcp": True})
        build_dir = layout.build_dir
        opted_out = _write(build_dir / "user-guide" / "secret.qmd", "---\nwebmcp: false\n---\n")
        kept = "---\ntitle: Intro\nwebmcp: true\n---\n\nText.\n"
        _write(build_dir / "user-guide" / "intro.qmd", kept)

        outcome = generated.webmcp_pages(layout.load_config(), layout)

        assert outcome == "WebMCP pages prepared (1 opted out)"
        assert _classes(opted_out.read_text()) == [CLASS]
        assert (build_dir / "user-guide" / "intro.qmd").read_text() == kept

    def test_the_facts_file_lists_every_page_source(self, tmp_path: Path):
        layout = _project(tmp_path, {"webmcp": True})
        build_dir = layout.build_dir
        _write(build_dir / "index.qmd", "---\ntitle: Home\n---\n")
        _write(
            build_dir / "user-guide" / "intro.qmd",
            "---\ntitle: Intro\ndescription: Start here\ndraft: true\ntags: [setup, basics]\n"
            "status: new\n---\n",
        )
        _write(build_dir / "notes" / "plain.md", "# Plain\n")
        _write(build_dir / "_private" / "hidden.qmd", "---\ntitle: Hidden\n---\n")
        _write(build_dir / ".quarto" / "cache.qmd", "")
        _write(build_dir / "user-guide" / "secret.qmd", "---\nwebmcp: false\n---\n")

        facts = webmcp_pages.prepare(layout.load_config(), layout)

        data = json.loads((build_dir / webmcp_pages.FACTS_FILE).read_text())
        assert data["schema"] == 1
        assert data["sections"] == [{"id": "user-guide", "title": "User Guide", "kind": "guide"}]
        defaults = {
            "title": None,
            "description": None,
            "section": "",
            "tags": [],
            "status": None,
            "date": None,
            "draft": False,
            "webmcp": True,
            "listed": True,
        }
        assert data["pages"] == [
            {**defaults, "path": "index.html", "source": "index.qmd", "title": "Home"},
            {**defaults, "path": "notes/plain.html", "source": "notes/plain.md"},
            {
                **defaults,
                "path": "user-guide/intro.html",
                "source": "user-guide/intro.qmd",
                "title": "Intro",
                "description": "Start here",
                "section": "user-guide",
                "tags": ["setup", "basics"],
                "status": "new",
                "draft": True,
            },
            {
                **defaults,
                "path": "user-guide/secret.html",
                "source": "user-guide/secret.qmd",
                "section": "user-guide",
                "webmcp": False,
            },
        ]
        assert [page.path for page in facts.pages] == [page["path"] for page in data["pages"]]

    def test_the_facts_file_reads_back_as_written(self, tmp_path: Path):
        layout = _project(tmp_path, {"webmcp": True})
        _write(layout.build_dir / "user-guide" / "intro.qmd", "---\ntags: [a, b]\n---\n")

        facts = webmcp_pages.prepare(layout.load_config(), layout)

        assert webmcp_pages.read(layout.build_dir) == facts

    @pytest.mark.parametrize("content", ["", "[]", '{"schema": 99, "sections": [], "pages": []}'])
    def test_an_unreadable_or_foreign_facts_file_reads_as_none(self, tmp_path: Path, content: str):
        if content:
            _write(tmp_path / webmcp_pages.FACTS_FILE, content)

        assert webmcp_pages.read(tmp_path) is None

    def test_a_blog_section_has_the_blog_kind(self, tmp_path: Path):
        sections = [
            {"title": "News", "dir": "news", "type": "blog"},
            {"title": "", "dir": "examples"},
        ]
        layout = _project(tmp_path, {"webmcp": True, "sections": sections})
        _write(
            layout.build_dir / "news" / "launch.qmd", "---\ntitle: Launch\ndate: 2026-01-02\n---\n"
        )
        _write(layout.build_dir / "examples" / "one.qmd", "---\ntitle: One\n---\n")

        facts = webmcp_pages.prepare(layout.load_config(), layout)

        assert facts.sections == (
            webmcp_pages.SectionFacts("news", "News", "blog"),
            webmcp_pages.SectionFacts("examples", "examples", "guide"),
        )
        sections_by_path = {page.path: page.section for page in facts.pages}
        assert sections_by_path == {"news/launch.html": "news", "examples/one.html": "examples"}
        assert facts.pages[1].date == "2026-01-02"

    def test_a_listed_false_mapping_keeps_tools_but_leaves_the_manifest(self, tmp_path: Path):
        layout = _project(tmp_path, {"webmcp": True})
        page = _write(layout.build_dir / "draft.qmd", "---\nwebmcp:\n  listed: false\n---\n")

        facts = webmcp_pages.prepare(layout.load_config(), layout)

        assert [(fact.webmcp, fact.listed) for fact in facts.pages] == [(True, False)]
        assert CLASS not in page.read_text()

    def test_only_a_false_value_opts_out(self, tmp_path: Path):
        layout = _project(tmp_path, {"webmcp": True})
        for name, value in [("no", "no"), ("off", '"false"'), ("null", "null")]:
            _write(layout.build_dir / f"{name}.qmd", f"---\nwebmcp: {value}\n---\n")

        facts = webmcp_pages.prepare(layout.load_config(), layout)

        assert all(page.webmcp and page.listed for page in facts.pages)
