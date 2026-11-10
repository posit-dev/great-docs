"""
Tests for ordering dependencies between site-wide Quarto settings

Each test checks a dependency between settings that tests of either setting
alone cannot cover.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from great_docs._build.facts import Facts
from great_docs._project.layout import Layout
from great_docs._website import assembly
from great_docs._website.identity import Identity
from tests.support import write_config

BASE_URL = "https://example.com/pkg/"


def _assemble(root: Path, settings: str) -> dict[str, Any]:
    """
    Assemble the Quarto configuration of a project named `pkg`

    Parameters
    ----------
    root
        The project directory.
    settings
        The contents of `great-docs.yml`.

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
    assembly.assemble(
        quarto_config,
        config,
        layout,
        repo=None,
        facts=Facts(),
        identity=Identity(name="Pkg", url=BASE_URL, base_url=BASE_URL),
        package_name="pkg",
        metadata={},
        has_api_reference=True,
        contributions=(),
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
