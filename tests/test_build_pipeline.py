"""
Package details in the build log header
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from great_docs import GreatDocs
from great_docs._build import pipeline
from great_docs._build.log import BuildLog
from tests.support import make_run, write_config, write_pyproject


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
