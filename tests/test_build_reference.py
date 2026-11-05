"""
Tests for reference page generation and source links
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from great_docs import GreatDocs
from great_docs._build import reference
from great_docs._build.log import BuildLog
from great_docs._build.steps import Outcome
from great_docs._utils import QUARTO_YML_HEADER
from tests.support import make_run, write_config


def _source_linked_project(root: Path, name: str, branch: str) -> GreatDocs:
    """
    Create a project whose API reference links to a branch of its GitHub repository

    Parameters
    ----------
    root
        The directory in which to create the project.
    name
        The package name, unique within the test session.
    branch
        The configured source-link branch.

    Returns
    -------
    :
        The project with its build directory's Quarto configuration written.
    """
    root.mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\n\n'
        f'[project.urls]\nRepository = "https://github.com/owner/{name}"\n',
        encoding="utf-8",
    )
    (root / "great-docs.yml").write_text(f"source:\n  branch: {branch}\n", encoding="utf-8")
    (root / name).mkdir()
    (root / name / "__init__.py").write_text(
        'def greet():\n    """Say hello."""\n    return "hi"\n', encoding="utf-8"
    )
    docs = GreatDocs(project_path=str(root))
    docs.build_dir.mkdir(parents=True)
    block = {
        "package": name,
        "dynamic": False,
        "dir": "reference",
        "sections": [{"title": "Functions", "contents": [{"name": "greet"}]}],
    }
    (docs.build_dir / "_quarto.yml").write_text(
        yaml.safe_dump({"api-reference": block}), encoding="utf-8"
    )
    return docs


def _write_api_reference(docs: GreatDocs) -> Outcome:
    """
    Run the API reference step in the build directory, as a build does

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The step's outcome.
    """
    outcome, _ = reference.api(
        make_run(docs), docs._config, docs.layout, BuildLog(stream=io.StringIO())
    )
    return outcome


def test_api_config_reuses_the_exports_discovered_during_preparation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    Reuse the API reference configuration discovered during build preparation
    """
    write_config(tmp_path, "module: mypkg\n")
    docs = GreatDocs(project_path=str(tmp_path))
    run = make_run(docs)

    with patch.object(run.exports, "sections") as sections:
        outcome = reference.api_config(run, refresh=True)

    sections.assert_not_called()
    assert outcome == "API reference refreshed"
    assert "API reference already configured in this build" in capsys.readouterr().out


def test_api_config_without_refresh_uses_the_existing_configuration(tmp_path: Path):
    """
    Report the existing API reference configuration when the build skips refreshing
    """
    write_config(tmp_path, "module: mypkg\n")
    docs = GreatDocs(project_path=str(tmp_path))

    assert reference.api_config(make_run(docs), refresh=False) == "Using existing config"


def test_api_links_each_project_in_a_process_to_its_own_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Link each project's reference pages to its own repository and branch
    """
    pages: list[str] = []
    for name, branch in [("srclinks_a", "branch-a"), ("srclinks_b", "branch-b")]:
        docs = _source_linked_project(tmp_path / name, name, branch)
        monkeypatch.syspath_prepend(str(docs.layout.package_root))
        monkeypatch.chdir(docs.build_dir)
        _ = _write_api_reference(docs)
        pages.append((docs.build_dir / "reference" / "greet.qmd").read_text(encoding="utf-8"))

    assert "github.com/owner/srclinks_a/blob/branch-a/srclinks_a/__init__.py" in pages[0]
    assert "github.com/owner/srclinks_b/blob/branch-b/srclinks_b/__init__.py" in pages[1]


def test_api_imports_the_package_from_the_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Import the documented package from the project root, as Quarto does
    """
    docs = _source_linked_project(tmp_path / "srclinks_path", "srclinks_path", "main")
    root = str(docs.layout.package_root)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.chdir(docs.build_dir)

    assert _write_api_reference(docs) == "API reference generated"

    assert root in sys.path


def test_cli_reports_a_command_tree_without_pages(tmp_path: Path):
    """
    Report an empty CLI result without changing the Quarto configuration
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
    write_config(tmp_path, "cli:\n  enabled: true\n")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir()
    (docs.build_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER, encoding="utf-8")

    with (
        patch("great_docs._cliref.click.discover", return_value={"name": "mycli"}),
        patch("great_docs._cliref.render.write_pages", return_value=[]),
    ):
        outcome = reference.cli(make_run(docs), docs._config, docs.layout)

    assert outcome == "No CLI pages generated"
    assert (docs.build_dir / "_quarto.yml").read_text(encoding="utf-8") == QUARTO_YML_HEADER
