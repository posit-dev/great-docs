"""
Build directory changes for Quarto 2 (experimental)
"""

import importlib.util
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from great_docs._apiref._format import markdown_escape, pretty_code
from great_docs._website import metadata_partial, quarto2, quarto_yml

ASSETS = Path(__file__).parents[1] / "great_docs" / "assets"


def _site_config() -> dict[str, Any]:
    return {
        "project": {"type": "website", "post-render": "scripts/share-sidebars.py"},
        "website": {
            "title": "Demo",
            "open-graph": {"image": "card.png"},
            "twitter-card": {"image": "card.png", "card-style": "summary", "site": "@demo"},
        },
        "format": {"html": {"theme": "flatly", "shift-heading-level-by": -1}},
        "filters": ["output-title", "interlinks"],
    }


class TestAdaptConfig:
    def test_moves_unsupported_settings_to_the_filter(self):
        adapted = quarto2.adapt_config(_site_config())

        assert adapted["filters"] == ["gd-quarto2", "output-title", "interlinks"]
        assert adapted["gd-quarto2"] == {
            "site-title": "Demo",
            "social-cards": {"image": "card.png", "card": "summary", "site": "@demo"},
            "shift-heading-level-by": -1,
        }
        assert adapted["website"] == {"title": "Demo", "search": {"search-json": True}}
        assert adapted["format"]["html"] == {"theme": "flatly"}
        assert adapted["project"]["post-render"] == [
            "scripts/share-sidebars.py",
            "scripts/quarto2-post-render.py",
        ]

    def test_leaves_the_configuration_unchanged(self):
        quarto_config = _site_config()
        _ = quarto2.adapt_config(quarto_config)
        assert quarto_config == _site_config()

    def test_applying_it_again_changes_nothing(self):
        adapted = quarto2.adapt_config(_site_config())
        assert quarto2.adapt_config(adapted) == adapted

    def test_keeps_disabled_search_and_search_options(self):
        disabled = quarto2.adapt_config({"website": {"search": False}})
        assert disabled["website"]["search"] is False
        options = quarto2.adapt_config({"website": {"search": {"location": "navbar"}}})
        assert options["website"]["search"] == {"location": "navbar", "search-json": True}

    def test_post_render_script_runs_last(self):
        quarto_config = {"project": {"post-render": ["scripts/quarto2-post-render.py", "b.py"]}}
        adapted = quarto2.adapt_config(quarto_config)
        assert adapted["project"]["post-render"] == ["b.py", "scripts/quarto2-post-render.py"]

    def test_written_only_for_quarto_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        quarto_yml.write(tmp_path, _site_config())
        assert "gd-quarto2" not in quarto_yml.read(tmp_path)

        monkeypatch.setenv("GREAT_DOCS_QUARTO", "q2")
        quarto_yml.write(tmp_path, _site_config())
        assert quarto_yml.read(tmp_path)["filters"][0] == "gd-quarto2"


