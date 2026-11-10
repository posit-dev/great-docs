import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from great_docs._build import generated
from great_docs._project.layout import Layout
from great_docs._website.ai_agents import llms_txt
from great_docs._website.ai_agents.webmcp_tools import TOOLS
from tests.support import write_config, write_pyproject

# The standard library's `json` always imports; its `dumps` and `JSONDecoder.decode`
# docstrings provide stable expectations for the documented package.
DUMPS_SUMMARY = "Serialize ``obj`` to a JSON formatted ``str``"


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    """Create a project layout with an existing build directory"""
    (tmp_path / "great-docs.yml").write_text("", encoding="utf-8")
    layout = Layout.make(tmp_path)
    layout.build_dir.mkdir(parents=True)
    return layout


def _api_reference(package: str, *sections: dict[str, Any]) -> dict[str, Any]:
    """
    Create an API reference configuration

    Parameters
    ----------
    package
        The documented package.
    *sections
        The reference sections.

    Returns
    -------
    :
        The configuration.
    """
    return {"package": package, "sections": list(sections)}


def _write_index(
    layout: Layout,
    api_block: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    site_url: str | None = None,
) -> str:
    """Write `llms.txt` in the layout's build directory and return its text"""
    path = llms_txt.write_index(
        layout, api_block, metadata or {}, site_url=site_url, report=lambda _: None
    )
    assert path is not None
    return path.read_text(encoding="utf-8")


def _write_full(
    layout: Layout,
    api_block: dict[str, Any],
    cli: dict[str, Any] | None = None,
    user_guide: dict[str, Any] | None = None,
) -> str:
    """Write `llms-full.txt` in the layout's build directory and return its text"""
    path = llms_txt.write_full(
        layout, api_block, cli=cli, user_guide=user_guide, report=lambda _: None
    )
    assert path is not None
    return path.read_text(encoding="utf-8")


SECTION = {"title": "Core", "contents": ["dumps"]}

# API reference configurations (`None` for a site without one), expected file
# availability, and whether the index is written.
GUARD_CASES: dict[str, tuple[dict[str, Any] | None, bool, bool]] = {
    "no API reference": (None, False, False),
    "no sections": ({"package": "json", "sections": []}, False, False),
    "no package": ({"sections": [SECTION]}, False, False),
    # The index can list an unimportable package without summaries; the full file
    # requires an importable package.
    "unimportable package": (_api_reference("no_such_package_xyz", SECTION), False, True),
    "importable package with sections": (_api_reference("json", SECTION), True, True),
}


@pytest.mark.parametrize("label", GUARD_CASES)
def test_writes_the_full_file_exactly_when_planned(label: str, layout: Layout):
    api_block, planned, index_written = GUARD_CASES[label]

    index = llms_txt.write_index(layout, api_block, {}, site_url=None, report=lambda _: None)
    full = llms_txt.write_full(layout, api_block, cli=None, user_guide=None, report=lambda _: None)

    assert llms_txt.is_planned(api_block) is planned
    assert (full is not None) is planned
    assert (layout.build_dir / "llms-full.txt").exists() is planned
    assert (index is not None) is index_written
    assert (layout.build_dir / "llms.txt").exists() is index_written


def test_reports_the_written_files(layout: Layout):
    api_block = _api_reference("json", SECTION)
    lines: list[str] = []

    llms_txt.write_index(layout, api_block, {}, site_url=None, report=lines.append)
    llms_txt.write_full(layout, api_block, cli=None, user_guide=None, report=lines.append)

    assert lines == [
        f"Created {layout.build_dir / 'llms.txt'}",
        f"Created {layout.build_dir / 'llms-full.txt'}",
    ]


def test_reports_a_package_that_does_not_import(layout: Layout):
    api_block = _api_reference("no_such_package_xyz", SECTION)
    lines: list[str] = []

    llms_txt.write_full(layout, api_block, cli=None, user_guide=None, report=lines.append)

    assert lines == ["Could not import no_such_package_xyz: No module named 'no_such_package_xyz'"]


