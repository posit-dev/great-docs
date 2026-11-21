"""
Tests for ordering dependencies between site-wide Quarto settings

Each test checks a dependency between settings that tests of either setting
alone cannot cover.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from great_docs._apiref.spec import ReferenceSpec
from great_docs._build.facts import Facts
from great_docs._cliref import render as cli_render
from great_docs._mcpref import build as mcp_build
from great_docs._project.layout import Layout
from great_docs._reference import sections as reference_sections
from great_docs._website import assembly
from great_docs._website.identity import Identity
from tests.support import write_config

BASE_URL = "https://example.com/pkg/"


def _assemble(
    root: Path, settings: str, *, references: tuple[str, ...] | None = None
) -> dict[str, Any]:
    """
    Assemble the Quarto configuration of a project named `pkg`

    Parameters
    ----------
    root
        The project directory.
    settings
        The contents of `great-docs.yml`.
    references
        Reference sections to contribute, or `None` for the initial defaults.

    Returns
    -------
    :
        The configuration after merging the site's settings into the initial
        website defaults.
    """
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
    config = write_config(root, settings)
    layout = Layout.make(root)
    layout.build_dir.mkdir(parents=True, exist_ok=True)
    quarto_config: dict[str, Any] = {
        "project": {"type": "website"},
        "format": {"html": {"theme": "flatly"}},
    }
    contributions = []
    for section in references or ():
        index = "reference/index.qmd" if section == "api" else f"reference/{section}/index.qmd"
        page = layout.build_dir / index
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("---\ntitle: Reference\n---\n", encoding="utf-8")
        if section == "api":
            contributions.append(reference_sections.contribution(config, ReferenceSpec("pkg", [])))
        else:
            producer = cli_render if section == "cli" else mcp_build
            contributions.append(producer.contribution(config, [index]))
    assembly.assemble(
        quarto_config,
        config,
        layout,
        repo=None,
        facts=Facts(),
        identity=Identity(name="Pkg", url=BASE_URL, base_url=BASE_URL),
        package_name="pkg",
        metadata={},
        has_api_reference=references is None or "api" in references,
        has_cli_reference=references is not None and "cli" in references,
        has_changelog=False,
        has_skills=False,
        contributions=contributions,
        report=lambda _: None,
        warn=lambda _: None,
    )
    return quarto_config


def test_canonical_link_in_site_header_replaces_the_generated_one(tmp_path: Path):
    # Canonical links are generated after the user's header includes are added, so a
    # canonical link among them is found and not duplicated.
    quarto_config = _assemble(
        tmp_path,
        f"site_url: {BASE_URL}\n"
        "include_in_header:\n"
        f'  - text: \'<link rel="canonical" href="{BASE_URL}">\'\n',
    )

    assert not quarto_config.get("gd-canonical")


@pytest.mark.parametrize(
    ("references", "order", "target"),
    [
        (("mcp",), [], "mcp"),
        (("cli",), [], "cli"),
        (("cli", "mcp"), [], "cli"),
        (("cli", "mcp"), ["mcp", "cli"], "mcp"),
        (("api", "mcp"), [], "api"),
        (("api", "mcp"), ["mcp", "api"], "mcp"),
        (("api", "cli", "mcp"), ["mcp", "cli", "api"], "mcp"),
        ((), [], None),
    ],
)
@pytest.mark.parametrize(("lang", "label"), [("en", "Reference"), ("fr", "Référence")])
def test_reference_navbar_opens_the_first_available_index(
    tmp_path: Path,
    references: tuple[str, ...],
    order: list[str],
    target: str | None,
    lang: str,
    label: str,
) -> None:
    settings = f"site:\n  lang: {lang}\nref_section_order: [" + ", ".join(order) + "]\n"
    quarto_config = _assemble(tmp_path, settings, references=references)

    links = quarto_config["website"]["navbar"]["left"]
    if target is None:
        assert links == []
        return
    index = "reference/index.qmd" if target == "api" else f"reference/{target}/index.qmd"
    assert links == [{"text": label, "href": index}]
    assert (Layout.make(tmp_path).build_dir / index).is_file()
