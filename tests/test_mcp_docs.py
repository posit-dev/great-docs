"""Tests for _mcpref/reference.py (pure page-generation functions) and _mcpref/runner.py."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.shared.exceptions import MCPError

from great_docs._mcpref.reference import (
    _dump,
    _extract_tools_from_source,
    _first_sentence,
    _generate_mcp_index_page,
    _generate_prompt_page,
    _generate_resource_page,
    _generate_resource_template_page,
    _generate_tool_page,
    _json_value,
    _messages_for_prompt,
    _schema_type_display,
    categorize_tools,
    discover_mcp_server,
    generate_mcp_manifest,
    generate_mcp_reference_pages,
    locate_server,
)

# ---------------------------------------------------------------------------
# _dump
# ---------------------------------------------------------------------------


class TestDump:
    def test_none_returns_empty_dict(self):
        assert _dump(None) == {}

    def test_dict_passthrough(self):
        d = {"a": 1, "b": 2}
        assert _dump(d) == d

    def test_model_dump_called_with_alias(self):
        obj = MagicMock()
        obj.model_dump.return_value = {"serverInfo": {"name": "my-server"}}
        assert _dump(obj) == {"serverInfo": {"name": "my-server"}}
        obj.model_dump.assert_called_once_with(by_alias=True, exclude_none=True)

    def test_serialisation_failure_propagates(self):
        obj = MagicMock(spec=["model_dump", "dict"])
        obj.model_dump.side_effect = ValueError("cannot serialise")
        obj.dict.return_value = {"key": "val"}
        with pytest.raises(ValueError, match="cannot serialise"):
            _dump(obj)


# ---------------------------------------------------------------------------
# locate_server
# ---------------------------------------------------------------------------


class TestLocateServer:
    def _make_module(self, **attrs) -> types.ModuleType:
        mod = types.ModuleType("fake_mod")
        for k, v in attrs.items():
            setattr(mod, k, v)
        return mod

    def test_explicit_var_found(self):
        obj = object()
        mod = self._make_module(my_server=obj)
        assert locate_server(mod, "my_server") is obj

    def test_explicit_var_missing_returns_none(self):
        mod = self._make_module()
        assert locate_server(mod, "missing_server") is None

    def test_auto_detect_server_type(self):
        mock_server = MagicMock()
        type(mock_server).__name__ = "Server"
        type(mock_server).__module__ = "mcp.server"
        mod = self._make_module(srv=mock_server)
        assert locate_server(mod, None) is mock_server

    def test_auto_detect_fastmcp_type(self):
        mock_server = MagicMock()
        type(mock_server).__name__ = "FastMCP"
        type(mock_server).__module__ = "mcp.fastmcp"
        mod = self._make_module(app=mock_server)
        assert locate_server(mod, None) is mock_server

    def test_auto_detect_mcpserver_type(self):
        mock_server = MagicMock()
        type(mock_server).__name__ = "MCPServer"
        type(mock_server).__module__ = "mcp.server.mcpserver.server"
        mod = self._make_module(app=mock_server)
        assert locate_server(mod, None) is mock_server

    def test_auto_detect_nothing_returns_none(self):
        mod = self._make_module(x=23, y="hello")
        assert locate_server(mod, None) is None


# ---------------------------------------------------------------------------
# _messages_for_prompt
# ---------------------------------------------------------------------------


class TestMessagesForPrompt:
    def test_empty_list_returns_empty(self):
        assert _messages_for_prompt([]) == []

    def test_none_returns_empty(self):
        assert _messages_for_prompt(None) == []  # type: ignore[arg-type]

    def test_single_message_with_text(self):
        messages = [{"role": "user", "content": {"text": "Hello"}}]
        result = _messages_for_prompt(messages)
        assert result == [{"role": "user", "text": "Hello"}]

    def test_message_with_list_content(self):
        messages = [
            {
                "role": "assistant",
                "content": [{"text": "Part 1"}, {"text": "Part 2"}],
            }
        ]
        result = _messages_for_prompt(messages)
        assert result == [
            {"role": "assistant", "text": "Part 1"},
            {"role": "assistant", "text": "Part 2"},
        ]

    def test_skips_blocks_with_no_text(self):
        messages = [{"role": "user", "content": {"text": ""}}]
        assert _messages_for_prompt(messages) == []

    def test_non_dict_content_block_ignored(self):
        messages = [{"role": "user", "content": [None, {"text": "hi"}]}]
        result = _messages_for_prompt(messages)
        assert result == [{"role": "user", "text": "hi"}]


# ---------------------------------------------------------------------------
# _first_sentence
# ---------------------------------------------------------------------------


class TestFirstSentence:
    def test_single_sentence(self):
        assert _first_sentence("Hello world.") == "Hello world."

    def test_multi_sentence(self):
        assert _first_sentence("First sentence. Second sentence.") == "First sentence."

    def test_adds_period_when_missing(self):
        assert _first_sentence("No period") == "No period."

    def test_empty_string(self):
        assert _first_sentence("") == ""

    def test_no_double_period(self):
        result = _first_sentence("One.")
        assert result == "One."


# ---------------------------------------------------------------------------
# _schema_type_display
# ---------------------------------------------------------------------------


class TestSchemaTypeDisplay:
    def test_array_type_with_items(self):
        assert (
            _schema_type_display({"type": "array", "items": {"type": "string"}}) == "array[string]"
        )

    def test_array_type_without_items(self):
        assert _schema_type_display({"type": "array"}) == "array[any]"

    def test_object_type(self):
        assert _schema_type_display({"type": "object"}) == "object"

    def test_enum_type(self):
        assert _schema_type_display({"type": "string", "enum": ["a", "b"]}) == "string (enum)"

    def test_plain_type(self):
        assert _schema_type_display({"type": "integer"}) == "integer"

    def test_missing_type_defaults_to_any(self):
        assert _schema_type_display({}) == "any"


# ---------------------------------------------------------------------------
# _json_value
# ---------------------------------------------------------------------------


class TestJsonValue:
    def test_true(self):
        assert _json_value(True) == "true"

    def test_false(self):
        assert _json_value(False) == "false"

    def test_string(self):
        assert _json_value("hello") == '"hello"'

    def test_none(self):
        assert _json_value(None) == "null"

    def test_integer(self):
        assert _json_value(23) == "23"

    def test_float(self):
        assert _json_value(3.14) == "3.14"


# ---------------------------------------------------------------------------
# categorize_tools
# ---------------------------------------------------------------------------


class TestCategorizeTools:
    def _tool(self, name: str) -> dict:
        return {"name": name, "description": "", "input_schema": {}}

    def test_manual_categories_assigns_correctly(self):
        tools = [self._tool("pkg_load"), self._tool("pkg_validate"), self._tool("pkg_other")]
        sections = categorize_tools(
            tools,
            manual_categories={"Loading": ["pkg_load"], "Validation": ["pkg_validate"]},
        )
        titles = [s["title"] for s in sections]
        assert "Loading" in titles
        assert "Validation" in titles

    def test_manual_categories_unassigned_go_to_other(self):
        tools = [self._tool("pkg_load"), self._tool("pkg_extra")]
        sections = categorize_tools(
            tools,
            manual_categories={"Loading": ["pkg_load"]},
        )
        other = next(s for s in sections if s["title"] == "Other Tools")
        assert any(t["name"] == "pkg_extra" for t in other["tools"])

    def test_auto_groups_by_prefix(self):
        tools = [self._tool("pkg_load_a"), self._tool("pkg_load_b"), self._tool("pkg_validate_x")]
        sections = categorize_tools(tools)
        # load group has 2 → should form a section
        section_titles = [s["title"] for s in sections]
        assert "Load" in section_titles

    def test_auto_small_groups_go_to_general(self):
        # Single-word names each get their own group of 1 → all go to "General"
        tools = [self._tool("alpha"), self._tool("beta")]
        sections = categorize_tools(tools)
        general = next((s for s in sections if s["title"] == "General"), None)
        assert general is not None

    def test_empty_tools_returns_empty(self):
        assert categorize_tools([]) == []


# ---------------------------------------------------------------------------
# _generate_mcp_index_page
# ---------------------------------------------------------------------------


class TestGenerateMcpIndexPage:
    def _server_info(self, **overrides) -> dict:
        base = {
            "name": "test-server",
            "tools": [],
            "resources": [],
            "prompts": [],
            "resource_templates": [],
            "instructions": None,
            "completions_enabled": False,
        }
        base.update(overrides)
        return base

    def test_contains_capability_tiles(self):
        info = self._server_info(tools=[{"name": "t", "description": "desc", "input_schema": {}}])
        content = _generate_mcp_index_page("test-server", info, [])
        assert "mcp-capability-tiles" in content

    def test_instructions_block_present_when_set(self):
        info = self._server_info(instructions="Do this first.")
        content = _generate_mcp_index_page("test-server", info, [])
        assert "Do this first." in content

    def test_no_instructions_block_when_absent(self):
        info = self._server_info(instructions=None)
        content = _generate_mcp_index_page("test-server", info, [])
        assert "Do this first." not in content

    def test_completions_note_when_enabled(self):
        info = self._server_info(completions_enabled=True)
        sections: list = []
        content = _generate_mcp_index_page("test-server", info, sections)
        assert "mcp-completions" in content.lower() or "completions" in content.lower()

    def test_resources_section_present(self):
        info = self._server_info(
            resources=[
                {
                    "name": "config",
                    "uri": "gd://config",
                    "description": "Config.",
                    "mime_type": None,
                }
            ]
        )
        content = _generate_mcp_index_page("test-server", info, [])
        assert "config" in content

    def test_tool_link_included_in_section(self):
        info = self._server_info()
        sections = [
            {
                "title": "Utils",
                "tools": [
                    {"name": "my_tool", "description": "Does something.", "input_schema": {}}
                ],
            }
        ]
        content = _generate_mcp_index_page("test-server", info, sections)
        assert "my_tool" in content
        assert "### Utils" in content


# ---------------------------------------------------------------------------
# _generate_tool_page
# ---------------------------------------------------------------------------


class TestGenerateToolPage:
    def _tool(self, **overrides) -> dict:
        base = {"name": "do_thing", "description": "Does a thing.", "input_schema": {}}
        base.update(overrides)
        return base

    def test_signature_block_has_function_class(self):
        tool = self._tool(
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The query."}},
            }
        )
        content = _generate_tool_page(tool, "my-server")
        assert "::: {.doc-signature .doc-function}" in content

    def test_title_in_frontmatter(self):
        content = _generate_tool_page(self._tool(), "my-server")
        assert 'title: "do_thing"' in content

    def test_tool_name_in_heading(self):
        content = _generate_tool_page(self._tool(), "my-server")
        assert "do_thing" in content

    def test_description_rendered(self):
        content = _generate_tool_page(self._tool(description="Short desc."), "my-server")
        assert "Short desc." in content

    def test_extended_description_rendered(self):
        tool = self._tool(description="First sentence. Second sentence with more detail.")
        content = _generate_tool_page(tool, "my-server")
        assert "Second sentence with more detail." in content

    def test_required_param_rendered(self):
        tool = self._tool(
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The query."}},
                "required": ["query"],
            }
        )
        content = _generate_tool_page(tool, "my-server")
        assert "query" in content
        assert "required" in content

    def test_optional_param_with_default(self):
        tool = self._tool(
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max items.", "default": 10}
                },
            }
        )
        content = _generate_tool_page(tool, "my-server")
        assert "limit" in content
        assert "10" in content

    def test_no_parameters_section_without_schema(self):
        content = _generate_tool_page(self._tool(), "my-server")
        assert "doc-parameters" not in content

    def test_enum_values_in_param_description(self):
        tool = self._tool(
            input_schema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["fast", "slow"], "description": "Mode."}
                },
            }
        )
        content = _generate_tool_page(tool, "my-server")
        assert "fast" in content
        assert "slow" in content


# ---------------------------------------------------------------------------
# _generate_resource_page
# ---------------------------------------------------------------------------


class TestGenerateResourcePage:
    def test_contains_resource_name(self):
        resource = {
            "name": "config",
            "uri": "gd://config",
            "description": "Config file.",
            "mime_type": None,
        }
        content = _generate_resource_page(resource, "my-server")
        assert "config" in content

    def test_uri_rendered(self):
        resource = {"name": "log", "uri": "gd://build/log", "description": "", "mime_type": None}
        content = _generate_resource_page(resource, "my-server")
        assert "gd://build/log" in content

    def test_mime_type_rendered_when_set(self):
        resource = {
            "name": "data",
            "uri": "gd://data",
            "description": "",
            "mime_type": "application/json",
        }
        content = _generate_resource_page(resource, "my-server")
        assert "application/json" in content

    def test_no_mime_type_line_when_absent(self):
        resource = {"name": "data", "uri": "gd://data", "description": "", "mime_type": None}
        content = _generate_resource_page(resource, "my-server")
        assert "MIME Type" not in content


# ---------------------------------------------------------------------------
# _generate_resource_template_page
# ---------------------------------------------------------------------------


class TestGenerateResourceTemplatePage:
    def test_contains_template_name(self):
        template = {
            "name": "symbol",
            "uri_template": "gd://symbol/{name}",
            "description": "",
            "mime_type": None,
        }
        content = _generate_resource_template_page(template, "my-server")
        assert "symbol" in content

    def test_uri_template_rendered(self):
        template = {
            "name": "page",
            "uri_template": "gd://page/{path}",
            "description": "",
            "mime_type": None,
        }
        content = _generate_resource_template_page(template, "my-server")
        assert "gd://page/{path}" in content

    def test_template_variables_extracted(self):
        template = {
            "name": "item",
            "uri_template": "gd://items/{category}/{id}",
            "description": "",
            "mime_type": None,
        }
        content = _generate_resource_template_page(template, "my-server")
        assert "category" in content
        assert "id" in content

    def test_no_variables_section_when_uri_has_none(self):
        template = {
            "name": "root",
            "uri_template": "gd://root",
            "description": "",
            "mime_type": None,
        }
        content = _generate_resource_template_page(template, "my-server")
        assert "template-variables" not in content.lower()

    def test_description_rendered(self):
        """When description is truthy, renders doc-subject block."""
        template = {
            "name": "docs",
            "uri_template": "gd://docs/{path}",
            "description": "Fetch documentation for a given path.",
            "mime_type": None,
        }
        content = _generate_resource_template_page(template, "my-server")
        assert "doc-subject" in content
        assert "Fetch documentation for a given path." in content

    def test_mime_type_rendered(self):
        """When mime_type is truthy, renders MIME Type line."""
        template = {
            "name": "docs",
            "uri_template": "gd://docs/{path}",
            "description": "",
            "mime_type": "application/json",
        }
        content = _generate_resource_template_page(template, "my-server")
        assert "application/json" in content
        assert "MIME Type" in content


# ---------------------------------------------------------------------------
# _generate_prompt_page
# ---------------------------------------------------------------------------


class TestGeneratePromptPage:
    def test_prompt_name_in_heading(self):
        prompt = {"name": "setup-docs", "description": "", "arguments": [], "messages": []}
        content = _generate_prompt_page(prompt, "my-server")
        assert "setup-docs" in content

    def test_description_rendered(self):
        prompt = {"name": "p", "description": "Do the thing.", "arguments": [], "messages": []}
        content = _generate_prompt_page(prompt, "my-server")
        assert "Do the thing." in content

    def test_required_argument_rendered(self):
        prompt = {
            "name": "p",
            "description": "",
            "arguments": [{"name": "topic", "description": "Topic.", "required": True}],
            "messages": [],
        }
        content = _generate_prompt_page(prompt, "my-server")
        assert "topic" in content
        assert "required" in content

    def test_optional_argument_no_required_badge(self):
        prompt = {
            "name": "p",
            "description": "",
            "arguments": [{"name": "audience", "description": "", "required": False}],
            "messages": [],
        }
        content = _generate_prompt_page(prompt, "my-server")
        assert "audience" in content
        assert "required" not in content

    def test_messages_rendered_as_callouts(self):
        prompt = {
            "name": "p",
            "description": "",
            "arguments": [],
            "messages": [{"role": "user", "text": "Do something important."}],
        }
        content = _generate_prompt_page(prompt, "my-server")
        assert "Do something important." in content
        assert "callout-note" in content

    def test_no_messages_section_when_empty(self):
        prompt = {"name": "p", "description": "", "arguments": [], "messages": []}
        content = _generate_prompt_page(prompt, "my-server")
        assert "callout-note" not in content


# ---------------------------------------------------------------------------
# _extract_tools_from_source
# ---------------------------------------------------------------------------


class TestExtractToolsFromSource:
    def _module_with_source(self, source: str) -> types.ModuleType:
        mod = types.ModuleType("fake")
        mod.__file__ = "<string>"
        # Patch inspect.getsource to return the given source
        with patch("great_docs._mcpref.reference.inspect") as mock_inspect:
            mock_inspect.getsource.return_value = source
            from great_docs._mcpref.reference import _extract_tools_from_source as fn

            return fn(mod)

    def test_extracts_tool_name_and_description(self):
        source = """
