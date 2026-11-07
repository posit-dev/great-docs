"""
Build log package details and configuration writes during preparation
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from unittest.mock import DEFAULT, patch

import pytest

from great_docs import GreatDocs
from great_docs._build import pipeline
from great_docs._build.log import BuildLog
from great_docs._build.pipeline import Run
from great_docs._build.steps import BuildError
from great_docs._website import quarto_yml
from tests.support import make_run, stubbed_build, write_config, write_pyproject


def _header_log(root: Path) -> BuildLog:
    """
    Create a header log for an uninstalled package in `root`

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
        The build log, with its header's package details.
    """
    write_pyproject(root, "header-demo-pkg")
    package = root / "header_demo_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    write_config(root)
    docs = GreatDocs(str(root))
    return pipeline._make_log(make_run(docs), docs._config, docs.layout)


def test_header_shows_no_version_for_an_uninstalled_package(tmp_path: Path):
    log = _header_log(tmp_path)

    assert log.package_name == "header-demo-pkg"
    assert log.package_version == ""
    assert log.package_location == str(tmp_path / "header_demo_pkg")


def test_header_shows_the_package_directory_without_git(tmp_path: Path):
    with patch("great_docs._build.pipeline.subprocess.run", side_effect=FileNotFoundError):
        log = _header_log(tmp_path)

    assert log.package_location == str(tmp_path / "header_demo_pkg")


def _versioned_docs(root: Path) -> GreatDocs:
    """
    Create a versioned project with an initial build configuration

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
        The project, configured with versions `0.2` and `0.1`.
    """
    write_config(root, {"versions": ["0.2", "0.1"]})
    docs = GreatDocs(str(root))
    docs.layout.build_dir.mkdir(parents=True)
    quarto_yml.write_initial(docs.layout.build_dir)
    return docs


def _set_title(run: Run, *args: object, **kwargs: object) -> object:
    """
    Set the prepared site's title without writing configuration

    Parameters
    ----------
    run
        The current build.
    *args
        Further arguments of the step, ignored here.
    **kwargs
        Keyword arguments of the step, ignored here.

    Returns
    -------
    :
        `DEFAULT`, so the stub returns its configured value.
    """
    run.quarto_config["website"] = {"title": "Prepared"}
    return DEFAULT


def test_versioned_build_renders_each_version_from_the_configuration_in_memory(tmp_path: Path):
    docs = _versioned_docs(tmp_path)
    initial = quarto_yml.read(docs.layout.build_dir)
    seen: dict[str, Any] = {}

    def versioned_build(*args: object, **kwargs: Any) -> dict[str, Any]:
        seen["written"] = quarto_yml.read(docs.layout.build_dir)
        seen["passed"] = kwargs["quarto_config"]
        return {"success": False, "errors": [], "versions_built": []}

    with (
        stubbed_build() as stubs,
        patch("great_docs._versions.build.run_versioned_build", side_effect=versioned_build),
        pytest.raises(BuildError),
    ):
        stubs.steps["content.assets"].side_effect = _set_title
        docs.build(refresh=False)

    # Preparation passes the finished configuration in memory and leaves the file unchanged.
    assert seen["written"] == initial
    assert seen["passed"]["website"] == {"title": "Prepared"}


def test_freeze_preparation_of_a_versioned_project_writes_the_configuration(tmp_path: Path):
    docs = _versioned_docs(tmp_path)
    log = BuildLog(stream=io.StringIO())

    with stubbed_build() as stubs:
        stubs.steps["content.assets"].side_effect = _set_title
        pipeline.prepare_for_freeze(docs._config, docs.layout, log, remote=docs._remote)

    assert quarto_yml.read(docs.layout.build_dir)["website"] == {"title": "Prepared"}