def test_index_lists_each_section_with_links_and_summaries(layout: Layout):
    api_block = _api_reference(
        "json",
        {"title": "Encoding", "desc": "Write JSON", "contents": ["dumps"]},
        {"subtitle": "Decoding", "contents": [{"name": "JSONDecoder", "members": []}]},
    )

    text = _write_index(layout, api_block, {"description": "A JSON library"})

    assert text.split("\n") == [
        "# json",
        "",
        "> A JSON library",
        "",
        "## Docs",
        "",
        "### API Reference",
        "",
        "#### Encoding",
        "> Write JSON",
        "",
        f"- [dumps](reference/dumps.html): {DUMPS_SUMMARY}",
        "",
        "#### Decoding",
        "",
        "- [JSONDecoder](reference/JSONDecoder.html): Simple JSON <https://json.org> decoder",
        "",
    ]


def test_index_has_no_section_heading_for_a_single_section(layout: Layout):
    api_block = _api_reference("json", SECTION)

    text = _write_index(layout, api_block)

    assert "####" not in text
    assert "> " not in text


def test_index_links_a_module_qualified_entry_to_its_page(layout: Layout):
    api_block = _api_reference(
        "pkg", {"title": "Devices", "contents": ["devices.keithley:Keithley2400"]}
    )

    text = _write_index(layout, api_block)

    assert "- [devices.keithley:Keithley2400](reference/devices.keithley.Keithley2400.html)" in text


@pytest.mark.parametrize(
    ("documentation", "site_url", "base"),
    [
        ("https://a.io/pkg/#readme", "https://ignored.io", "https://a.io/pkg/"),
        ("", "https://example.com/docs", "https://example.com/docs/"),
    ],
)
def test_index_links_are_absolute_with_a_site_url(
    documentation: str, site_url: str, base: str, layout: Layout
):
    text = _write_index(
        layout,
        _api_reference("json", SECTION),
        {"urls": {"Documentation": documentation}},
        site_url=site_url,
    )

    assert f"- [dumps]({base}reference/dumps.html)" in text


def test_docstring_summary_is_the_first_line_without_its_period():
    assert llms_txt.docstring_summary("json", "dumps") == DUMPS_SUMMARY


@pytest.mark.parametrize(
    ("package", "name"),
    [("json", "no_such_name"), ("no_such_package_xyz", "dumps"), ("json", "JSONDecoder.decode")],
)
def test_docstring_summary_is_empty_when_the_object_is_not_found(package: str, name: str):
    assert llms_txt.docstring_summary(package, name) == ""


def test_full_file_holds_signatures_and_docstrings_by_section(layout: Layout):
    api_block = _api_reference(
        "json",
        {"title": "Encoding", "desc": "Write JSON", "contents": ["dumps"]},
        {"subtitle": "Decoding", "contents": [{"name": "JSONDecoder.decode"}, "missing"]},
        {"contents": ["decoder"]},
    )

    text = _write_full(layout, api_block)

    assert text.startswith(
        "-" * 70 + "\nThis is the API documentation for the json library.\n" + "-" * 70 + "\n"
    )
    assert "\n## Encoding\n\nWrite JSON\n" in text
    assert "\ndumps(obj, *, skipkeys=False," in text
    assert DUMPS_SUMMARY + "." in text
    assert "\n## Decoding\n" in text
    assert "\ndecode(self, s, " in text
    assert "missing" not in text
    # A module has no signature, so its name replaces the signature.
    assert "\njson.decoder\n\nImplementation of JSONDecoder" in text
    assert "CLI documentation" not in text
    assert "User Guide documentation" not in text


def test_full_file_holds_the_help_of_each_visible_command(layout: Layout):
    api_block = _api_reference("json", SECTION)
    cli = {
        "entry_point_name": "my-cli",
        "help_text": "Usage: my-cli [OPTIONS]",
        "commands": [
            {
                "name": "group",
                "full_path": "my-cli group",
                "help_text": "A group",
                "commands": [
                    {"name": "leaf", "full_path": "my-cli group leaf", "help_text": "A leaf"}
                ],
            },
            {"name": "secret", "full_path": "my-cli secret", "help_text": "Hidden", "hidden": True},
        ],
    }

    text = _write_full(layout, api_block, cli=cli)

    cli_part = text.split("This is the CLI documentation for the package.\n" + "-" * 70 + "\n")[1]
    assert cli_part.split("\n") == [
        "",
        "## CLI: my-cli",
        "",
        "```",
        "Usage: my-cli [OPTIONS]",
        "```",
        "",
        "### my-cli group",
        "",
        "```",
        "A group",
        "```",
        "",
        "### my-cli group leaf",
        "",
        "```",
        "A leaf",
        "```",
        "",
    ]