Tool(
    name="do_thing",
    description="Does the thing",
    inputSchema={},
)
"""
        result = self._module_with_source(source)
        assert len(result) == 1
        assert result[0]["name"] == "do_thing"
        assert "Does the thing" in result[0]["description"]

    def test_returns_empty_when_no_tools(self):
        result = self._module_with_source("x = 1")
        assert result == []

    def test_extracts_multiple_tools(self):
        source = """
Tool(name="tool_a", description="First tool", inputSchema={})
Tool(name="tool_b", description="Second tool", inputSchema={})
"""
        result = self._module_with_source(source)
        names = [t["name"] for t in result]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_returns_empty_on_getsource_error(self):
        mod = types.ModuleType("fake")
        with patch("great_docs._mcpref.reference.inspect.getsource", side_effect=OSError):
            from great_docs._mcpref.reference import _extract_tools_from_source as fn

            assert fn(mod) == []


# ---------------------------------------------------------------------------
# generate_mcp_reference_pages
# ---------------------------------------------------------------------------


class TestGenerateMcpReferencePages:
    def _server_info(self) -> dict:
        return {
            "name": "test-server",
            "tools": [{"name": "do_thing", "description": "Does a thing.", "input_schema": {}}],
            "resources": [
                {"name": "config", "uri": "gd://config", "description": "", "mime_type": None}
            ],
            "prompts": [{"name": "setup", "description": "", "arguments": [], "messages": []}],
            "resource_templates": [
                {
                    "name": "sym",
                    "uri_template": "gd://sym/{name}",
                    "description": "",
                    "mime_type": None,
                }
            ],
            "instructions": None,
            "completions_enabled": False,
        }

    def test_creates_index_page(self, tmp_path: Path):
        generate_mcp_reference_pages(self._server_info(), tmp_path)
        assert (tmp_path / "index.qmd").exists()

    def test_creates_tool_page(self, tmp_path: Path):
        generate_mcp_reference_pages(self._server_info(), tmp_path)
        assert (tmp_path / "do_thing.qmd").exists()

    def test_creates_resource_page(self, tmp_path: Path):
        generate_mcp_reference_pages(self._server_info(), tmp_path)
        assert (tmp_path / "resource_config.qmd").exists()

    def test_creates_prompt_page(self, tmp_path: Path):
        generate_mcp_reference_pages(self._server_info(), tmp_path)
        assert (tmp_path / "prompt_setup.qmd").exists()

    def test_creates_resource_template_page(self, tmp_path: Path):
        generate_mcp_reference_pages(self._server_info(), tmp_path)
        assert (tmp_path / "template_sym.qmd").exists()

    def test_returns_sidebar_items(self, tmp_path: Path):
        items = generate_mcp_reference_pages(self._server_info(), tmp_path)
        assert len(items) > 0

    def test_display_name_override(self, tmp_path: Path):
        info = self._server_info()
        generate_mcp_reference_pages(info, tmp_path, display_name="My Docs Server")
        index_content = (tmp_path / "index.qmd").read_text(encoding="utf-8")
        # Server name used for display; tool pages reference it
        assert (tmp_path / "do_thing.qmd").exists()

    def test_tool_name_with_hyphens_uses_underscores(self, tmp_path: Path):
        info = self._server_info()
        info["tools"] = [{"name": "do-thing", "description": "", "input_schema": {}}]
        generate_mcp_reference_pages(info, tmp_path)
        assert (tmp_path / "do_thing.qmd").exists()


# ---------------------------------------------------------------------------
# generate_mcp_manifest
# ---------------------------------------------------------------------------


class TestGenerateMcpManifest:
    def _server_info(self, **overrides) -> dict:
        base = {
            "name": "my-server",
            "module": "mypackage.mcp",
            "tools": [{"name": "do_thing", "description": "Does it."}],
            "resources": [],
            "prompts": [],
        }
        base.update(overrides)
        return base

    def test_creates_well_known_directory(self, tmp_path: Path):
        generate_mcp_manifest(self._server_info(), tmp_path)
        assert (tmp_path / ".well-known" / "mcp.json").exists()

    def test_manifest_contains_server_name(self, tmp_path: Path):
        import json

        generate_mcp_manifest(self._server_info(), tmp_path)
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["server"]["name"] == "my-server"

    def test_manifest_tools_summary(self, tmp_path: Path):
        import json

        generate_mcp_manifest(self._server_info(), tmp_path)
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["capabilities"]["tools"]["count"] == 1

    def test_package_name_adds_installation_info(self, tmp_path: Path):
        import json

        generate_mcp_manifest(self._server_info(), tmp_path, package_name="my-pkg")
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["installation"]["package"] == "my-pkg"
        assert "pip install my-pkg" in data["installation"]["install"]

    def test_custom_install_command(self, tmp_path: Path):
        import json

        generate_mcp_manifest(
            self._server_info(), tmp_path, package_name="my-pkg", install_command="uv add my-pkg"
        )
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["installation"]["install"] == "uv add my-pkg"

    def test_site_url_adds_documentation(self, tmp_path: Path):
        import json

        generate_mcp_manifest(self._server_info(), tmp_path, site_url="https://example.com/docs")
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert "documentation" in data
        assert data["documentation"]["url"].endswith("/reference/mcp/")

    def test_repo_url_added_to_installation(self, tmp_path: Path):
        import json

        generate_mcp_manifest(
            self._server_info(), tmp_path, package_name="p", repo_url="https://github.com/x/y"
        )
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["installation"]["repository"] == "https://github.com/x/y"

    def test_module_path_sets_run_command(self, tmp_path: Path):
        import json

        generate_mcp_manifest(self._server_info(), tmp_path)
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["server"]["run"]["args"] == ["-m", "mypackage.mcp"]

    def test_no_installation_section_without_package_or_repo(self, tmp_path: Path):
        import json

        generate_mcp_manifest(self._server_info(), tmp_path)
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert "installation" not in data


# ---------------------------------------------------------------------------
# discover_mcp_server
# ---------------------------------------------------------------------------


class TestDiscoverMcpServer:
    def test_returns_none_on_import_error(self):
        with patch(
            "great_docs._mcpref.reference.importlib.import_module",
            side_effect=ImportError("no module"),
        ):
            result = discover_mcp_server("nonexistent.module")
        assert result is None

    def test_returns_none_when_no_server_found(self):
        mod = types.ModuleType("fake")
        with patch("great_docs._mcpref.reference.importlib.import_module", return_value=mod):
            result = discover_mcp_server("fake")
        assert result is None

    def test_lists_tools_of_an_mcpserver_over_the_protocol(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "probe_mcpserver.py").write_text(
            "from mcp.server.mcpserver import MCPServer\n"
            "\n"
            'app = MCPServer("probe")\n'
            "\n"
            "\n"
            "@app.tool()\n"
            "def add(a: int, b: int) -> int:\n"
            '    """Add numbers."""\n'
            "    return a + b\n",
            encoding="utf-8",
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.setenv("PYTHONPATH", str(tmp_path))

        info = discover_mcp_server("probe_mcpserver")

        assert info is not None
        assert info["name"] == "probe"
        assert [tool["name"] for tool in info["tools"]] == ["add"]

    def test_protocol_failure_falls_back_to_static_scan(self):
        import inspect

        source = 'Tool(name="scan_tool", description="Scans things", inputSchema={})'
        mod = types.ModuleType("fake")
        mock_server = MagicMock()
        type(mock_server).__name__ = "FastMCP"
        type(mock_server).__module__ = "mcp.fastmcp"
        mod.srv = mock_server

        with (
            patch("great_docs._mcpref.reference._introspect_via_protocol", return_value=None),
            patch.object(inspect, "getsource", return_value=source),
            patch("importlib.import_module", return_value=mod),
        ):
            result = discover_mcp_server("fake")

        assert result is not None
        assert any(t["name"] == "scan_tool" for t in result["tools"])

    def test_uses_protocol_info_when_available(self):
        mod = types.ModuleType("fake")
        mock_server = MagicMock()
        type(mock_server).__name__ = "Server"
        type(mock_server).__module__ = "mcp.server"
        mock_server.name = "proto-server"
        mod.srv = mock_server

        protocol_info = {
            "name": "proto-server",
            "tools": [{"name": "proto_tool", "description": "Proto.", "input_schema": {}}],
            "resources": [],
            "prompts": [],
            "resource_templates": [],
            "instructions": None,
            "completions_enabled": False,
        }

        with patch(
            "great_docs._mcpref.reference._introspect_via_protocol", return_value=protocol_info
        ):
            with patch("great_docs._mcpref.reference.importlib.import_module", return_value=mod):
                result = discover_mcp_server("fake")

        assert result is not None
        assert result["name"] == "proto-server"
        assert result["tools"][0]["name"] == "proto_tool"

    def test_uses_server_name_as_fallback(self):
        mod = types.ModuleType("fake")
        mock_server = MagicMock()
        type(mock_server).__name__ = "Server"
        type(mock_server).__module__ = "mcp.server"
        mock_server.name = "fallback-name"
        mod.srv = mock_server

        protocol_info = {
            "name": None,
            "tools": [],
            "resources": [],
            "prompts": [],
            "resource_templates": [],
            "instructions": None,
            "completions_enabled": False,
        }

        with patch(
            "great_docs._mcpref.reference._introspect_via_protocol", return_value=protocol_info
        ):
            with patch("great_docs._mcpref.reference.importlib.import_module", return_value=mod):
                result = discover_mcp_server("fake")

        assert result["name"] == "fallback-name"


# ---------------------------------------------------------------------------
# MCP server discovery
# ---------------------------------------------------------------------------


class TestMcpRunnerRun:
    def test_raises_system_exit_when_no_server(self):
        from great_docs._mcpref.runner import _run

        mod = types.ModuleType("fake")
        with patch("great_docs._mcpref.runner.importlib.import_module", return_value=mod):
            with pytest.raises(SystemExit):
                asyncio.run(_run("fake.module", None))

    def test_calls_run_stdio_async_on_fastmcp(self):
        from great_docs._mcpref.runner import _run

        mock_server = AsyncMock()
        mock_server.run_stdio_async = AsyncMock()
        type(mock_server).__name__ = "FastMCP"
        type(mock_server).__module__ = "mcp.fastmcp"

        mod = types.ModuleType("fake")
        mod.app = mock_server

        with patch("great_docs._mcpref.runner.importlib.import_module", return_value=mod):
            asyncio.run(_run("fake.module", None))

        mock_server.run_stdio_async.assert_called_once()

    def test_explicit_server_var_used(self):
        from great_docs._mcpref.runner import _run

        mock_server = AsyncMock()
        mock_server.run_stdio_async = AsyncMock()
        type(mock_server).__name__ = "FastMCP"
        type(mock_server).__module__ = "mcp.fastmcp"

        mod = types.ModuleType("fake")
        mod.named_server = mock_server

        with patch("great_docs._mcpref.runner.importlib.import_module", return_value=mod):
            asyncio.run(_run("fake.module", "named_server"))

        mock_server.run_stdio_async.assert_called_once()

    def test_runs_low_level_server_with_initialization_options(self):
        from great_docs._mcpref.runner import _run

        server = MagicMock(spec=["run", "create_initialization_options"])
        server.run = AsyncMock()
        mod = types.ModuleType("fake")
        mod.server = server

        @contextlib.asynccontextmanager
        async def fake_stdio_server():
            yield "read", "write"

        # The second patch replaces the import function that `patch` uses to
        # resolve targets. Apply the stdio patch first.
        with (
            patch("mcp.server.stdio.stdio_server", fake_stdio_server),
            patch("great_docs._mcpref.runner.importlib.import_module", return_value=mod),
        ):
            asyncio.run(_run("fake.module", "server"))

        server.run.assert_awaited_once_with(
            "read", "write", server.create_initialization_options.return_value
        )


# ---------------------------------------------------------------------------
# _introspect_via_protocol
# ---------------------------------------------------------------------------

_LOW_LEVEL_SERVER = """
from mcp import types
from mcp.server import Server