class TestPreparePages:
    def test_adapts_sidebars_and_navbars_and_copies_the_script(self, tmp_path: Path):
        (tmp_path / "reference").mkdir()
        page = tmp_path / "reference" / "a.qmd"
        page.write_text("---\ntitle: A\nsidebar: gd-full-api\n---\n\nText\n", encoding="utf-8")
        hidden = tmp_path / "b.qmd"
        hidden.write_text("---\nsidebar: false\n---\n\nText\n", encoding="utf-8")
        navbar = tmp_path / "d.qmd"
        navbar.write_text("---\ntitle: D\nnavbar: true\n---\n\nText\n", encoding="utf-8")
        metadata = tmp_path / "reference" / "_metadata.yml"
        metadata.write_text("sidebar: api\n", encoding="utf-8")
        (tmp_path / "_site").mkdir()
        output = tmp_path / "_site" / "c.md"
        output.write_text("---\nsidebar: x\n---\n", encoding="utf-8")

        quarto2.prepare_pages(tmp_path)
        quarto2.prepare_pages(tmp_path)

        assert page.read_text(encoding="utf-8") == (
            "---\ntitle: A\nsite-sidebar: gd-full-api\n---\n\nText\n"
        )
        assert hidden.read_text(encoding="utf-8") == "---\nsidebar: false\n---\n\nText\n"
        assert navbar.read_text(encoding="utf-8") == "---\ntitle: D\n---\n\nText\n"
        assert metadata.read_text(encoding="utf-8") == "site-sidebar: api\n"
        assert output.read_text(encoding="utf-8") == "---\nsidebar: x\n---\n"
        assert (tmp_path / "scripts" / "quarto2-post-render.py").read_bytes() == (
            ASSETS / "quarto2-post-render.py"
        ).read_bytes()

    def test_rewrites_definition_lists_in_the_body(self, tmp_path: Path):
        page = tmp_path / "a.qmd"
        page.write_text("---\ntitle: A\n---\n\nterm\n:   definition\n", encoding="utf-8")
        quarto2.prepare_pages(tmp_path)
        assert page.read_text(encoding="utf-8") == (
            "---\ntitle: A\n---\n\n::: {.definition-list}\n* term\n  - definition\n:::\n"
        )


def _dedent(s: str) -> str:
    return textwrap.dedent(s).lstrip("\n")


class TestDefinitionLists:
    def test_tight_items_share_one_list(self):
        markdown = _dedent(
            """
            ::: {.doc-definition-items}
            <code>a</code>
            :   Required.

            <code>b</code>
            :   &nbsp;

            :::
            """
        )
        assert quarto2.definition_lists(markdown) == _dedent(
            """
            ::: {.doc-definition-items}
            ::: {.definition-list}
            * <code>a</code>
              - Required.
            * <code>b</code>
              - &nbsp;
            :::

            :::
            """
        )

    def test_loose_items_empty_and_several_definitions(self):
        markdown = "a\n\n:   first\n\n:   second\n\nb\n\n:   \n\nAfter\n"
        assert quarto2.definition_lists(markdown) == (
            "::: {.definition-list}\n* a\n  - first\n  - second\n* b\n  -\n:::\n\nAfter\n"
        )

    def test_definition_with_several_blocks(self):
        markdown = _dedent(
            """
            term
            :   Text
                continued

                ```python
                code
                ```

            Paragraph
            """
        )
        assert quarto2.definition_lists(markdown) == _dedent(
            """
            ::: {.definition-list}
            * term
              - Text
                continued

                ```python
                code
                ```
            :::

            Paragraph
            """
        )

    def test_lazy_continuation_line(self):
        markdown = "term\n:   Text\nmore text\n"
        assert quarto2.definition_lists(markdown) == (
            "::: {.definition-list}\n* term\n  - Text\n    more text\n:::\n"
        )

    @pytest.mark.parametrize(
        "markdown",
        [
            "```\nterm\n:   in code\n```\n",
            "A paragraph\nterm\n:   needs a blank line before the term\n",
            ":::\n",
            "Plain text\n\nMore text\n",
        ],
    )
    def test_leaves_other_markdown_alone(self, markdown: str):
        assert quarto2.definition_lists(markdown) == markdown


