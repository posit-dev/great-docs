"""Tests for `webmcp.js`, run with Node in a stub page."""

from __future__ import annotations

import gzip
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from great_docs._website.ai_agents.webmcp_tools import TOOLS

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "great_docs" / "assets" / "webmcp.js"
HARNESS = ROOT / "tests" / "js" / "webmcp_harness.js"
SITE = ROOT / "tests" / "fixtures" / "webmcp_site"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

SETTLE = "await settle();"


def _run(scenario: str = "", **options: Any) -> dict[str, Any]:
    """
    Run a scenario against the runtime in a stub page

    Parameters
    ----------
    scenario
        The body of an async function; see `tests/js/webmcp_harness.js`.
    **options
        The harness options. `siteDir` defaults to the fixture site.

    Returns
    -------
    :
        What the harness observed, with the scenario's return value as `result`.
    """
    options.setdefault("siteDir", str(SITE))
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
        assert observed["registered"] == ["get_current_page"]
        assert observed["warnings"] == []

    def test_navigator_model_context_is_a_fallback(self):
        observed = _run(SETTLE, modelContext="navigator")

        assert observed["status"] == "registered"
        assert observed["registered"] == ["get_current_page"]

    def test_without_webmcp_the_js_api_still_works(self):
        observed = _run(
            f"{SETTLE} return [tools.status, tools.list().map((t) => t.name),"
            " (await tools.call('get_current_page', {format: 'outline'})).source];",
            modelContext="none",
        )

        assert observed["status"] == "unavailable"
        assert observed["result"] == ["unavailable", ["get_current_page"], "markdown"]

    def test_platform_objects_keep_their_properties(self):
        observed = _run(
            f"{SETTLE} tools.add({{name: 'site_tool', description: 'A tool.', execute: () => 1}});"
            f" {SETTLE}",
            modelContext="both",
        )

        assert observed["registered"] == ["get_current_page", "site_tool"]
        assert observed["platformUnchanged"] is True

    def test_a_refused_tool_leaves_the_status_failed_and_warns_once(self):
        observed = _run(SETTLE, refuse=["get_current_page"])

        assert observed["status"] == "failed"
        assert len(observed["warnings"]) == 1
        assert "get_current_page" in observed["warnings"][0]

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
        observed = _run(SETTLE, settings={"exclude": ["get_current_page"]})

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

        assert observed["result"] == [["Get the current page", {"readOnlyHint": True}]]

    def test_the_browser_receives_plain_results(self):
        observed = _run(
            f"{SETTLE} const tool = browser.tools[0];"
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

        assert [tool["name"] for tool in listed] == ["get_current_page"]
        assert set(listed[0]) == {"name", "title", "description", "inputSchema", "annotations"}
        assert listed[0]["inputSchema"]["properties"]["format"]["enum"] == ["markdown", "outline"]

    def test_call_reports_an_unknown_tool(self):
        result = _call("get_nothing", {})

        assert result["error"]["code"] == "not_found"
        assert result["error"]["candidates"] == ["get_current_page"]

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
        assert names == ["get_current_page", "site.echo"]
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
            " const pending = browser.tools[0].execute({}, {signal: controller.signal});"
            " controller.abort(); return await pending;"
        )

        assert observed["result"]["error"]["code"] == "unavailable"


def test_the_runtime_stays_small():
    raw = RUNTIME.read_bytes()

    assert len(raw) <= 40 * 1024
    assert len(gzip.compress(raw)) <= 12 * 1024
