"""
Build directory changes for Quarto 2 (experimental)
"""

import importlib.util
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from great_docs._apiref._format import (
    escape_code_text,
    escape_emphasis,
    fence_indented_code,
    format_value,
    markdown_escape,
    pretty_code,
)
from great_docs._cliref import render as cli_render
from great_docs._website import metadata_partial, quarto2, quarto_yml
from tests.support import mock_config

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

        assert adapted["quarto-required"] == "^2"
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

    def test_keeps_card_settings_for_quarto_2_that_writes_the_tags(self):
        adapted = quarto2.adapt_config(_site_config(), native_social_cards=True)

        assert adapted["gd-quarto2"]["social-cards"] == {"native": True}
        assert adapted["website"]["open-graph"] == {"image": "card.png"}
        assert adapted["website"]["twitter-card"]["card-style"] == "summary"
        assert quarto2.adapt_config(adapted, native_social_cards=True) == adapted
        no_cards = quarto2.adapt_config({"website": {"title": "Demo"}}, native_social_cards=True)
        assert "social-cards" not in no_cards["gd-quarto2"]

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
        assert escape_emphasis("*Ts") == "*Ts"
        assert escape_code_text("_DEFAULT * 2") == "_DEFAULT * 2"
        assert format_value("'$HOME'") == "[&quot;$HOME&quot;]{.st}"
        assert pretty_code('"{{"') == "[&quot;{{&quot;]{.st}"

    def test_quarto_2_escapes_every_underscore_and_doubled_braces(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("GREAT_DOCS_QUARTO", "q2")
        assert markdown_escape("__init__") == r"\_\_init\_\_"
        assert markdown_escape("a*b") == r"a\*b"
        assert escape_emphasis("*Ts") == r"\*Ts"
        assert escape_code_text("_DEFAULT * 2") == r"\_DEFAULT \* 2"
        assert format_value("'$HOME'") == r"[&quot;\$HOME&quot;]{.st}"
        assert pretty_code('"{{"') == "[&quot;&#123;&#123;&quot;]{.st}"
        assert pretty_code("{'a': 'b'}") == "{[&apos;a&apos;]{.st}: [&apos;b&apos;]{.st}}"


class TestCliHelp:
    def _page(self) -> str:
        cli_info = {
            "name": "mycli",
            "short_help": "Build docs/_site.",
            "description": "Build docs/_site.",
            "options": [
                {
                    "name": "--shell",
                    "name_display": "--shell",
                    "required": True,
                    "envvar": "MY_SHELL",
                    "help": "Shell to spawn (default: $SHELL), as with 'my_shell'",
                }
            ],
            "arguments": [],
            "commands": [],
        }
        return cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)

    def test_quarto_1_writes_the_help_unchanged(self):
        page = self._page()
        assert "Build docs/_site." in page
        assert (
            ":   **Required.** Shell to spawn (default: $SHELL), as with `my_shell` "
            "Environment variable: `MY_SHELL`."
        ) in page

    def test_quarto_2_escapes_the_help_outside_code(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GREAT_DOCS_QUARTO", "q2")
        page = self._page()
        assert r"Build docs/\_site." in page
        assert (
            r":   **Required.** Shell to spawn (default: \$SHELL), as with `my_shell` "
            "Environment variable: `MY_SHELL`."
        ) in page
        assert cli_render.escape_markup("``a ` b_c`` d_e") == r"``a ` b_c`` d\_e"


class TestFenceIndentedCode:
    @pytest.fixture(autouse=True)
    def _quarto_2(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GREAT_DOCS_QUARTO", "q2")

    def test_fences_an_indented_block(self):
        markdown = ".. math::\n\n    \\sqrt{x_1 * x_2}\n\n      y\n\nAfter\n"
        assert fence_indented_code(markdown) == (
            ".. math::\n\n```\n\\sqrt{x_1 * x_2}\n\n  y\n```\n\nAfter\n"
        )

    def test_fences_a_block_at_the_start_and_end(self):
        assert fence_indented_code("\tcode\n    more\n") == "```\ncode\nmore\n```\n"

    def test_fence_is_longer_than_backticks_in_the_code(self):
        assert fence_indented_code("Text\n\n    a = ```b```") == "Text\n\n````\na = ```b```\n````"

    @pytest.mark.parametrize(
        "markdown",
        [
            "Text\n    continued, without a blank line\n",
            "- item\n\n    continued item\n\nText\n",
            "1. item\n\n    continued item\n",
            "term\n:   definition\n\n    continued definition\n",
            "```python\n\n    indented in a fence\n```\n",
            "~~~~\n```\n\n    in a fence\n~~~~\n",
        ],
    )
    def test_leaves_other_markdown_alone(self, markdown: str):
        assert fence_indented_code(markdown) == markdown

    def test_fences_after_a_list_ends(self):
        markdown = "- item\n\nText\n\n    code\n"
        assert fence_indented_code(markdown) == "- item\n\nText\n\n```\ncode\n```\n"

    def test_quarto_1_leaves_the_text_unchanged(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GREAT_DOCS_QUARTO")
        assert fence_indented_code("Text\n\n    code\n") == "Text\n\n    code\n"