def test_full_file_holds_the_user_guide_pages_in_order(tmp_path: Path, layout: Layout):
    api_block = _api_reference("json", SECTION)
    guide = tmp_path / "guide"
    guide.mkdir()
    (guide / "intro.qmd").write_text("---\ntitle: Intro\n---\n\n# Welcome\n\nHello.\n")
    (guide / "usage.qmd").write_text("---\ntitle: Usage\n---\n\nJust text.\n")
    (guide / "more.qmd").write_text("No front matter.\n")
    user_guide = {
        "files": [
            {"path": guide / "intro.qmd", "title": "Intro", "section": "Basics"},
            {"path": guide / "usage.qmd", "title": "Usage", "section": "Basics"},
            {"path": guide / "missing.qmd", "title": "Missing", "section": "Gone"},
            {"path": guide / "more.qmd", "title": "More", "section": "Advanced"},
        ]
    }

    text = _write_full(layout, api_block, user_guide=user_guide)

    guide_part = text.split("This is the User Guide documentation for the package.\n")[1]
    assert guide_part.split("\n") == [
        "-" * 70,
        "",
        "",
        "## Basics",
        "",
        "# Welcome",
        "",
        "Hello.",
        "",
        "",
        "### Usage",
        "",
        "Just text.",
        "",
        "",
        "",
        "## Advanced",
        "",
        "### More",
        "",
        "No front matter.",
        "",
        "",
    ]


@pytest.mark.parametrize(
    ("page", "body"),
    [
        ("# Only a body\n", "# Only a body\n"),
        ("---\ntitle: Unclosed\n# Body\n", "---\ntitle: Unclosed\n# Body\n"),
    ],
)
def test_full_file_keeps_a_page_without_closed_front_matter(
    page: str, body: str, tmp_path: Path, layout: Layout
):
    api_block = _api_reference("json", SECTION)
    (tmp_path / "page.qmd").write_text(page)
    user_guide = {"files": [{"path": tmp_path / "page.qmd", "title": "Page"}]}

    text = _write_full(layout, api_block, user_guide=user_guide)

    assert text.endswith(f"\n{body}\n")


def test_full_file_keeps_a_page_whose_front_matter_contains_three_dashes(
    tmp_path: Path, layout: Layout
):
    """Keep the body and omit front matter containing an embedded `---`"""
    api_block = _api_reference("json", SECTION)
    (tmp_path / "page.qmd").write_text('---\ntitle: "Before --- after"\n---\n\n# Body\n')
    user_guide = {"files": [{"path": tmp_path / "page.qmd", "title": "Page"}]}

    text = _write_full(layout, api_block, user_guide=user_guide)

    assert text.endswith("\n# Body\n\n")
    assert "after" not in text


def _webmcp_section(text: str) -> list[str]:
    """Return the lines of the WebMCP section, which ends the file"""
    return text.split("\n## WebMCP tools\n")[1].split("\n")


def _write_index_with_tools(
    layout: Layout, *names: str, site_url: str | None = None, js_api: bool = True
) -> str:
    tools = [tool for tool in TOOLS if tool.name in names]
    path = llms_txt.write_index(
        layout,
        _api_reference("json", SECTION),
        {},
        site_url=site_url,
        report=lambda _: None,
        webmcp_tools=tools,
        webmcp_js_api=js_api,
    )
    assert path is not None
    return path.read_text(encoding="utf-8")


