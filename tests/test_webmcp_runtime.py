"""Tests for `webmcp.js`, run with Node in a stub page."""

from __future__ import annotations

import gzip
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from great_docs._interlinks.sphinx_inventory import Inventory, InventoryEntry, encode
from great_docs._website.ai_agents import webmcp_manifest, webmcp_pages
from great_docs._website.ai_agents.webmcp_manifest import Root, SiteInfo
from great_docs._website.ai_agents.webmcp_pages import PageFacts, SectionFacts
from great_docs._website.ai_agents.webmcp_tools import TOOLS, registered

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "great_docs" / "assets" / "webmcp.js"
HARNESS = ROOT / "tests" / "js" / "webmcp_harness.js"
SITE = ROOT / "tests" / "fixtures" / "webmcp_site"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

SETTLE = "await settle();"
BASE = "https://docs.example.org/"
SITE_TOOLS = ["get_site_overview", "get_current_page", "list_pages", "get_page", "search_docs"]
API_TOOLS = ["list_api", "get_api_reference"]
# The settings of a site with an API reference.
WITH_API = {"features": {"api": True}}
WITH_ALL = {"features": {"api": True, "cli": True}}

_QUARTO_YML = """\
project:
  type: website
website:
  sidebar:
    - id: user-guide
      contents:
        - user-guide/intro.qmd
        - user-guide/setup.qmd
        - section: Publishing
          contents:
            - user-guide/02-deploy.qmd
    - id: reference
      contents:
        - reference/index.qmd
        - section: Classes
          contents:
            - reference/Widget.qmd
            - reference/Widget.spin.qmd
        - section: CLI
          contents:
            - reference/cli/index.qmd
            - reference/cli/example.qmd
            - reference/cli/build.qmd
            - reference/cli/config.qmd
            - reference/cli/config/show.qmd
"""

_PAGES = [
    ("index.html", {"title": "Example"}),
    ("notes.html", {"title": "Notes"}),
    (
        "user-guide/intro.html",
        {"title": "Introduction", "description": "What Example does.", "tags": ("basics",)},
    ),
    ("user-guide/setup.html", {"title": "Setup"}),
    (
        "user-guide/02-deploy.html",
        {"description": "Publish the docs to GitHub Pages or Netlify.", "status": "new"},
    ),
    ("user-guide/internal.html", {"listed": False}),
    ("blog/index.html", {}),
    ("blog/launch.html", {"date": "2026-01-02", "tags": ("news",)}),
    ("blog/setup.html", {"date": "2026-03-01"}),
]

_HTML_CLASSES = {
    "reference/index.html": "doc-reference",
    "reference/Widget.html": "doc-api-page doc-py-api-page",
    "reference/Widget.spin.html": "doc-api-page doc-py-api-page",
    "reference/cli/index.html": "doc-reference doc-cli-reference",
    "reference/cli/example.html": "doc-api-page doc-cli-api-page",
    "reference/cli/build.html": "doc-api-page doc-cli-api-page",
    "reference/cli/config.html": "doc-api-page doc-cli-api-page",
    "reference/cli/config/show.html": "doc-api-page doc-cli-api-page",
}

_API = [
    ("example.Widget", "class", "reference/Widget.html#example.Widget"),
    ("example.Widget.spin", "method", "reference/Widget.spin.html#example.Widget.spin"),
    ("example.Widget.stop", "method", "reference/Widget.html#stop"),
    # A page without a Markdown copy.
    ("example.stop", "function", "reference/stop.html#example.stop"),
]

_SUMMARIES = {
    "reference/Widget.html": "A widget that spins.",
    "reference/Widget.spin.html": "Spin the widget.",
}


def _page_facts(path: str, fields: dict[str, Any]) -> PageFacts:
    values: dict[str, Any] = {
        "source": path.replace(".html", ".qmd"),
        "title": None,
        "description": None,
        "section": path.split("/")[0] if "/" in path else "",
        "tags": (),
        "status": None,
        "date": None,
        "draft": False,
        "webmcp": True,
        "listed": True,
    }
    return PageFacts(path=path, **{**values, **fields})


def _build_site(directory: Path) -> Path:
    """
    Copy the fixture site and write what a build adds to it, including `gd-webmcp.json`

    Parameters
    ----------
    directory
        An empty directory to build in.

    Returns
    -------
    :
        The site directory.
    """
    site_dir = directory / "_site"
    _ = shutil.copytree(SITE, site_dir)
    project_dir = directory
    _ = (project_dir / "_quarto.yml").write_text(_QUARTO_YML, encoding="utf-8")
    facts = {
        "schema": 1,
        "sections": [
            asdict(SectionFacts("user-guide", "User Guide", "guide")),
            asdict(SectionFacts("blog", "Blog", "blog")),
        ],
        "pages": [asdict(_page_facts(path, fields)) for path, fields in _PAGES],
    }
    _ = (project_dir / webmcp_pages.FACTS_FILE).write_text(json.dumps(facts), encoding="utf-8")
    search = json.loads((site_dir / "search.json").read_text(encoding="utf-8"))
    for path in {entry["href"].split("#")[0] for entry in search}:
        html = site_dir / path
        html.parent.mkdir(parents=True, exist_ok=True)
        summary = _SUMMARIES.get(path)
        head = f'<head><meta name="description" content="{summary}"></head>' if summary else ""
        _ = html.write_text(
            f'<html>{head}<body class="{_HTML_CLASSES.get(path, "")}"><main></main></body></html>',
            encoding="utf-8",
        )
    inventory = Inventory(
        "example",
        "1.2.0",
        tuple(InventoryEntry(name, "py", role, 1, uri, name) for name, role, uri in _API),
    )
    _ = (site_dir / "objects.inv").write_bytes(encode(inventory))
    info = SiteInfo(
        name="example",
        title="Example",
        description="A package for examples.",
        version="1.2.0",
        repo="https://github.com/acme/example",
        license="MIT",
        install=("pip install example",),
    )
    warnings: list[str] = []
    _ = webmcp_manifest.write([Root(site_dir, project_dir, None, BASE)], info, warn=warnings.append)
    assert warnings == []
    return site_dir


_built: list[Path] = []


@pytest.fixture(scope="module", autouse=True)
def built_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    site_dir = _build_site(tmp_path_factory.mktemp("webmcp"))
    _built[:] = [site_dir]
    return site_dir