async def list_tools(ctx, params=None):
    tool = types.Tool(name="add", description="Add numbers.", input_schema={"type": "object"})
    return types.ListToolsResult(tools=[tool])


async def list_prompts(ctx, params=None):
    argument = types.PromptArgument(name="topic", required=True)
    prompt = types.Prompt(name="explain", description="Explain.", arguments=[argument])
    return types.ListPromptsResult(prompts=[prompt])


async def get_prompt(ctx, params):
    topic = (params.arguments or {})["topic"]
    content = types.TextContent(type="text", text=f"Explain {topic}")
    return types.GetPromptResult(messages=[types.PromptMessage(role="user", content=content)])


async def list_resources(ctx, params=None):
    resource = types.Resource(uri="probe://config", name="config", mime_type="text/plain")
    return types.ListResourcesResult(resources=[resource])


async def list_resource_templates(ctx, params=None):
    template = types.ResourceTemplate(uri_template="probe://items/{id}", name="item")
    return types.ListResourceTemplatesResult(resource_templates=[template])


server = Server(
    "probe",
    instructions="  Start here.  ",
    on_list_tools=list_tools,
    on_list_prompts=list_prompts,
    on_get_prompt=get_prompt,
    on_list_resources=list_resources,
    on_list_resource_templates=list_resource_templates,
)
"""


class TestIntrospectViaProtocol:
    def test_reads_a_low_level_server_over_the_protocol(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from great_docs._mcpref.reference import _introspect_via_protocol

        (tmp_path / "probe_server.py").write_text(_LOW_LEVEL_SERVER, encoding="utf-8")
        monkeypatch.setenv("PYTHONPATH", str(tmp_path))

        info = _introspect_via_protocol("probe_server", "server")

        assert info is not None
        assert info["name"] == "probe"
        assert info["instructions"] == "Start here."
        assert [tool["name"] for tool in info["tools"]] == ["add"]
        assert info["resources"][0]["mime_type"] == "text/plain"
        assert info["resource_templates"][0]["uri_template"] == "probe://items/{id}"
        # The required prompt argument makes the preview use a placeholder value.
        assert info["prompts"][0]["messages"] == [{"role": "user", "text": "Explain <topic>"}]

    @pytest.mark.parametrize(
        "error",
        [
            # Nested groups reproduce how AnyIO reports a server connection failure.
            ExceptionGroup(
                "outer", [ExceptionGroup("inner", [MCPError(-32000, "Connection closed")])]
            ),
            TimeoutError("no answer"),
            OSError("cannot start"),
        ],
        ids=["protocol-error-in-task-groups", "timeout", "os-error"],
    )
    def test_expected_failure_falls_back(
        self, error: Exception, capsys: pytest.CaptureFixture[str]
    ):
        from great_docs._mcpref.reference import _introspect_via_protocol

        async def failing(*args: Any) -> None:
            raise error

        with patch("great_docs._mcpref.reference._collect_over_protocol", failing):
            result = _introspect_via_protocol("fake.module", None)

        assert result is None
        message = "Connection closed" if isinstance(error, ExceptionGroup) else str(error)
        assert (
            f"Could not introspect MCP server over protocol: {message}" in capsys.readouterr().out
        )

    def test_missing_mcp_falls_back(self):
        from great_docs._mcpref.reference import _introspect_via_protocol

        with patch.dict("sys.modules", {"mcp.shared.exceptions": None}):
            assert _introspect_via_protocol("fake.module", None) is None

    @pytest.mark.parametrize(
        "error",
        [
            RuntimeError("bug"),
            ExceptionGroup("outer", [MCPError(-32000, "Connection closed"), RuntimeError("bug")]),
        ],
        ids=["bare", "beside-a-protocol-error"],
    )
    def test_unexpected_error_propagates(self, error: Exception):
        from great_docs._mcpref.reference import _introspect_via_protocol

        async def failing(*args: Any) -> None:
            raise error

        with patch("great_docs._mcpref.reference._collect_over_protocol", failing):
            with pytest.raises(type(error)):
                _introspect_via_protocol("fake.module", None)


# ---------------------------------------------------------------------------
# Protocol listing helpers
# ---------------------------------------------------------------------------


class TestListHelpers:
    def test_list_tools_follows_the_next_cursor(self):
        from great_docs._mcpref.reference import _list_tools

        session = MagicMock()
        session.list_tools = AsyncMock(
            side_effect=[
                {"tools": [{"name": "first"}], "nextCursor": "page-2"},
                {"tools": [{"name": "second"}]},
            ]
        )

        tools = asyncio.run(_list_tools(session))

        assert [tool["name"] for tool in tools] == ["first", "second"]
        assert session.list_tools.await_args_list[0].kwargs == {"params": None}
        assert session.list_tools.await_args_list[1].kwargs["params"].cursor == "page-2"

    @pytest.mark.parametrize(
        "method", ["list_resources", "list_resource_templates", "list_prompts"]
    )
    @pytest.mark.parametrize(
        "error",
        [MCPError(-32601, "Method not found"), TimeoutError()],
        ids=["protocol-error", "timeout"],
    )
    def test_protocol_error_or_timeout_lists_nothing(self, method: str, error: Exception):
        from great_docs._mcpref import reference

        session = MagicMock()
        setattr(session, method, AsyncMock(side_effect=error))

        assert asyncio.run(getattr(reference, f"_{method}")(session)) == []

    @pytest.mark.parametrize(
        "method", ["list_resources", "list_resource_templates", "list_prompts"]
    )
    def test_unexpected_error_from_a_list_call_propagates(self, method: str):
        from great_docs._mcpref import reference

        session = MagicMock()
        setattr(session, method, AsyncMock(side_effect=RuntimeError("bug")))

        with pytest.raises(RuntimeError, match="bug"):
            asyncio.run(getattr(reference, f"_{method}")(session))

    @pytest.mark.parametrize(
        "error",
        [MCPError(-32602, "topic is required"), TimeoutError()],
        ids=["protocol-error", "timeout"],
    )
    def test_prompt_preview_retries_with_placeholder_arguments(self, error: Exception):
        from great_docs._mcpref.reference import _get_prompt_messages

        message = {"role": "user", "content": {"type": "text", "text": "Explain <topic>"}}
        session = MagicMock()
        session.get_prompt = AsyncMock(side_effect=[error, {"messages": [message]}])

        messages = asyncio.run(_get_prompt_messages(session, "explain", ["topic"]))

        assert messages == [message]
        assert session.get_prompt.await_args_list[1].args == ("explain", {"topic": "<topic>"})

    def test_prompt_preview_is_empty_when_every_attempt_fails(self):
        from great_docs._mcpref.reference import _get_prompt_messages

        session = MagicMock()
        session.get_prompt = AsyncMock(side_effect=MCPError(-32602, "topic is required"))

        assert asyncio.run(_get_prompt_messages(session, "explain", ["topic"])) == []
        assert session.get_prompt.await_count == 2

    def test_prompt_that_asks_for_input_has_no_preview(self):
        from mcp.types import InputRequiredResult

        from great_docs._mcpref.reference import _get_prompt_messages

        # The client requires callers to opt in to responses that request
        # user input. Match that requirement in the fake.
        async def get_prompt(
            name: str, arguments: dict[str, str], *, allow_input_required: bool = False
        ) -> InputRequiredResult:
            if not allow_input_required:
                raise RuntimeError("Server returned InputRequiredResult")
            return InputRequiredResult(request_state="awaiting-topic")

        session = MagicMock()
        session.get_prompt = get_prompt

        assert asyncio.run(_get_prompt_messages(session, "explain", ["topic"])) == []

    def test_unexpected_error_from_a_prompt_preview_propagates(self):
        from great_docs._mcpref.reference import _get_prompt_messages

        session = MagicMock()
        session.get_prompt = AsyncMock(side_effect=RuntimeError("bug"))

        with pytest.raises(RuntimeError, match="bug"):
            asyncio.run(_get_prompt_messages(session, "explain", []))


# ---------------------------------------------------------------------------
# generate_mcp_manifest — resources and prompts sections
# ---------------------------------------------------------------------------


class TestGenerateMcpManifestExtended:
    def _server_info(self, **overrides) -> dict:
        base: dict = {
            "name": "srv",
            "module": "pkg.mcp",
            "tools": [],
            "resources": [],
            "prompts": [],
        }
        base.update(overrides)
        return base

    def test_resources_section_included(self, tmp_path: Path):
        import json

        info = self._server_info(
            resources=[{"uri": "gd://config", "name": "config", "description": "Cfg."}]
        )
        generate_mcp_manifest(info, tmp_path)
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["capabilities"]["resources"]["count"] == 1
        assert data["capabilities"]["resources"]["list"][0]["name"] == "config"

    def test_prompts_section_included(self, tmp_path: Path):
        import json

        info = self._server_info(prompts=[{"name": "setup", "description": "Set up docs."}])
        generate_mcp_manifest(info, tmp_path)
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert data["capabilities"]["prompts"]["count"] == 1
        assert data["capabilities"]["prompts"]["list"][0]["name"] == "setup"

    def test_no_tools_section_when_empty(self, tmp_path: Path):
        import json

        generate_mcp_manifest(self._server_info(), tmp_path)
        data = json.loads((tmp_path / ".well-known" / "mcp.json").read_text())
        assert "tools" not in data["capabilities"]