class TestWebMCPSection:
    def test_no_section_without_tools(self, layout: Layout):
        text = _write_index(layout, _api_reference("json", SECTION))

        assert "WebMCP" not in text
        assert text.endswith(f"{DUMPS_SUMMARY}\n")

    def test_the_section_lists_the_manifest_tools_and_js_api(self, layout: Layout):
        text = _write_index_with_tools(layout, "get_site_overview", "search_docs")

        assert text.startswith("# json\n\n## Docs\n")
        assert _webmcp_section(text) == [
            "",
            "An AI agent in a browser that supports WebMCP can call these tools on this site's "
            "pages. Results are JSON objects with absolute URLs.",
            "",
            "- [WebMCP manifest](gd-webmcp.json): The site's sections, pages and API names, "
            "which the tools read",
            "",
            "- `get_site_overview`: The package, its version and install commands, the site's "
            "sections and these tools",
            "- `search_docs`: Ranked matches for a query, by page section",
            "",
            "Scripts on the site's pages can call the same tools:",
            "",
            "```js",
            "window.greatDocs.tools.list();",
            'await window.greatDocs.tools.call("search_docs", { query: "install" });',
            "```",
            "",
        ]

    def test_the_manifest_link_is_absolute_with_a_site_url(self, layout: Layout):
        text = _write_index_with_tools(layout, "search_docs", site_url="https://example.com/docs")

        assert "- [WebMCP manifest](https://example.com/docs/gd-webmcp.json): " in text

    def test_no_js_api_example_without_the_js_api(self, layout: Layout):
        text = _write_index_with_tools(layout, "search_docs", js_api=False)

        assert "window.greatDocs" not in text
        assert text.endswith("- `search_docs`: Ranked matches for a query, by page section\n")

    @pytest.mark.parametrize(
        ("names", "call"),
        [
            (["get_page", "list_pages"], 'call("list_pages", {})'),
            (["get_page"], None),
        ],
    )
    def test_the_example_calls_a_listed_tool(
        self, names: list[str], call: str | None, layout: Layout
    ):
        lines = _webmcp_section(_write_index_with_tools(layout, *names))

        calls = [line for line in lines if ".call(" in line]
        assert calls == ([f"await window.greatDocs.tools.{call};"] if call else [])
        assert "window.greatDocs.tools.list();" in lines


def _build_llms_txt(tmp_path: Path, settings: dict[str, Any]) -> str:
    """Run the build step that writes `llms.txt` and return the file's text"""
    tmp_path.mkdir(parents=True, exist_ok=True)
    write_pyproject(tmp_path, "json")
    config = write_config(tmp_path, settings)
    layout = Layout.make(tmp_path)
    layout.build_dir.mkdir(parents=True)
    run = SimpleNamespace(
        api_block=_api_reference("json", SECTION),
        project=SimpleNamespace(manifest={}, name="json", importable_name=None),
        user_guide=None,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        _ = generated.llms_txt(run, config, layout)  # type: ignore[arg-type]
    return (layout.build_dir / "llms.txt").read_text(encoding="utf-8")


class TestBuildStep:
    def test_the_section_is_written_only_with_webmcp_on(self, tmp_path: Path):
        assert "## WebMCP tools" not in _build_llms_txt(tmp_path / "off", {})
        assert "## WebMCP tools" in _build_llms_txt(tmp_path / "on", {"webmcp": True})

    def test_the_configuration_chooses_the_tools_and_example(self, tmp_path: Path):
        webmcp = {"enabled": True, "exclude_tools": ["search_docs"], "js_api": False}
        text = _build_llms_txt(tmp_path, {"webmcp": webmcp})

        tools = [line.split("`")[1] for line in _webmcp_section(text) if line.startswith("- `")]
        assert tools == [
            "get_site_overview",
            "get_current_page",
            "list_pages",
            "get_page",
            "list_api",
            "get_api_reference",
        ]
        assert "window.greatDocs" not in text

    def test_a_configured_cli_reference_adds_the_cli_tool(self, tmp_path: Path):
        text = _build_llms_txt(tmp_path, {"webmcp": True, "cli": {"enabled": True}})

        tools = [line.split("`")[1] for line in _webmcp_section(text) if line.startswith("- `")]
        assert tools[-1] == "get_cli_help"