def _run(scenario: str = "", **options: Any) -> dict[str, Any]:
    """
    Run a scenario against the runtime in a stub page

    Parameters
    ----------
    scenario
        The body of an async function; see `tests/js/webmcp_harness.js`.
    **options
        The harness options. `siteDir` defaults to the built fixture site.

    Returns
    -------
    :
        What the harness observed, with the scenario's return value as `result`.
    """
    if "siteDir" not in options:
        options["siteDir"] = str(_built[0])
    completed = subprocess.run(
        ["node", str(HARNESS), str(RUNTIME), json.dumps(options), scenario],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _call(name: str, tool_input: object = None, **options: Any) -> dict[str, Any]:
    argument = "undefined" if tool_input is None else json.dumps(tool_input)
    return _run(f"{SETTLE} return await tools.call({json.dumps(name)}, {argument});", **options)[
        "result"
    ]


def _internal(expression: str, **options: Any) -> Any:
    return _run(f"const internals = tools._internals; return {expression};", **options)["result"]


class TestRegistration:
    def test_tools_register_with_document_model_context(self):
        observed = _run(SETTLE)

        assert observed["status"] == "registered"
        assert observed["registered"] == SITE_TOOLS
        assert observed["warnings"] == []

    def test_the_python_table_lists_the_registered_tools(self):
        # `llms.txt` lists the tools from the Python table, so it must match the runtime.
        observed = _run(SETTLE, settings={**WITH_ALL, "exclude": ["get_page"], "actions": False})
        expected = registered({"site", "api", "cli"}, actions=False, exclude=["get_page"])

        assert observed["registered"] == [tool.name for tool in expected]

    def test_navigator_model_context_is_a_fallback(self):
        observed = _run(SETTLE, modelContext="navigator")

        assert observed["status"] == "registered"
        assert observed["registered"] == SITE_TOOLS

    def test_without_webmcp_the_js_api_still_works(self):
        observed = _run(
            f"{SETTLE} return [tools.status, tools.list().map((t) => t.name),"
            " (await tools.call('get_current_page', {format: 'outline'})).source];",
            modelContext="none",
        )

        assert observed["status"] == "unavailable"
        assert observed["result"] == ["unavailable", SITE_TOOLS, "markdown"]

    def test_platform_objects_keep_their_properties(self):
        observed = _run(
            f"{SETTLE} tools.add({{name: 'site_tool', description: 'A tool.', execute: () => 1}});"
            f" {SETTLE}",
            modelContext="both",
        )

        assert observed["registered"] == [*SITE_TOOLS, "site_tool"]
        assert observed["platformUnchanged"] is True

    def test_refused_tools_leave_the_status_failed_and_warn_once_each(self):
        observed = _run(SETTLE, refuse=SITE_TOOLS)

        assert observed["status"] == "failed"
        assert len(observed["warnings"]) == len(SITE_TOOLS)
        assert "get_current_page" in observed["warnings"][1]

    def test_a_refused_tool_leaves_the_status_partial(self):
        observed = _run(SETTLE, refuse=["get_page"])

        assert observed["status"] == "partial"
        assert len(observed["warnings"]) == 1
        assert "get_page" in observed["warnings"][0]

    def test_the_status_is_pending_until_registration_settles(self):
        observed = _run("return document.documentElement.getAttribute('data-gd-webmcp');")

        assert observed["result"] == "pending"
        assert observed["status"] == "registered"

    def test_an_opted_out_page_registers_nothing(self):
        observed = _run(
            f"{SETTLE} return [tools.list(), await tools.call('get_current_page', {{}}),"
            " tools.add({name: 'x', description: 'X.', execute: () => 1})];",
            bodyClasses=["gd-no-webmcp"],
        )

        listed, called, added = observed["result"]
        assert observed["status"] == "off"
        assert observed["registered"] == []
        assert listed == []
        assert called["error"]["code"] == "unavailable"
        assert added == {"added": [], "rejected": [{"name": "x", "reason": ANY_STRING}]}
        assert observed["fetched"] == []

    def test_excluded_tools_are_not_registered(self):
        observed = _run(SETTLE, settings={"exclude": SITE_TOOLS})

        assert observed["status"] == "off"
        assert observed["registered"] == []

    def test_unreadable_settings_fall_back_to_the_defaults(self):
        observed = _run(SETTLE, settings="{not json")

        assert observed["status"] == "registered"
        assert len(observed["warnings"]) == 1

    def test_without_the_js_api_nothing_is_exposed_or_announced(self):
        observed = _run(f"{SETTLE} return typeof window.greatDocs;", settings={"js_api": False})

        assert observed["result"] == "undefined"
        assert observed["status"] == "registered"
        assert observed["events"] == []

    def test_the_ready_event_fires_once_with_the_api(self):
        observed = _run(SETTLE)

        assert observed["events"] == [{"type": "gd-webmcp:ready", "detailIsTools": True}]

    def test_registered_tools_carry_title_and_annotations(self):
        observed = _run(f"{SETTLE} return browser.tools.map((t) => [t.title, t.annotations]);")

        assert observed["result"] == [
            [tool.title, {"readOnlyHint": True}] for tool in TOOLS if tool.name in SITE_TOOLS
        ]

    def test_the_browser_receives_plain_results(self):
        observed = _run(
            f"{SETTLE} const tool = browser.tools.find((t) => t.name === 'get_current_page');"
            " return await tool.execute({format: 'outline'}, {});"
        )

        assert observed["result"]["format"] == "outline"
        assert observed["result"]["outline"][0]["text"] == "Introduction"


class _AnyString:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str) and bool(other)


ANY_STRING = _AnyString()