def _post_render() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "quarto2_post_render", ASSETS / "quarto2-post-render.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPostRender:
    def test_rewrites_root_relative_addresses_in_tags(self):
        html = (
            '<link href="/a.css"><script src="/b.js">if (x < "/y") {}</script>'
            '<a href="//cdn.example/c">c</a><img src="/d.png">'
            '<!-- <a href="/e"> --><style>a { background: url("/f.png"); }</style>'
        )
        assert _post_render().rewrite(html, "../") == (
            '<link href="../a.css"><script src="../b.js">if (x < "/y") {}</script>'
            '<a href="//cdn.example/c">c</a><img src="../d.png">'
            '<!-- <a href="/e"> --><style>a { background: url("/f.png"); }</style>'
        )

    def test_root_page_gets_a_dot_prefix(self):
        assert _post_render().rewrite("<a href='/x.html'>x</a>", "") == ("<a href='./x.html'>x</a>")

    def test_moves_the_filter_markers_onto_html_and_body(self):
        html = (
            '<html lang="ar">\n<head>\n<meta name="gd-dir" content="rtl">\n'
            '<meta name="gd-body-classes" content="gd-blog-index fullcontent">\n</head>\n'
            '<body class="fullcontent nav-fixed">\n'
        )
        assert _post_render().apply_markers(html) == (
            '<html lang="ar" dir="rtl">\n<head>\n</head>\n'
            '<body class="fullcontent nav-fixed gd-blog-index">\n'
        )

    def test_markers_replace_a_direction_and_add_a_class_attribute(self):
        html = (
            '<html dir="ltr"><meta name="gd-dir" content="rtl">'
            '<meta name="gd-body-classes" content="a"><body>'
        )
        assert _post_render().apply_markers(html) == '<html dir="rtl"><body class="a">'

    def test_page_without_markers_is_unchanged(self):
        html = '<html lang="en"><body class="x">'
        assert _post_render().apply_markers(html) == html

    def test_rewrites_the_pages_quarto_listed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        site = tmp_path / "_site"
        (site / "guide").mkdir(parents=True)
        (site / "index.html").write_text('<a href="/guide/a.html">', encoding="utf-8")
        (site / "guide" / "a.html").write_text('<script src="/x.js"></script>', encoding="utf-8")
        (site / "other.html").write_text('<a href="/x">', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("QUARTO_PROJECT_OUTPUT_DIR", "_site")
        monkeypatch.setenv("QUARTO_PROJECT_OUTPUT_FILES", "_site/index.html\n_site/guide/a.html")
        monkeypatch.delenv("QUARTO_PROJECT_RENDER_ALL", raising=False)
        monkeypatch.delenv("QUARTO_USE_FILE_FOR_PROJECT_OUTPUT_FILES", raising=False)

        module = _post_render()
        module.build_dir = tmp_path
        module.main()

        assert (site / "index.html").read_text(encoding="utf-8") == '<a href="./guide/a.html">'
        assert (site / "guide" / "a.html").read_text(encoding="utf-8") == (
            '<script src="../x.js"></script>'
        )
        assert (site / "other.html").read_text(encoding="utf-8") == '<a href="/x">'


class TestMetadataPartial:
    def test_constant_lines(self):
        partial = (
            '<meta charset="utf-8" />\n'
            "<style>a{}</style>\n"
            "$if(robots)$\n"
            '<meta name="robots" content="$robots$" />\n'
            "$endif$\n"
            '<meta name="viewport" content="x" />\n'
            '<meta name="gd-i18n" content="a$$b">\n'
            "<title>$pagetitle$</title>\n"
        )
        assert metadata_partial.constant_lines(partial) == [
            "<style>a{}</style>",
            '<meta name="gd-i18n" content="a$b">',
        ]


class TestEscapes:
    def test_quarto_1_escapes_only_a_leading_underscore(self):
        assert markdown_escape("__init__") == r"\__init__"
        assert pretty_code('"{{"') == "[&quot;{{&quot;]{.st}"

    def test_quarto_2_escapes_every_underscore_and_doubled_braces(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("GREAT_DOCS_QUARTO", "q2")
        assert markdown_escape("__init__") == r"\_\_init\_\_"
        assert markdown_escape("a*b") == r"a\*b"
        assert pretty_code('"{{"') == "[&quot;&#123;&#123;&quot;]{.st}"
        assert pretty_code("{'a': 'b'}") == "{[&apos;a&apos;]{.st}: [&apos;b&apos;]{.st}}"
