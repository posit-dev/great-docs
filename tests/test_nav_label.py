"""
Tests for reference navigation titles and translated prefixes

Disabling breadcrumbs lets Quarto supply the page title in the narrow-screen
navigation bar. CSS adds `API /`, `CLI /` or `MCP /` using custom properties
declared in the site's language.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from great_docs._mcp_docs import (
    _generate_mcp_index_page,
    _generate_prompt_page,
    _generate_resource_page,
    _generate_resource_template_page,
    _generate_tool_page,
)
from great_docs._website.navigation import label
from great_docs.config import Config
from great_docs.core import GreatDocs


def _front_matter(page: str) -> dict:
    """
    Parse the YAML front matter of a generated page

    Parameters
    ----------
    page
        Page source beginning with YAML enclosed by `---` lines.

    Returns
    -------
    :
        The parsed front matter.
    """
    _, block, _ = page.split("---\n", 2)
    return yaml.safe_load(block)


_MCP_SERVER_INFO = {
    "name": "my-server",
    "tools": [],
    "resources": [],
    "prompts": [],
    "resource_templates": [],
    "instructions": None,
    "completions_enabled": False,
}


@pytest.mark.parametrize(
    "page",
    [
        _generate_mcp_index_page("my-server", _MCP_SERVER_INFO, []),
        _generate_tool_page({"name": "t", "description": "", "input_schema": {}}, "my-server"),
        _generate_resource_page(
            {"name": "r", "uri": "gd://r", "description": "", "mime_type": None}, "my-server"
        ),
        _generate_resource_template_page(
            {"name": "rt", "uri_template": "gd://{x}", "description": "", "mime_type": None},
            "my-server",
        ),
        _generate_prompt_page(
            {"name": "p", "description": "", "arguments": [], "messages": []}, "my-server"
        ),
    ],
    ids=["index", "tool", "resource", "template", "prompt"],
)
def test_mcp_pages_turn_breadcrumbs_off(page: str):
    """Verify that every MCP reference page disables breadcrumbs"""
    assert _front_matter(page)["bread-crumbs"] is False


def test_cli_pages_turn_breadcrumbs_off():
    """Verify that CLI index and command pages disable breadcrumbs"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        index = docs._generate_cli_index_page(
            {"name": "tool", "entry_point_name": "tool", "is_group": True, "commands": []},
            "tool",
        )
        command = docs._generate_cli_command_page(
            {
                "name": "build",
                "full_path": "tool build",
                "help": "",
                "help_text": "",
                "description": "",
                "examples": [],
                "options": [],
                "arguments": [],
                "commands": [],
                "is_group": False,
            },
            is_main=False,
        )

    assert _front_matter(index)["bread-crumbs"] is False
    assert _front_matter(command)["bread-crumbs"] is False


def test_prefixes_are_declared_from_the_translations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Verify that translated prefixes are escaped and added to existing headers

    All bundled languages use `API` and `CLI`. Distinct patched values verify
    that prefixes come from the translation bundle. Quotes, backslashes,
    newlines and `<` also exercise CSS and HTML escaping.
    """
    monkeypatch.setattr(
        label, "get_translations_bundle", lambda language: {"api": 'A"P\\I', "cli": "C<L\nI"}
    )
    config = Config(tmp_path)
    quarto_config: dict = {"format": {"html": {"include-in-header": "existing.html"}}}

    label.register(quarto_config, config)

    assert quarto_config["format"]["html"]["include-in-header"] == [
        "existing.html",
        {
            "text": (
                "<style>:root{"
                '--gd-nav-prefix-api:"A\\"P\\\\I";'
                '--gd-nav-prefix-cli:"C\\3c L\\a I";'
                '--gd-nav-prefix-mcp:"MCP";'
                "}</style>"
            )
        },
    ]


@pytest.mark.parametrize(
    ("headers", "kept"),
    [({"text": "<meta>"}, [{"text": "<meta>"}]), (None, [])],
    ids=["mapping", "empty"],
)
def test_prefixes_join_any_include_in_header_form(tmp_path: Path, headers: object, kept: list):
    """Verify that navigation prefixes are added to mapping or empty header entries"""
    quarto_config: dict = {"format": {"html": {"include-in-header": headers}}}

    label.register(quarto_config, Config(tmp_path))

    *existing, added = quarto_config["format"]["html"]["include-in-header"]
    assert existing == kept
    assert added["text"].startswith("<style>:root{--gd-nav-prefix-api:")


def test_registering_twice_keeps_one_prefix_style(tmp_path: Path):
    """Verify that a repeated pass leaves a single navigation prefix style"""
    quarto_config: dict = {"format": {"html": {"include-in-header": [{"text": "<meta>"}]}}}
    config = Config(tmp_path)

    label.register(quarto_config, config)
    label.register(quarto_config, config)

    headers = quarto_config["format"]["html"]["include-in-header"]
    assert [h for h in headers if "--gd-nav-prefix-api" in str(h)] == headers[1:]
    assert len(headers) == 2


def test_registering_replaces_prefixes_of_another_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Verify that changing the language replaces the navigation prefix style"""
    quarto_config: dict = {"format": {"html": {}}}
    config = Config(tmp_path)

    monkeypatch.setattr(label, "get_translations_bundle", lambda lang: {"api": "A1", "cli": "C1"})
    label.register(quarto_config, config)
    monkeypatch.setattr(label, "get_translations_bundle", lambda lang: {"api": "A2", "cli": "C2"})
    label.register(quarto_config, config)

    (header,) = quarto_config["format"]["html"]["include-in-header"]
    assert '"A2"' in header["text"]