class TestJsApi:
    def test_list_describes_each_tool(self):
        listed = _run("return tools.list();")["result"]

        assert [tool["name"] for tool in listed] == SITE_TOOLS
        assert set(listed[1]) == {"name", "title", "description", "inputSchema", "annotations"}
        assert listed[1]["inputSchema"]["properties"]["format"]["enum"] == ["markdown", "outline"]

    def test_call_reports_an_unknown_tool(self):
        result = _call("get_nothing", {})

        assert result["error"]["code"] == "not_found"
        assert result["error"]["candidates"] == SITE_TOOLS

    def test_add_registers_a_working_tool(self):
        observed = _run(
            "const outcome = tools.add([{name: 'site.echo', title: 'Echo', description: 'Echo.',"
            " inputSchema: {type: 'object', properties: {text: {type: 'string'}},"
            " required: ['text']}, execute: (input) => ({echo: input.text})}]);"
            f" {SETTLE}"
            " return [outcome, await tools.call('site.echo', {text: 'hi'}),"
            " await tools.call('site.echo', {}), tools.list().map((t) => t.name)];"
        )

        outcome, echoed, missing, names = observed["result"]
        assert outcome == {"added": ["site.echo"], "rejected": []}
        assert echoed == {"echo": "hi"}
        assert missing["error"]["code"] == "invalid_input"
        assert names == [*SITE_TOOLS, "site.echo"]
        assert "site.echo" in observed["registered"]

    @pytest.mark.parametrize(
        ("tool", "reason"),
        [
            ("{name: 'get_page', description: 'X.', execute: () => 1}", "Great Docs"),
            ("{name: 'get_current_page', description: 'X.', execute: () => 1}", "Great Docs"),
            ("{name: 'bad name', description: 'X.', execute: () => 1}", "name"),
            ("{name: 'x'.repeat(129), description: 'X.', execute: () => 1}", "name"),
            ("{name: 'no_description', execute: () => 1}", "description"),
            ("{name: 'no_execute', description: 'X.'}", "execute"),
            (
                "{name: 'bad_schema', description: 'X.', inputSchema: {type: 'string'},"
                " execute: () => 1}",
                "inputSchema",
            ),
            ("null", "object"),
        ],
    )
    def test_add_rejects_an_invalid_tool(self, tool: str, reason: str):
        outcome = _run(f"return tools.add({tool});")["result"]

        assert outcome["added"] == []
        assert len(outcome["rejected"]) == 1
        assert reason in outcome["rejected"][0]["reason"]

    def test_add_rejects_a_duplicate(self):
        outcome = _run(
            "const tool = {name: 'twice', description: 'X.', execute: () => 1};"
            " tools.add(tool); return tools.add(tool);"
        )["result"]

        assert outcome == {"added": [], "rejected": [{"name": "twice", "reason": ANY_STRING}]}

    def test_a_tool_that_throws_returns_an_error(self):
        observed = _run(
            "tools.add({name: 'broken', description: 'X.', execute: () => {"
            " throw new Error('boom'); }});"
            " return [await tools.call('broken'), await tools.call('broken')];"
        )

        first, second = observed["result"]
        assert first == {"error": {"code": "internal", "message": "broken failed: boom"}}
        assert second == first
        assert len(observed["warnings"]) == 1

    def test_a_tool_that_returns_nothing_returns_an_object(self):
        result = _run(
            "tools.add({name: 'quiet', description: 'X.', execute: () => undefined});"
            " return await tools.call('quiet');"
        )["result"]

        assert result == {}

    def test_input_can_arrive_as_json_text(self):
        result = _call("get_current_page", '{"format": "outline"}')

        assert result["format"] == "outline"

    def test_reserved_names_match_the_tool_list(self):
        assert _internal("internals.reservedNames") == [tool.name for tool in TOOLS]


class TestValidation:
    SCHEMA = {
        "type": "object",
        "properties": {
            "format": {"type": "string", "enum": ["markdown", "outline"]},
            "max_chars": {"type": "integer", "minimum": 500, "maximum": 1000},
            "query": {"type": "string", "minLength": 2},
            "ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": [],
        "additionalProperties": False,
    }

    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ({}, None),
            ({"format": "outline", "max_chars": 600, "query": "ab", "ids": ["a"]}, None),
            ({"format": "html"}, '"format" must be one of "markdown", "outline".'),
            ({"max_chars": 1.5}, '"max_chars" must be an integer, not number.'),
            ({"max_chars": "600"}, '"max_chars" must be an integer, not string.'),
            ({"max_chars": 100}, '"max_chars" must be at least 500.'),
            ({"max_chars": 5000}, '"max_chars" must be at most 1000.'),
            ({"query": "a"}, '"query" must have at least 2 characters.'),
            ({"ids": ["a", 1]}, '"ids"[1] must be a string, not integer.'),
            (
                {"extra": 1},
                'Unknown property "extra". Known properties: format, max_chars, query, ids.',
            ),
            ([], "input must be an object, not array."),
        ],
    )
    def test_validate(self, value: object, message: str | None):
        expression = f"internals.validate({json.dumps(self.SCHEMA)}, {json.dumps(value)})"

        assert _internal(expression) == message

    def test_a_required_property_must_be_present(self):
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

        assert _internal(f"internals.validate({json.dumps(schema)}, {{}})") == '"path" is required.'

    def test_invalid_input_returns_the_schema_and_an_example(self):
        result = _call("get_current_page", {"format": "pdf"})

        error = result["error"]
        assert error["code"] == "invalid_input"
        assert error["example"] == {"format": "outline"}
        assert error["inputSchema"]["properties"]["format"]["enum"] == ["markdown", "outline"]


class TestMarkdown:
    def test_headings_skip_code_blocks_and_front_matter(self):
        markdown = (SITE / "user-guide" / "intro.md").read_text(encoding="utf-8")

        outline = _internal(f"internals.headings({json.dumps(markdown)})")

        assert outline == [
            {"level": 1, "text": "Introduction", "anchor": "introduction"},
            {"level": 2, "text": "Getting started", "anchor": "getting-started"},
            {"level": 2, "text": "Options", "anchor": "sec-options"},
            {"level": 3, "text": "The level option", "anchor": "the-level-option"},
            {"level": 2, "text": "Getting started", "anchor": "getting-started-1"},
        ]

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Publishing Skills (for Authors)", "publishing-skills-for-authors"),
            ("1. Install", "install"),
            ("What's new in v2.0?", "whats-new-in-v2.0"),
            ("Ünïcode títle", "ünïcode-títle"),
            ("123", "section"),
        ],
    )
    def test_slug_follows_pandoc(self, text: str, expected: str):
        assert _internal(f"internals.slug({json.dumps(text)})") == expected

    def test_headings_handle_closing_hashes_and_links(self):
        markdown = "## A [link](x.html) ##\n####### Not a heading\n#NoSpace\n"

        assert _internal(f"internals.headings({json.dumps(markdown)})") == [
            {"level": 2, "text": "A link", "anchor": "a-link"}
        ]

    def test_truncate_leaves_short_text_alone(self):
        assert _internal("internals.truncate('short', 500)") == {
            "text": "short",
            "truncated": False,
        }

    def test_truncate_cuts_at_a_line_break(self):
        markdown = "\n".join(f"Line {i:03d} of the page." for i in range(100))

        result = _internal(f"internals.truncate({json.dumps(markdown)}, 500)")

        assert result["truncated"] is True
        assert len(result["text"]) <= 500
        assert markdown.startswith(result["text"])
        assert result["text"].endswith("of the page.")

    def test_truncate_closes_a_code_block_it_cuts(self):
        markdown = "Intro\n\n````python\n" + "\n".join(f"x = {i}" for i in range(200)) + "\n````\n"

        result = _internal(f"internals.truncate({json.dumps(markdown)}, 500)")

        text = result["text"]
        assert len(text) <= 500
        assert text.endswith("\n````")
        assert _internal(f"internals.headings({json.dumps(text + chr(10) + '# After')})") == [
            {"level": 1, "text": "After", "anchor": "after"}
        ]


class TestPagePaths:
    @pytest.mark.parametrize(
        ("pathname", "root", "expected"),
        [
            ("/", "/", "index.html"),
            ("/index.html", "/", "index.html"),
            ("/user-guide/", "/", "user-guide/index.html"),
            ("/user-guide/intro.html", "/", "user-guide/intro.html"),
            ("/user-guide/intro", "/", "user-guide/intro.html"),
            ("/docs/user-guide/intro.html", "/docs/", "user-guide/intro.html"),
            ("/docs/", "/docs/", "index.html"),
            ("/docs/a%20b.html", "/docs/", "a b.html"),
        ],
    )
    def test_page_path(self, pathname: str, root: str, expected: str):
        expression = f"internals.pagePath({json.dumps(pathname)}, {json.dumps(root)})"

        assert _internal(expression) == expected

    def test_the_site_root_is_the_script_directory(self):
        assert _internal("internals.siteRoot", scriptSrc="/docs/webmcp.js") == (
            "https://docs.example.org/docs/"
        )


