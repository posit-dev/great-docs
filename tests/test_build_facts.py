"""
Tests for repository data read once per documentation build
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from great_docs._apiref._settings import SourceLinks
from great_docs._build.facts import Facts, source_links, source_ref
from great_docs._github import GithubRepo
from great_docs._website.navigation.release import Release
from tests.support import StubRemote, mock_config

REPO = GithubRepo(owner="owner", name="repo")
RELEASE = {"tag_name": "v1.2.0", "published_at": "2025-06-15T10:00:00Z"}


def test_without_a_repository_nothing_is_fetched():
    remote = StubRemote(stats={"stars": 5, "forks": 1}, releases=[RELEASE])

    facts = Facts.make(mock_config(github_style="widget"), None, remote)

    assert facts == Facts()
    assert remote.calls == []


def test_the_widget_style_fetches_counts_and_the_latest_release():
    remote = StubRemote(stats={"stars": 5, "forks": 1}, releases=[RELEASE])

    facts = Facts.make(mock_config(github_style="widget"), REPO, remote)

    assert facts == Facts(
        github_stats={"stars": 5, "forks": 1},
        latest_release=Release(version="1.2.0", date="2025-06-15"),
    )
    assert remote.calls == ["github_stats", "github_releases"]


def test_the_icon_style_fetches_only_the_latest_release():
    remote = StubRemote(stats={"stars": 5, "forks": 1})

    facts = Facts.make(mock_config(github_style="icon"), REPO, remote)

    assert facts == Facts()
    assert remote.calls == ["github_releases"]


def _exited(returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    """
    Create a result for a completed `git` command

    Parameters
    ----------
    returncode
        The exit status.
    stdout
        The standard output.

    Returns
    -------
    :
        The completed process.
    """
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr="")


def _unexpected(message: str) -> None:
    """
    Fail a test that expects no warning

    Parameters
    ----------
    message
        The warning text.

    Raises
    ------
    AssertionError
        Always, with the warning text in the error message.
    """
    raise AssertionError(f"unexpected warning: {message}")


def test_a_configured_branch_is_the_ref_without_running_git(tmp_path: Path):
    with patch("subprocess.run") as run:
        ref = source_ref(mock_config(source_branch="develop"), tmp_path, warn=_unexpected)

    assert ref == "develop"
    run.assert_not_called()


def test_the_exact_tag_is_the_ref(tmp_path: Path):
    with patch("subprocess.run", return_value=_exited(0, "v1.2.3\n")):
        assert source_ref(mock_config(), tmp_path, warn=_unexpected) == "v1.2.3"


def test_the_branch_is_the_ref_without_an_exact_tag(tmp_path: Path):
    with patch("subprocess.run", side_effect=[_exited(128), _exited(0, "feature\n")]):
        assert source_ref(mock_config(), tmp_path, warn=_unexpected) == "feature"


def test_a_detached_head_falls_back_to_main(tmp_path: Path):
    with patch("subprocess.run", side_effect=[_exited(128), _exited(0, "HEAD\n")]):
        assert source_ref(mock_config(), tmp_path, warn=_unexpected) == "main"


def test_outside_a_repository_the_ref_is_main(tmp_path: Path):
    assert source_ref(mock_config(), tmp_path, warn=_unexpected) == "main"


def test_git_that_fails_to_start_once_is_retried(tmp_path: Path):
    side_effect = [BlockingIOError(11, "Resource temporarily unavailable"), _exited(0, "2.0.0\n")]
    with patch("subprocess.run", side_effect=side_effect), patch("time.sleep"):
        assert source_ref(mock_config(), tmp_path, warn=_unexpected) == "2.0.0"


def test_git_that_never_starts_warns_before_falling_back(tmp_path: Path):
    warnings: list[str] = []
    error = BlockingIOError(11, "Resource temporarily unavailable")
    with patch("subprocess.run", side_effect=error), patch("time.sleep"):
        ref = source_ref(mock_config(), tmp_path, warn=warnings.append)

    assert ref == "main"
    assert len(warnings) == 1
    assert "Resource temporarily unavailable" in warnings[0]


def test_git_that_runs_too_long_warns_before_falling_back(tmp_path: Path):
    warnings: list[str] = []
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 5)):
        ref = source_ref(mock_config(), tmp_path, warn=warnings.append)

    assert ref == "main"
    assert len(warnings) == 1
    assert "timed out after 5 seconds" in warnings[0]


def test_source_links_link_to_the_repository(tmp_path: Path):
    config = mock_config(source_enabled=True, source_branch="dev", source_path="pkg/src")

    links = source_links(config, tmp_path, REPO.url, warn=_unexpected)

    assert links == SourceLinks(repo_url=REPO.url, ref="dev", package_root=tmp_path, path="pkg/src")


@pytest.mark.parametrize(("enabled", "repo_url"), [(False, REPO.url), (True, None)])
def test_source_links_without_a_repository_to_link_run_no_git(
    tmp_path: Path, enabled: bool, repo_url: str | None
):
    with patch("subprocess.run") as run:
        links = source_links(
            mock_config(source_enabled=enabled), tmp_path, repo_url, warn=_unexpected
        )

    assert links == SourceLinks()
    run.assert_not_called()
