from pathlib import Path
from typing import Any

import pytest
from yaml12 import format_yaml

from great_docs._website.ai_agents import llms_txt

# The standard library's `json` always imports; its `dumps` and `JSONDecoder.decode`
# docstrings provide stable expectations for the documented package.
DUMPS_SUMMARY = "Serialize ``obj`` to a JSON formatted ``str``"


def _write_quarto_yml(build_dir: Path, config: object) -> None:
    """
    Write a project's `_quarto.yml`

    Parameters
    ----------
    build_dir
        The Quarto project directory.
    config
        The configuration to serialise.

    Returns
    -------
    :
        Nothing; the configuration is written to `_quarto.yml`.
    """
    (build_dir / "_quarto.yml").write_text(format_yaml(config), encoding="utf-8")


def _api_reference(package: str, *sections: dict[str, Any]) -> dict[str, Any]:
    """
    Create a Quarto configuration with an `api-reference` block

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
    return {"api-reference": {"package": package, "sections": list(sections)}}


def _write_index(build_dir: Path, metadata: dict[str, Any] | None = None) -> str:
    """
    Write `llms.txt` and return its text

    Parameters
    ----------
    build_dir
        The Quarto project directory.
    metadata
        The package metadata.

    Returns
    -------
    :
        The text of the file.
    """
    path = llms_txt.write_index(build_dir, metadata or {}, report=lambda _: None)
    assert path is not None
    return path.read_text(encoding="utf-8")


def _write_full(
    build_dir: Path,
    cli: dict[str, Any] | None = None,
    user_guide: dict[str, Any] | None = None,
) -> str:
    """
    Write `llms-full.txt` and return its text

    Parameters
    ----------
    build_dir
        The Quarto project directory.
    cli
        The discovered command-line interface.
    user_guide
        The discovered user guide.

    Returns
    -------
    :
        The text of the file.
    """
    path = llms_txt.write_full(build_dir, cli=cli, user_guide=user_guide, report=lambda _: None)
    assert path is not None
    return path.read_text(encoding="utf-8")


SECTION = {"title": "Core", "contents": ["dumps"]}

# Quarto configurations (`None` for a missing file), expected file availability, and
# whether the index is written.
GUARD_CASES: dict[str, tuple[object, bool, bool]] = {
    "no _quarto.yml": (None, False, False),
    "no api-reference": ({"project": {"type": "website"}}, False, False),
    "non-mapping root": (["foo", "bar"], False, False),
    "no sections": ({"api-reference": {"package": "json", "sections": []}}, False, False),
    "no package": ({"api-reference": {"sections": [SECTION]}}, False, False),
    # The index can list an unimportable package without summaries; the full file
    # requires an importable package.
    "unimportable package": (_api_reference("no_such_package_xyz", SECTION), False, True),
    "importable package with sections": (_api_reference("json", SECTION), True, True),
}


@pytest.mark.parametrize("label", GUARD_CASES)
def test_writes_the_full_file_exactly_when_planned(label: str, tmp_path: Path):
    config, planned, index_written = GUARD_CASES[label]
    if config is not None:
        _write_quarto_yml(tmp_path, config)

    index = llms_txt.write_index(tmp_path, {}, report=lambda _: None)
    full = llms_txt.write_full(tmp_path, cli=None, user_guide=None, report=lambda _: None)

    assert llms_txt.is_planned(tmp_path) is planned
    assert (full is not None) is planned
    assert (tmp_path / "llms-full.txt").exists() is planned
    assert (index is not None) is index_written
    assert (tmp_path / "llms.txt").exists() is index_written


def test_reports_the_written_files(tmp_path: Path):
    _write_quarto_yml(tmp_path, _api_reference("json", SECTION))
    lines: list[str] = []

    llms_txt.write_index(tmp_path, {}, report=lines.append)
    llms_txt.write_full(tmp_path, cli=None, user_guide=None, report=lines.append)

    assert lines == [f"Created {tmp_path / 'llms.txt'}", f"Created {tmp_path / 'llms-full.txt'}"]


def test_reports_a_package_that_does_not_import(tmp_path: Path):
    _write_quarto_yml(tmp_path, _api_reference("no_such_package_xyz", SECTION))
    lines: list[str] = []

    llms_txt.write_full(tmp_path, cli=None, user_guide=None, report=lines.append)

    assert lines == ["Could not import no_such_package_xyz: No module named 'no_such_package_xyz'"]


def test_index_lists_each_section_with_links_and_summaries(tmp_path: Path):
    _write_quarto_yml(
        tmp_path,
        _api_reference(
            "json",
            {"title": "Encoding", "desc": "Write JSON", "contents": ["dumps"]},
            {"subtitle": "Decoding", "contents": [{"name": "JSONDecoder", "members": []}]},
        ),
    )

    text = _write_index(tmp_path, {"description": "A JSON library"})

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


def test_index_has_no_section_heading_for_a_single_section(tmp_path: Path):
    _write_quarto_yml(tmp_path, _api_reference("json", SECTION))

    text = _write_index(tmp_path)

    assert "####" not in text
    assert "> " not in text


def test_index_links_a_module_qualified_entry_to_its_page(tmp_path: Path):
    _write_quarto_yml(
        tmp_path,
        _api_reference("pkg", {"title": "Devices", "contents": ["devices.keithley:Keithley2400"]}),
    )

    text = _write_index(tmp_path)

    assert "- [devices.keithley:Keithley2400](reference/devices.keithley.Keithley2400.html)" in text


@pytest.mark.parametrize(
    ("documentation", "site_url", "base"),
    [
        ("https://a.io/pkg/#readme", "https://ignored.io", "https://a.io/pkg/"),
        ("", "https://example.com/docs", "https://example.com/docs/"),
    ],
)
def test_index_links_are_absolute_with_a_site_url(
    documentation: str, site_url: str, base: str, tmp_path: Path
):
    config = _api_reference("json", SECTION) | {"website": {"site-url": site_url}}
    _write_quarto_yml(tmp_path, config)

    text = _write_index(tmp_path, {"urls": {"Documentation": documentation}})

    assert f"- [dumps]({base}reference/dumps.html)" in text


def test_docstring_summary_is_the_first_line_without_its_period():
    assert llms_txt.docstring_summary("json", "dumps") == DUMPS_SUMMARY


@pytest.mark.parametrize(
    ("package", "name"),
    [("json", "no_such_name"), ("no_such_package_xyz", "dumps"), ("json", "JSONDecoder.decode")],
)
def test_docstring_summary_is_empty_when_the_object_is_not_found(package: str, name: str):
    assert llms_txt.docstring_summary(package, name) == ""


def test_full_file_holds_signatures_and_docstrings_by_section(tmp_path: Path):
    _write_quarto_yml(
        tmp_path,
        _api_reference(
            "json",
            {"title": "Encoding", "desc": "Write JSON", "contents": ["dumps"]},
            {"subtitle": "Decoding", "contents": [{"name": "JSONDecoder.decode"}, "missing"]},
            {"contents": ["decoder"]},
        ),
    )

    text = _write_full(tmp_path)

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


def test_full_file_holds_the_help_of_each_visible_command(tmp_path: Path):
    _write_quarto_yml(tmp_path, _api_reference("json", SECTION))
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

    text = _write_full(tmp_path, cli=cli)

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


def test_full_file_holds_the_user_guide_pages_in_order(tmp_path: Path):
    _write_quarto_yml(tmp_path, _api_reference("json", SECTION))
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

    text = _write_full(tmp_path, user_guide=user_guide)

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
def test_full_file_keeps_a_page_without_closed_front_matter(page: str, body: str, tmp_path: Path):
    _write_quarto_yml(tmp_path, _api_reference("json", SECTION))
    (tmp_path / "page.qmd").write_text(page)
    user_guide = {"files": [{"path": tmp_path / "page.qmd", "title": "Page"}]}

    text = _write_full(tmp_path, user_guide=user_guide)

    assert text.endswith(f"\n{body}\n")
