"""
Tests for the build steps that run after the site is rendered
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs._build import finish
from great_docs._build.log import BuildLog
from great_docs._build.pipeline import Run
from great_docs._project.layout import Layout
from tests.support import write_config, write_pyproject


def _save_snapshot(root: Path, name: str, settings: str = "") -> MagicMock:
    """
    Run the snapshot step for a project and return its build log

    Parameters
    ----------
    root
        The project directory.
    name
        The distribution name to declare in `pyproject.toml`.
    settings
        The project's `great-docs.yml`.

    Returns
    -------
    :
        The build log the step wrote to.
    """
    config = write_config(write_pyproject(root, name), settings)
    layout = Layout.make(root)
    log = MagicMock(spec=BuildLog)
    _ = finish.save_api_snapshot(Run.make(config, layout, watch=False), config, layout, log)
    return log


@patch("great_docs._api_evolution.snapshot.snapshot_from_griffe")
def test_snapshot_loads_the_importable_module(mock_snapshot: MagicMock, tmp_path: Path):
    """
    The snapshot loads the configured module when it differs from the distribution name
    """
    _ = _save_snapshot(tmp_path, "my-dist", "module: actual_module\n")

    assert mock_snapshot.call_args[0][0] == "actual_module"


@pytest.mark.parametrize(
    ("outcomes", "version"),
    [
        ([subprocess.TimeoutExpired(["git"], 5)], "dev"),
        (
            [
                BlockingIOError(11, "Resource temporarily unavailable"),
                subprocess.CompletedProcess(["git"], 0, stdout="v2.0.0\n", stderr=""),
            ],
            "v2.0.0",
        ),
    ],
)
@patch("great_docs._api_evolution.snapshot.snapshot_from_griffe")
def test_snapshot_is_named_after_the_exact_tag(
    mock_snapshot: MagicMock, tmp_path: Path, outcomes: list[object], version: str
):
    """
    A failed `git` start is retried once; a 5-second timeout names the snapshot `dev`
    """
    with patch("subprocess.run", side_effect=outcomes), patch("time.sleep"):
        _ = _save_snapshot(tmp_path, "mypkg")

    assert mock_snapshot.call_args.kwargs["version"] == version


@patch(
    "great_docs._api_evolution.snapshot.snapshot_from_griffe", side_effect=ImportError("no mypkg")
)
def test_snapshot_failure_warns(_mock_snapshot: MagicMock, tmp_path: Path):
    """
    A package that cannot be loaded leaves no snapshot and a warning in the build log
    """
    log = _save_snapshot(tmp_path, "mypkg")

    log.warn.assert_called_once_with("Snapshot auto-save failed: no mypkg")
    assert not (tmp_path / ".great-docs" / "snapshots").exists()
