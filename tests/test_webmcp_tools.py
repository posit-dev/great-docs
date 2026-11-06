from __future__ import annotations

import re

from great_docs._website.ai_agents.webmcp_tools import TOOL_NAMES, TOOLS

# The site features a tool can depend on.
_FEATURES = {"site", "api", "cli", "versions", "changelog", "skills", "blog", "theme"}


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