class TestGetCurrentPage:
    def test_markdown_is_the_page_copy(self):
        result = _call("get_current_page")

        markdown = (SITE / "user-guide" / "intro.md").read_text(encoding="utf-8")
        assert result == {
            "url": "https://docs.example.org/user-guide/intro.html",
            "path": "user-guide/intro.html",
            "title": "Intro – Example",
            "format": "markdown",
            "source": "markdown",
            "markdown": markdown,
            "truncated": False,
        }

    def test_the_title_comes_from_the_page_heading(self):
        result = _call(
            "get_current_page",
            {"format": "outline"},
            main=["main", {}, ["header", {}, ["h1", {"class": "title"}, "Introduction"]]],
        )

        assert result["title"] == "Introduction"

    def test_a_page_under_a_subpath_fetches_beside_the_script(self):
        observed = _run(
            f"{SETTLE} return await tools.call('get_current_page', {{format: 'outline'}});",
            pathname="/docs/",
            scriptSrc="/docs/webmcp.js",
        )

        assert observed["fetched"] == ["https://docs.example.org/docs/index.md"]
        assert observed["result"]["path"] == "index.html"
        assert observed["result"]["outline"][0]["text"] == "Example"

    def test_a_long_page_is_truncated_with_its_outline(self):
        result = _call("get_current_page", {"max_chars": 500})

        assert result["truncated"] is True
        assert len(result["markdown"]) <= 500
        assert result["total_chars"] > 500
        assert [item["anchor"] for item in result["outline"]][-1] == "getting-started-1"

    def test_the_outline_format_returns_only_headings(self):
        result = _call("get_current_page", {"format": "outline"})

        assert "markdown" not in result
        assert result["outline"][2] == {"level": 2, "text": "Options", "anchor": "sec-options"}

    def test_repeated_calls_fetch_once(self):
        observed = _run(
            "await tools.call('get_current_page'); await tools.call('get_current_page');"
        )

        assert observed["fetched"] == ["https://docs.example.org/user-guide/intro.md"]

    MAIN = [
        "main",
        {},
        [
            "section",
            {"id": "setup"},
            ["h2", {"data-anchor-id": "setup"}, "Setup"],
            ["p", {}, "Install ", ["code", {}, "example"], " first."],
            ["pre", {}, "pip install example\n"],
            ["ul", {}, ["li", {}, "One"], ["li", {}, "Two"]],
            ["button", {}, "Copy"],
            ["div", {"aria-hidden": "true"}, "Hidden"],
        ],
        ["section", {"id": "usage"}, ["h3", {}, "Usage"]],
    ]

    def test_a_failed_fetch_falls_back_to_the_page_text(self):
        result = _call("get_current_page", {}, fetchFails=True, main=self.MAIN)

        assert result["source"] == "dom"
        assert "could not be loaded" in result["note"]
        assert result["markdown"] == (
            "## Setup\n\nInstall example first.\n\n```\npip install example\n```"
            "\n\n- One\n\n- Two\n\n### Usage"
        )

    def test_a_missing_copy_falls_back_to_the_page_text(self):
        result = _call("get_current_page", {"format": "outline"}, pathname="/nowhere.html")

        assert result["source"] == "dom"

    def test_without_markdown_pages_the_page_text_is_used_without_fetching(self):
        observed = _run(
            "return await tools.call('get_current_page', {format: 'outline'});",
            settings={"markdown_pages": False},
            main=self.MAIN,
        )

        assert observed["fetched"] == []
        assert observed["result"]["source"] == "dom"
        assert "note" not in observed["result"]
        assert observed["result"]["outline"] == [
            {"level": 2, "text": "Setup", "anchor": "setup"},
            {"level": 3, "text": "Usage", "anchor": "usage"},
        ]

    def test_a_cancelled_call_returns_an_error(self):
        observed = _run(
            f"{SETTLE} const controller = new AbortController();"
            " const tool = browser.tools.find((t) => t.name === 'get_current_page');"
            " const pending = tool.execute({}, {signal: controller.signal});"
            " controller.abort(); return await pending;"
        )

        assert observed["result"]["error"]["code"] == "unavailable"


def _variant(tmp_path: Path, search: list[dict[str, str]] | None = None) -> Path:
    """Build the fixture site in `tmp_path`, then replace its search index with `search`"""
    site_dir = _build_site(tmp_path)
    if search is not None:
        _ = (site_dir / "search.json").write_text(json.dumps(search), encoding="utf-8")
    return site_dir


class TestToolDescriptions:
    @pytest.mark.parametrize("name", [*SITE_TOOLS, *API_TOOLS])
    @pytest.mark.parametrize("body", [[], ["doc-api-page", "doc-py-api-page"]])
    def test_descriptions_say_when_to_use_the_tool(self, name: str, body: list[str]):
        listed = _run("return tools.list();", settings=WITH_API, bodyClasses=body)["result"]
        [tool] = [tool for tool in listed if tool["name"] == name]

        description = tool["description"]
        assert description.startswith("Use this")
        assert len(description) <= 450
        assert 'Example: "' in description

    def test_titles_match_the_tool_list(self):
        listed = _run("return tools.list();")["result"]

        titles = {tool.name: tool.title for tool in TOOLS}
        assert [tool["title"] for tool in listed] == [titles[tool["name"]] for tool in listed]


class TestGetSiteOverview:
    def test_the_overview_describes_the_package_and_its_sections(self):
        result = _call("get_site_overview")

        assert {key: result[key] for key in ("name", "version", "install", "license")} == {
            "name": "example",
            "version": "1.2.0",
            "install": ["pip install example"],
            "license": "MIT",
        }
        assert result["url"] == BASE
        assert result["repo"] == "https://github.com/acme/example"
        assert result["sections"] == [
            {"id": "user-guide", "title": "User Guide", "kind": "guide", "pages": 3},
            {"id": "blog", "title": "Blog", "kind": "blog", "pages": 3},
            {"id": "reference", "title": "Reference", "kind": "reference", "pages": 8},
        ]
        assert result["pages"] == 16
        assert result["resources"] == {
            "llms_txt": f"{BASE}llms.txt",
            "search": f"{BASE}search.json",
        }
        assert result["current_page"]["path"] == "user-guide/intro.html"

    def test_the_tools_are_those_registered_with_their_purposes(self):
        observed = _run(
            "tools.add({name: 'site.echo', title: 'Echo', description: 'Echo.',"
            " execute: () => 1});"
            " return await tools.call('get_site_overview');",
            settings={"exclude": ["search_docs"]},
        )

        expected = [
            {"name": tool.name, "title": tool.title, "purpose": tool.purpose}
            for tool in TOOLS
            if tool.name in SITE_TOOLS and tool.name != "search_docs"
        ]
        expected.append({"name": "site.echo", "title": "Echo", "purpose": "Echo"})
        assert observed["result"]["tools"] == expected

    def test_without_the_manifest_the_overview_still_lists_the_tools(self):
        result = _call("get_site_overview", fetchFails=True)

        assert "could not be loaded" in result["note"]
        assert [tool["name"] for tool in result["tools"]] == SITE_TOOLS
        assert "sections" not in result

    def test_the_manifest_is_fetched_once_and_the_search_index_not_at_all(self):
        observed = _run(
            "await tools.call('get_site_overview'); await tools.call('list_pages');"
            " await tools.call('get_page', {page: 'deploy'});"
        )

        assert observed["fetched"] == [f"{BASE}gd-webmcp.json", f"{BASE}user-guide/02-deploy.md"]


