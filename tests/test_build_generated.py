"""
Tests for generated site files and CLI help
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from great_docs import GreatDocs
from great_docs._build import generated
from tests.support import make_run

# Use the standard library's `json` so planning `llms.txt` needs no test package.
LLMS_TXT_QUARTO_YML = "api-reference:\n  package: json\n  sections:\n    - contents: [dumps]\n"


def _cli_project(root: Path, cli_source: str | None = None) -> GreatDocs:
    """
    Create a project whose distribution and module names differ, with its CLI enabled

    Parameters
    ----------
    root
        The project directory.
    cli_source
        The source of the module's `cli.py`, or `None` to leave the module unwritten.

    Returns
    -------
    :
        The project, with a build directory whose API reference plans the llms files.
    """
    (root / "pyproject.toml").write_text('[project]\nname = "my-dist"\n', encoding="utf-8")
    (root / "great-docs.yml").write_text(
        "module: actual_module\ncli:\n  enabled: true\n", encoding="utf-8"
    )
    if cli_source is not None:
        package = root / "actual_module"
        package.mkdir()
        (package / "__init__.py").write_text('"""actual_module."""\n', encoding="utf-8")
        (package / "cli.py").write_text(cli_source, encoding="utf-8")
    docs = GreatDocs(project_path=str(root))
    docs.build_dir.mkdir()
    (docs.build_dir / "_quarto.yml").write_text(LLMS_TXT_QUARTO_YML, encoding="utf-8")
    return docs


@pytest.fixture
def importable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Make `actual_module` importable from the test's directory and forget it afterwards

    Parameters
    ----------
    tmp_path
        The test's directory.
    monkeypatch
        Restores `sys.path` after the test.

    Yields
    ------
    :
        `tmp_path`.
    """
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for name in ("actual_module", "actual_module.cli"):
        sys.modules.pop(name, None)


def test_llms_cli_help_is_discovered_in_the_importable_module(tmp_path: Path):
    """
    Discover the Click CLI by the importable module's name, not the distribution's name
    """
    docs = _cli_project(tmp_path)

    with patch("great_docs._cliref.click.discover", return_value=None) as discover:
        generated.llms_txt(make_run(docs), docs._config, docs.layout)

    discover.assert_called_once_with(
        "actual_module",
        docs.layout.package_root,
        cli_module=None,
        cli_name=None,
        display_name="my-dist",
        report=print,
    )


def test_llms_cli_heading_uses_the_distribution_name(importable: Path):
    """
    Use the distribution's name in the CLI heading when the project declares no scripts
    """
    docs = _cli_project(
        importable, 'import click\n\n\n@click.group()\ndef main():\n    """Main CLI."""\n'
    )

    generated.llms_txt(make_run(docs), docs._config, docs.layout)

    assert "## CLI: my-dist" in (docs.build_dir / "llms-full.txt").read_text(encoding="utf-8")


def test_llms_full_is_written_without_cli_when_the_cli_module_fails_to_import(importable: Path):
    """
    Write `llms-full.txt` without the CLI when a candidate CLI module fails to import
    """
    docs = _cli_project(importable, "import brokencli_missing_dependency\n")

    generated.llms_txt(make_run(docs), docs._config, docs.layout)

    assert "## CLI" not in (docs.build_dir / "llms-full.txt").read_text(encoding="utf-8")
