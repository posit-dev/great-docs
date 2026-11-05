"""
Tests for the build steps that render the site with Quarto
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs._build import quarto, render
from great_docs._build.log import BuildLog
from great_docs._build.steps import StepError
from great_docs._layout import Layout
from tests.support import mock_config, write_config

TRANSIENT = quarto.RenderResult(1, "ENOENT: No such file or directory, rename", [])
FAILED = quarto.RenderResult(1, "Error: bad YAML", [])
RENDERED = quarto.RenderResult(0, "", [{"page": "index.qmd", "seconds": 1.0}])


@pytest.fixture
def quarto_render() -> Generator[MagicMock]:
    """
    Replace the Quarto render with a stub and Quarto's environment with an empty one

    Yields
    ------
    :
        The render stub; set its `side_effect` to the results of successive renders.
    """
    with (
        patch("great_docs._build.quarto.environment", return_value={}),
        patch("great_docs._build.quarto.render") as stub,
    ):
        yield stub


def test_site_retries_a_transient_failure(tmp_path: Path, quarto_render: MagicMock):
    _ = write_config(tmp_path)
    quarto_render.side_effect = [TRANSIENT, RENDERED]
    log = MagicMock(spec=BuildLog)

    result = render.site(mock_config(), Layout.make(tmp_path), {}, log, 1, {}, None)

    assert result == (RENDERED, None)
    assert quarto_render.call_count == 2
    log.warn.assert_called_once()


@pytest.mark.parametrize(("results", "renders"), [([FAILED], 1), ([TRANSIENT, TRANSIENT], 2)])
def test_site_stops_after_a_lasting_failure(
    tmp_path: Path, quarto_render: MagicMock, results: list[quarto.RenderResult], renders: int
):
    """
    Any other failure, or a second transient one, stops the build
    """
    _ = write_config(tmp_path)
    quarto_render.side_effect = results
    log = MagicMock(spec=BuildLog)

    with pytest.raises(StepError, match="Quarto render failed"):
        _ = render.site(mock_config(), Layout.make(tmp_path), {}, log, 1, {}, None)

    assert quarto_render.call_count == renders
