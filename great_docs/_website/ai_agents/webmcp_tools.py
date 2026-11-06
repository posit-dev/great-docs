"""
The tools a site can register for in-browser AI agents through WebMCP
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebMCPTool:
    """
    One tool the WebMCP runtime can register

    Attributes
    ----------
    name
        The name agents call the tool by. Frozen once released.
    title
        A short human-readable label.
    purpose
        One line saying what the tool returns or does.
    feature
        The site feature the tool needs: `site` (every site), `api`, `cli`, `versions`,
        `changelog`, `skills`, `blog` or `theme`.
    action
        Whether the tool changes the page rather than only reading it. Action tools are
        left out when `webmcp.actions` is false.
    """

    name: str
    title: str
    purpose: str
    feature: str
    action: bool = False


TOOLS: tuple[WebMCPTool, ...] = (
    WebMCPTool(
        "get_site_overview",
        "Get the site overview",
        "The package, its version and install commands, the site's sections and these tools",
        "site",
    ),
    WebMCPTool(
        "get_current_page",
        "Get the current page",
        "The open page as Markdown, or as an outline of its headings",
        "site",
    ),
    WebMCPTool("list_pages", "List the pages", "The site's pages grouped by section", "site"),
    WebMCPTool("get_page", "Get a page", "One page, or one section of it, as Markdown", "site"),
    WebMCPTool(
        "search_docs", "Search the docs", "Ranked matches for a query, by page section", "site"
    ),
    WebMCPTool(
        "list_api",
        "List the API",
        "The documented objects grouped by reference section",
        "api",
    ),
    WebMCPTool(
        "get_api_reference",
        "Get an API reference",
        "One object's signature, parameters, returns and examples",
        "api",
    ),
    WebMCPTool("get_cli_help", "Get CLI help", "The help text of a CLI command", "cli"),
    WebMCPTool(
        "list_versions",
        "List the versions",
        "The documented versions, with this page's URL in each",
        "versions",
    ),
    WebMCPTool(
        "get_changelog",
        "Get the changelog",
        "One release's changelog entry, or the latest few",
        "changelog",
    ),
    WebMCPTool(
        "get_agent_skill",
        "Get an agent skill",
        "A published SKILL.md and its companion files",
        "skills",
    ),
    WebMCPTool(
        "get_post_summary",
        "Get the post summary",
        "A blog post's summary, takeaways, audience and outline",
        "blog",
    ),
    WebMCPTool(
        "get_post_evidence",
        "Get the post evidence",
        "A blog post's claims, evidence and sources",
        "blog",
    ),
    WebMCPTool(
        "get_post_next_steps",
        "Get the post next steps",
        "A blog post's next steps and related posts",
        "blog",
    ),
    WebMCPTool(
        "open_page", "Open a page", "Go to a page or section of this site", "site", action=True
    ),
    WebMCPTool(
        "set_theme",
        "Set the theme",
        "Switch to the light, dark or system theme",
        "theme",
        action=True,
    ),
    WebMCPTool(
        "switch_version",
        "Switch the version",
        "Go to this page in another documented version",
        "versions",
        action=True,
    ),
)
"""Every built-in tool, in the order the runtime registers them"""

TOOL_NAMES: frozenset[str] = frozenset(tool.name for tool in TOOLS)
"""The names of the built-in tools"""