class TestListPages:
    def test_pages_are_grouped_by_section_in_order(self):
        result = _call("list_pages")

        sections = result["sections"]
        assert [section["id"] for section in sections] == ["", "user-guide", "blog", "reference"]
        assert [page["url"] for page in sections[1]["pages"]] == [
            f"{BASE}user-guide/intro.html",
            f"{BASE}user-guide/setup.html",
            f"{BASE}user-guide/02-deploy.html",
        ]

    def test_entries_carry_their_details(self):
        result = _call("list_pages", {"section": "user-guide"})

        assert result["sections"][0]["pages"][2] == {
            "title": "Deploying the site",
            "url": f"{BASE}user-guide/02-deploy.html",
            "description": "Publish the docs to GitHub Pages or Netlify.",
            "kind": "guide",
            "group": "Publishing",
            "status": "new",
        }

    def test_blog_posts_come_newest_first(self):
        result = _call("list_pages", {"section": "blog"})

        pages = result["sections"][0]["pages"]
        assert [(page["title"], page.get("date")) for page in pages] == [
            ("Blog", None),
            ("Setup", "2026-03-01"),
            ("Launch day", "2026-01-02"),
        ]

    @pytest.mark.parametrize("section", ["reference", "REFERENCE", "Reference"])
    def test_a_section_is_named_by_id_or_title(self, section: str):
        result = _call("list_pages", {"section": section})

        assert [section["id"] for section in result["sections"]] == ["reference"]

    def test_an_unknown_section_lists_the_sections(self):
        result = _call("list_pages", {"section": "recipes"})

        assert result["error"]["code"] == "not_found"
        assert [item["id"] for item in result["error"]["candidates"]] == [
            "user-guide",
            "blog",
            "reference",
        ]

    def test_a_failed_fetch_points_to_other_files(self):
        result = _call("list_pages", fetchFails=True)

        assert result["error"]["code"] == "fetch_failed"
        assert result["error"]["fallback"] == [
            f"{BASE}llms.txt",
            f"{BASE}llms-full.txt",
            f"{BASE}search.json",
        ]


class TestGetPage:
    @pytest.mark.parametrize(
        ("page", "path", "match"),
        [
            ("user-guide/02-deploy.html", "user-guide/02-deploy.html", "path"),
            ("/user-guide/02-deploy", "user-guide/02-deploy.html", "path"),
            ("user-guide/02-deploy.md", "user-guide/02-deploy.html", "path"),
            (f"{BASE}user-guide/02-deploy.html", "user-guide/02-deploy.html", "path"),
            ("reference/cli/", "reference/cli/index.html", "path"),
            ("reference/cli", "reference/cli/index.html", "path"),
            ("example.Widget.spin", "reference/Widget.spin.html", "api"),
            ("Widget", "reference/Widget.html", "api"),
            ("deploying the SITE", "user-guide/02-deploy.html", "title"),
            ("02-deploy", "user-guide/02-deploy.html", "name"),
            ("deploy", "user-guide/02-deploy.html", "name"),
            ("netlify publishing", "user-guide/02-deploy.html", "words"),
            ("deployment", "user-guide/02-deploy.html", "words"),
        ],
    )
    def test_a_page_is_found_by_path_api_name_title_file_name_or_words(
        self, page: str, path: str, match: str
    ):
        result = _call("get_page", {"page": page})

        assert (result["path"], result["match"]) == (path, match)
        assert result["url"] == BASE + path
        assert result["markdown"] == (SITE / path.replace(".html", ".md")).read_text(
            encoding="utf-8"
        )
        assert result["truncated"] is False

    def test_a_shared_title_is_ambiguous(self):
        result = _call("get_page", {"page": "Setup"})

        assert result["error"]["code"] == "ambiguous"
        assert [item["url"] for item in result["error"]["candidates"]] == [
            f"{BASE}user-guide/setup.html",
            f"{BASE}blog/setup.html",
        ]

    def test_close_word_matches_are_ambiguous(self):
        result = _call("get_page", {"page": "widget class"})

        assert result["error"]["code"] == "ambiguous"
        assert [item["title"] for item in result["error"]["candidates"]] == [
            "Widget",
            "Widget.spin",
        ]

    @pytest.mark.parametrize("page", ["nothing like it", "https://elsewhere.org/intro.html"])
    def test_an_unknown_page_is_not_found(self, page: str):
        result = _call("get_page", {"page": page})

        assert result["error"]["code"] == "not_found"
        assert result["error"]["hint"]

    @pytest.mark.parametrize(
        "section", ["github-pages", "#github-pages", "GitHub Pages", "github pages"]
    )
    def test_a_section_is_named_by_anchor_or_heading(self, section: str):
        result = _call("get_page", {"page": "deploy", "section": section})

        assert result["url"] == f"{BASE}user-guide/02-deploy.html#github-pages"
        assert result["section"] == {"level": 2, "text": "GitHub Pages", "anchor": "github-pages"}
        # The section runs to the next heading of its level, past a `#` line in a code block.
        assert result["markdown"] == (
            "## GitHub Pages {#github-pages}\n\n"
            "Push to the `gh-pages` branch, or let the workflow deploy it:\n\n"
            "```yaml\n# deploy on every push\non: push\n```\n\n"
            "### Custom domains\n\nAdd a `CNAME` file.\n"
        )

    def test_an_anchor_of_the_rendered_page_names_its_section(self):
        result = _call("get_page", {"page": "Widget", "section": "#widget-params"})

        assert result["url"] == f"{BASE}reference/Widget.html#widget-params"
        assert result["markdown"] == (
            "## Parameters\n\n`speed: int = 1`  \nHow fast the widget spins.\n"
        )

    def test_the_anchor_of_a_page_url_names_the_section(self):
        result = _call("get_page", {"page": f"{BASE}user-guide/02-deploy.html#netlify"})

        assert result["section"]["text"] == "Netlify"

    def test_a_page_url_anchor_that_names_no_section_is_ignored(self):
        result = _call("get_page", {"page": "user-guide/02-deploy.html#gone"})

        assert "section" not in result
        assert result["markdown"].startswith("# Deploying the site")

    def test_a_repeated_heading_is_ambiguous(self):
        result = _call("get_page", {"page": "intro", "section": "Getting started"})

        assert result["error"]["code"] == "ambiguous"
        assert [item["anchor"] for item in result["error"]["candidates"]] == [
            "getting-started",
            "getting-started-1",
        ]

    def test_an_unknown_section_lists_the_outline(self):
        result = _call("get_page", {"page": "intro", "section": "Nowhere"})

        assert result["error"]["code"] == "not_found"
        assert [item["text"] for item in result["error"]["candidates"]] == [
            "Introduction",
            "Getting started",
            "Options",
            "The level option",
            "Getting started",
        ]

    def test_a_long_page_is_truncated_with_its_outline(self):
        result = _call("get_page", {"page": "intro", "max_chars": 500})

        assert result["truncated"] is True
        assert len(result["markdown"]) <= 500
        assert result["total_chars"] > 500
        assert [item["anchor"] for item in result["outline"]][-1] == "getting-started-1"

    def test_a_page_without_a_markdown_copy_is_unavailable(self):
        result = _call("get_page", {"page": "notes"})

        assert result["error"] == {
            "code": "unavailable",
            "message": "notes.html has no Markdown copy.",
            "url": f"{BASE}notes.html",
        }

    def test_a_missing_markdown_copy_points_to_other_files(self, tmp_path: Path):
        site_dir = _variant(tmp_path)
        (site_dir / "user-guide" / "setup.md").unlink()

        result = _call("get_page", {"page": "user-guide/setup.html"}, siteDir=str(site_dir))

        assert result["error"]["code"] == "fetch_failed"
        assert "user-guide/setup.md" in result["error"]["message"]
        assert len(result["error"]["fallback"]) == 3

    def test_a_missing_manifest_points_to_other_files(self):
        result = _call("get_page", {"page": "intro"}, fetchFails=True)

        assert result["error"]["code"] == "fetch_failed"
        assert f"{BASE}llms.txt" in result["error"]["fallback"]


