from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from great_docs._website.ai_agents import webmcp_tools
from great_docs._website.ai_agents.webmcp_tools import TOOL_NAMES, TOOLS, WebMCPTool
from tests.support import write_config

if TYPE_CHECKING:
    from pathlib import Path

# The site features a tool can depend on.
_FEATURES = {"site", "api", "cli", "versions", "changelog", "skills", "blog", "theme"}

_SITE_TOOLS = ["get_site_overview", "get_current_page", "list_pages", "get_page", "search_docs"]


def test_names_are_unique():
    assert len(TOOL_NAMES) == len(TOOLS)


def test_names_are_snake_case_verb_noun():
    # Chrome accepts `[A-Za-z0-9_.-]{1,128}`; the built-in tools use a narrower style.
    for tool in TOOLS:
        assert re.fullmatch(r"(get|list|search|open|set|switch)_[a-z]+(_[a-z]+)*", tool.name)


def test_every_tool_is_described():
    for tool in TOOLS:
        assert tool.title and tool.title[0].isupper(), tool.name
        assert tool.purpose and len(tool.purpose) <= 100, tool.name
        assert tool.feature in _FEATURES, tool.name


def test_action_tools():
    assert {tool.name for tool in TOOLS if tool.action} == {
        "open_page",
        "set_theme",
        "switch_version",
    }


def test_site_tools_need_no_feature():
    site = {tool.name for tool in TOOLS if tool.feature == "site" and not tool.action}
    assert site == {
        "get_site_overview",
        "get_current_page",
        "list_pages",
        "get_page",
        "search_docs",
    }


def test_the_site_reference_version_and_changelog_tools_are_implemented():
    assert [tool.name for tool in TOOLS if tool.implemented] == [
        *_SITE_TOOLS,
        "list_api",
        "get_api_reference",
        "get_cli_help",
        "list_versions",
        "get_changelog",
    ]


def _names(tools: list[WebMCPTool]) -> list[str]:
    return [tool.name for tool in tools]


class TestRegistered:
    @pytest.fixture
    def table(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Replace the tool table with one implemented tool of each kind"""
        monkeypatch.setattr(
            webmcp_tools,
            "TOOLS",
            (
                WebMCPTool("get_one", "Get one", "One", "site", implemented=True),
                WebMCPTool("list_api", "List the API", "API", "api", implemented=True),
                WebMCPTool("get_cli_help", "Get CLI help", "CLI", "cli"),
                WebMCPTool("open_page", "Open", "Go", "site", action=True, implemented=True),
            ),
        )

    @pytest.mark.usefixtures("table")
    def test_only_implemented_tools_of_the_site_features_are_registered(self):
        tools = webmcp_tools.registered(_FEATURES, actions=True, exclude=())

        assert _names(tools) == ["get_one", "list_api", "open_page"]
        assert _names(webmcp_tools.registered({"site"}, actions=True, exclude=())) == [
            "get_one",
            "open_page",
        ]

    @pytest.mark.usefixtures("table")
    def test_actions_and_excluded_tools_are_left_out(self):
        assert _names(webmcp_tools.registered({"site"}, actions=False, exclude=())) == ["get_one"]
        assert _names(webmcp_tools.registered({"site"}, actions=True, exclude=["get_one"])) == [
            "open_page"
        ]


class TestSiteTools:
    def test_no_tools_without_webmcp(self, tmp_path: Path):
        config = write_config(tmp_path, {"webmcp": False})

        assert webmcp_tools.site_tools(config, _FEATURES) == []

    def test_the_configuration_chooses_the_tools(self, tmp_path: Path):
        config = write_config(
            tmp_path, {"webmcp": {"enabled": True, "exclude_tools": ["get_page"]}}
        )

        assert _names(webmcp_tools.site_tools(config, _FEATURES)) == [
            "get_site_overview",
            "get_current_page",
            "list_pages",
            "search_docs",
            "list_api",
            "get_api_reference",
            "get_cli_help",
            "list_versions",
            "get_changelog",
        ]