def _entry(href: str, title: str, section: str = "", text: str = "") -> dict[str, str]:
    return {"href": href, "title": title, "section": section, "text": text}


class TestSearchDocs:
    def test_a_question_finds_the_section_that_answers_it(self):
        result = _call("search_docs", {"query": "How do I deploy to GitHub Pages?"})

        first = result["results"][0]
        assert first == {
            "title": "Deploying the site",
            "section": "GitHub Pages",
            "url": f"{BASE}user-guide/02-deploy.html#github-pages",
            "kind": "guide",
            "score": first["score"],
            "excerpt": "Push to the gh-pages branch, or let the workflow deploy it to GitHub Pages.",
        }
        assert isinstance(first["score"], (int, float))

    def test_pages_left_out_of_the_manifest_are_not_searched(self):
        result = _call("search_docs", {"query": "secrets"})

        assert result["results"] == []
        assert result["hint"]

    def test_title_beats_heading_beats_text(self, tmp_path: Path):
        site_dir = _variant(
            tmp_path,
            [
                _entry("blog/launch.html", "Launch day", text="A gizmo appears."),
                _entry("user-guide/setup.html#gizmos", "Setup", "Gizmo", "Text."),
                _entry("notes.html", "Gizmo", text="Notes."),
            ],
        )

        result = _call("search_docs", {"query": "gizmo"}, siteDir=str(site_dir))

        assert [hit["url"] for hit in result["results"]] == [
            f"{BASE}notes.html",
            f"{BASE}user-guide/setup.html#gizmos",
            f"{BASE}blog/launch.html",
        ]
        assert [hit["score"] for hit in result["results"]] == [13, 8, 4]

    def test_a_page_gives_at_most_two_matches(self, tmp_path: Path):
        site_dir = _variant(
            tmp_path,
            [_entry(f"user-guide/setup.html#s{n}", "Setup", "Gizmo") for n in range(4)]
            + [_entry("notes.html", "Notes", text="gizmo")],
        )

        result = _call("search_docs", {"query": "gizmo"}, siteDir=str(site_dir))

        assert [hit["url"] for hit in result["results"]] == [
            f"{BASE}user-guide/setup.html#s0",
            f"{BASE}user-guide/setup.html#s1",
            f"{BASE}notes.html",
        ]

    def test_an_api_name_finds_its_page_first(self):
        result = _call("search_docs", {"query": "Widget.spin"})

        assert result["results"][0]["url"] == f"{BASE}reference/Widget.spin.html"
        assert result["results"][0]["kind"] == "api"

    @pytest.mark.parametrize(
        ("scope", "urls"),
        [
            ("blog", [f"{BASE}blog/launch.html"]),
            ("post", [f"{BASE}blog/launch.html"]),
            ("user-guide", [f"{BASE}user-guide/02-deploy.html#github-pages"]),
            ("User Guide", [f"{BASE}user-guide/02-deploy.html#github-pages"]),
        ],
    )
    def test_a_scope_keeps_a_kind_of_page_or_a_section(self, scope: str, urls: list[str]):
        result = _call("search_docs", {"query": "deploy", "scope": scope, "limit": 1})

        assert [hit["url"] for hit in result["results"]] == urls

    def test_an_unknown_scope_lists_the_scopes(self):
        result = _call("search_docs", {"query": "deploy", "scope": "recipes"})

        assert result["error"]["code"] == "not_found"
        assert result["error"]["candidates"][0] == "all"
        assert {"guide", "api", "cli", "blog", "user-guide"} <= set(result["error"]["candidates"])

    @pytest.mark.parametrize("limit", [0, 26])
    def test_the_limit_is_bounded(self, limit: int):
        result = _call("search_docs", {"query": "deploy", "limit": limit})

        assert result["error"]["code"] == "invalid_input"

    def test_a_query_without_words_is_invalid(self):
        result = _call("search_docs", {"query": "?!"})

        assert result["error"]["code"] == "invalid_input"

    def test_html_entities_in_the_index_are_decoded(self):
        result = _call("search_docs", {"query": "launched", "limit": 1})

        assert result["results"][0]["excerpt"] == (
            "We launched Example. Deploy it today & tell a friend."
        )

    def test_a_missing_index_points_to_other_files(self, tmp_path: Path):
        site_dir = _variant(tmp_path)
        (site_dir / "search.json").unlink()

        result = _call("search_docs", {"query": "deploy"}, siteDir=str(site_dir))

        assert result["error"]["code"] == "fetch_failed"
        assert result["error"]["fallback"] == [f"{BASE}llms.txt", f"{BASE}llms-full.txt"]


class TestListApi:
    def test_objects_are_grouped_by_reference_section(self):
        result = _call("list_api", {}, settings=WITH_API)

        assert result == {
            "url": f"{BASE}reference/index.html",
            "sections": [
                {
                    "title": "Classes",
                    "objects": [
                        {
                            "name": "example.Widget",
                            "kind": "class",
                            "summary": "A widget that spins.",
                            "url": f"{BASE}reference/Widget.html",
                        },
                        {
                            "name": "example.Widget.spin",
                            "kind": "method",
                            "summary": "Spin the widget.",
                            "url": f"{BASE}reference/Widget.spin.html",
                        },
                        {
                            "name": "example.Widget.stop",
                            "kind": "method",
                            "url": f"{BASE}reference/Widget.html",
                        },
                    ],
                },
                {
                    "objects": [
                        {
                            "name": "example.stop",
                            "kind": "function",
                            "url": f"{BASE}reference/stop.html",
                        }
                    ]
                },
            ],
        }

    def test_a_section_is_named_by_its_title_in_any_case(self):
        result = _call("list_api", {"section": "classes"}, settings=WITH_API)

        assert [section["title"] for section in result["sections"]] == ["Classes"]

    def test_an_unknown_section_lists_the_sections(self):
        result = _call("list_api", {"section": "Functions"}, settings=WITH_API)

        assert result["error"]["code"] == "not_found"
        assert result["error"]["candidates"] == ["Classes"]

    def test_a_failed_manifest_load_points_to_other_files(self):
        result = _call("list_api", {}, settings=WITH_API, fetchFails=True)

        assert result["error"]["code"] == "fetch_failed"
        assert f"{BASE}llms.txt" in result["error"]["fallback"]


class TestGetApiReference:
    # The body classes of an object's reference page.
    API_PAGE = ["doc-api-page", "doc-py-api-page"]

    def test_a_reference_is_split_into_its_parts(self):
        result = _call("get_api_reference", {"name": "example.Widget.spin"}, settings=WITH_API)

        assert result == {
            "name": "example.Widget.spin",
            "kind": "method",
            "url": f"{BASE}reference/Widget.spin.html",
            "match": "name",
            "summary": "Spin the widget.",
            "signature": "Widget.spin(times=1)",
            "sections": {
                "parameters": "`times: int = 1`  \nHow many turns to make.",
                "returns": "`int`  \nThe turns made.",
                "raises": "`ValueError`  \nIf `times` is negative.",
                "examples": "``` python\nWidget().spin(times=3)\n```",
            },
        }

    def test_a_class_reference_has_its_description_and_leaves_methods_whole(self):
        result = _call("get_api_reference", {"name": "Widget"}, settings=WITH_API)

        assert result["match"] == "alias"
        assert result["url"] == f"{BASE}reference/Widget.html"
        assert result["signature"] == "Widget(speed=1)"
        assert result["description"] == "Widgets spin in place until stopped."
        assert list(result["sections"]) == ["parameters", "methods", "examples"]
        assert result["sections"]["methods"].endswith("Whether the widget was spinning.")

    def test_a_method_documented_with_its_class_is_read_from_its_heading(self):
        result = _call("get_api_reference", {"name": "Widget.stop"}, settings=WITH_API)

        assert result == {
            "name": "example.Widget.stop",
            "kind": "method",
            "url": f"{BASE}reference/Widget.html#stop",
            "match": "alias",
            "summary": "Stop the widget.",
            "signature": "Widget.stop(now=False)",
            "sections": {"returns": "`bool`  \nWhether the widget was spinning."},
        }

    @pytest.mark.parametrize(
        ("name", "match"),
        [
            ("spin", "alias"),
            ("spin()", "alias"),
            ("WIDGET.SPIN", "case"),
            (".Widget.spin", "suffix"),
            ("example.widget.stop", "case"),
        ],
    )
    def test_a_name_can_be_short_in_any_case_or_end_a_full_name(self, name: str, match: str):
        result = _call("get_api_reference", {"name": name}, settings=WITH_API)

        assert result["match"] == match

    def test_a_shared_name_is_ambiguous(self):
        result = _call("get_api_reference", {"name": "stop"}, settings=WITH_API)

        assert result["error"]["code"] == "ambiguous"
        assert [item["name"] for item in result["error"]["candidates"]] == [
            "example.Widget.stop",
            "example.stop",
        ]

    def test_an_unknown_name_suggests_objects_sharing_its_words(self):
        result = _call("get_api_reference", {"name": "widget turns"}, settings=WITH_API)

        assert result["error"]["code"] == "not_found"
        assert result["error"]["candidates"][0]["name"] == "example.Widget"
        assert "list_api" in result["error"]["hint"]

    def test_include_picks_the_parts(self):
        result = _call(
            "get_api_reference",
            {"name": "Widget.spin", "include": ["signature", "raises"]},
            settings=WITH_API,
        )

        assert result["signature"] == "Widget.spin(times=1)"
        assert list(result["sections"]) == ["raises"]
        assert "markdown" not in result

    def test_markdown_is_the_whole_reference(self):
        result = _call(
            "get_api_reference",
            {"name": "Widget.stop", "include": ["markdown"]},
            settings=WITH_API,
        )

        assert "signature" not in result and "sections" not in result
        assert result["markdown"].startswith("### stop()\n")
        assert result["markdown"].endswith("Whether the widget was spinning.\n")
        assert "## Examples" not in result["markdown"]

    def test_an_unknown_part_is_invalid(self):
        result = _call(
            "get_api_reference", {"name": "Widget", "include": ["notes"]}, settings=WITH_API
        )

        assert result["error"]["code"] == "invalid_input"

    def test_an_object_without_a_markdown_copy_links_its_page(self):
        result = _call("get_api_reference", {"name": "example.stop"}, settings=WITH_API)

        assert result["error"]["code"] == "unavailable"
        assert result["error"]["url"] == f"{BASE}reference/stop.html"

    def test_a_missing_markdown_copy_points_to_other_files(self, tmp_path: Path):
        site_dir = _variant(tmp_path)
        (site_dir / "reference" / "Widget.spin.md").unlink()

        result = _call(
            "get_api_reference", {"name": "spin"}, settings=WITH_API, siteDir=str(site_dir)
        )

        assert result["error"]["code"] == "fetch_failed"
        assert "reference/Widget.spin.md" in result["error"]["message"]

    def test_the_name_is_required_off_an_object_page(self):
        result = _call("get_api_reference", {}, settings=WITH_API)

        assert result["error"]["code"] == "invalid_input"

    @pytest.mark.parametrize(
        ("path", "name"),
        [
            ("/reference/Widget.html", "example.Widget"),
            ("/reference/Widget.spin.html", "example.Widget.spin"),
        ],
    )
    def test_on_an_object_page_the_name_defaults_to_its_object(self, path: str, name: str):
        result = _call(
            "get_api_reference", {}, settings=WITH_API, pathname=path, bodyClasses=self.API_PAGE
        )

        assert (result["name"], result["match"]) == (name, "page")

    def test_on_an_object_page_another_object_can_be_named(self):
        result = _call(
            "get_api_reference",
            {"name": "Widget.stop"},
            settings=WITH_API,
            pathname="/reference/Widget.spin.html",
            bodyClasses=self.API_PAGE,
        )

        assert result["name"] == "example.Widget.stop"

    def test_a_reference_page_without_an_object_needs_a_name(self):
        result = _call(
            "get_api_reference",
            {},
            settings=WITH_API,
            pathname="/reference/typing.html",
            bodyClasses=self.API_PAGE,
        )

        assert result["error"]["code"] == "invalid_input"
        assert "name" in result["error"]["message"]

    @pytest.mark.parametrize(
        ("body", "required"),
        [
            (["doc-api-page", "doc-py-api-page"], None),
            (["doc-api-page", "doc-cli-api-page"], ["name"]),
            ([], ["name"]),
        ],
    )
    def test_only_an_object_page_makes_the_name_optional(
        self, body: list[str], required: list[str] | None
    ):
        listed = _run("return tools.list();", settings=WITH_API, bodyClasses=body)["result"]
        [tool] = [tool for tool in listed if tool["name"] == "get_api_reference"]

        assert tool["inputSchema"].get("required") == required
        assert ("this page" in tool["description"]) is (required is None)

    def test_the_tools_need_an_api_reference(self):
        observed = _run(
            f"{SETTLE} return await tools.call('list_api', {{}});",
            settings={"features": {"api": False}},
        )

        assert observed["registered"] == SITE_TOOLS
        assert observed["result"]["error"]["code"] == "not_found"

    def test_with_an_api_reference_the_tools_register(self):
        observed = _run(SETTLE, settings=WITH_API)

        assert observed["registered"] == [*SITE_TOOLS, *API_TOOLS]

    def test_a_reference_without_a_code_block_has_a_summary_and_description(self):
        markdown = "# helper()\n\nHelp out.\n\nIn more detail.\n\n## Returns\n\nNothing.\n"

        parts = _internal(
            f"internals.referenceParts({json.dumps(markdown)}, {{name: 'example.helper'}})"
        )

        assert parts == {
            "anchor": None,
            "summary": "Help out.",
            "signature": None,
            "description": "In more detail.",
            "sections": {"returns": "Nothing."},
            "markdown": markdown,
        }


class TestGetCliHelp:
    # The settings of a site with CLI reference pages.
    WITH_CLI = {"features": {"cli": True}}

    def _call(self, tool_input: object = None, **options: Any) -> dict[str, Any]:
        return _call("get_cli_help", tool_input, settings=self.WITH_CLI, **options)

    def test_without_a_command_the_root_command_is_returned(self):
        result = self._call({})

        assert result == {
            "command": "example",
            "url": f"{BASE}reference/cli/example.html",
            "subcommands": [
                {"command": "example build", "url": f"{BASE}reference/cli/build.html"},
                {"command": "example config", "url": f"{BASE}reference/cli/config.html"},
            ],
            "markdown": (SITE / "reference" / "cli" / "example.md").read_text(encoding="utf-8"),
        }

    @pytest.mark.parametrize(
        "command",
        ["config show", "example config show", "  Config   SHOW ", "example  config show"],
    )
    def test_a_nested_command_is_named_with_or_without_the_program(self, command: str):
        result = self._call({"command": command})

        assert result["command"] == "example config show"
        assert result["url"] == f"{BASE}reference/cli/config/show.html"
        assert result["subcommands"] == []
        assert result["markdown"].startswith("# example config show\n")

    def test_a_group_lists_only_its_direct_subcommands(self):
        result = self._call({"command": "example"})

        assert [item["command"] for item in result["subcommands"]] == [
            "example build",
            "example config",
        ]

    def test_an_unknown_command_suggests_commands_sharing_its_words(self):
        result = self._call({"command": "config edit"})

        assert result["error"]["code"] == "not_found"
        assert [item["command"] for item in result["error"]["candidates"]] == [
            "example config",
            "example config show",
        ]
        assert result["error"]["hint"]

    def test_on_a_command_page_the_command_defaults_to_its_own(self):
        result = self._call(
            {},
            pathname="/reference/cli/build.html",
            bodyClasses=["doc-api-page", "doc-cli-api-page"],
        )

        assert result["command"] == "example build"

    def test_a_missing_markdown_copy_points_to_other_files(self, tmp_path: Path):
        site_dir = _variant(tmp_path)
        (site_dir / "reference" / "cli" / "build.md").unlink()

        result = self._call({"command": "build"}, siteDir=str(site_dir))

        assert result["error"]["code"] == "fetch_failed"
        assert "reference/cli/build.md" in result["error"]["message"]

    def test_a_site_without_commands_says_so(self, tmp_path: Path):
        site_dir = _variant(tmp_path)
        manifest_file = site_dir / "gd-webmcp.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        _ = manifest_file.write_text(json.dumps({**manifest, "cli": []}), encoding="utf-8")

        result = self._call({}, siteDir=str(site_dir))

        assert result["error"]["code"] == "unavailable"

    def test_the_tool_needs_a_cli_reference(self):
        assert _run(SETTLE)["registered"] == SITE_TOOLS
        assert _run(SETTLE, settings=self.WITH_CLI)["registered"] == [*SITE_TOOLS, "get_cli_help"]

    def test_the_description_says_when_to_use_the_tool(self):
        listed = _run("return tools.list();", settings=self.WITH_CLI)["result"]
        [tool] = [tool for tool in listed if tool["name"] == "get_cli_help"]

        assert tool["description"].startswith("Use this")
        assert len(tool["description"]) <= 450
        assert 'Example: "' in tool["description"]


class TestWords:
    def test_identifiers_are_kept_whole_and_split(self):
        assert _internal("internals.tokenize('Use GT.fmt_number() here')") == [
            "use",
            "gt.fmt_number",
            "gt",
            "fmt_number",
            "fmt",
            "number",
            "here",
        ]

    def test_queries_drop_common_words_unless_they_have_only_those(self):
        assert _internal("internals.queryWords('How do I install it?')") == ["install"]
        assert _internal("internals.queryWords('how to')") == ["how", "to"]

    def test_excerpts_are_cut_between_words(self):
        text = " ".join(f"word{n}" for n in range(200))

        excerpt = _internal(f"internals.excerpt({json.dumps(text)}, {text.index('word100')})")

        assert excerpt.startswith("…word") and excerpt.endswith("…")
        assert "word100" in excerpt
        assert len(excerpt) <= 242
        assert excerpt[1:-1] in text


def test_the_runtime_stays_small():
    # Servers send the runtime compressed, so the compressed size is the tighter limit.
    raw = RUNTIME.read_bytes()

    assert len(raw) <= 96 * 1024
    assert len(gzip.compress(raw)) <= 20 * 1024
