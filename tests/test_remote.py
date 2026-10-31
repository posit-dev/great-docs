"""
Tests for GitHub and PyPI data retrieval over HTTP
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from great_docs._github import GithubRepo
from great_docs._remote import HttpRemote, OfflineRemote

REPO = GithubRepo("owner", "repo")


@pytest.fixture(autouse=True)
def no_token(monkeypatch):
    """Send GitHub requests without a token unless a test sets one"""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)


def response(status: int, body: object = None) -> MagicMock:
    """
    Create a mock HTTP response

    Parameters
    ----------
    status
        The HTTP status code.
    body
        The decoded JSON body.

    Returns
    -------
    :
        The response.
    """
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    return resp


def releases(count: int, **fields: Any) -> list[dict[str, Any]]:
    """
    Create GitHub API release entries, newest first

    Parameters
    ----------
    count
        The number of entries.
    **fields
        Values that replace the defaults in every entry.

    Returns
    -------
    :
        The entries, tagged `v{count}` down to `v1`.
    """
    return [
        {
            "tag_name": f"v{i}",
            "name": f"Release {i}",
            "body": "",
            "published_at": "2026-01-01T00:00:00Z",
            "html_url": f"https://github.com/owner/repo/releases/tag/v{i}",
            "prerelease": False,
            "draft": False,
            **fields,
        }
        for i in range(count, 0, -1)
    ]


def test_github_stats():
    body = {"stargazers_count": 42, "forks_count": 7}
    with patch("requests.get", return_value=response(200, body)):
        stats = HttpRemote(report=print).github_stats(REPO)

    assert stats == {"stars": 42, "forks": 7}


@pytest.mark.parametrize(
    "outcome",
    [requests.ConnectionError("offline"), response(404)],
    ids=["request error", "status 404"],
)
def test_github_stats_unknown(outcome):
    with patch("requests.get", side_effect=[outcome]):
        stats = HttpRemote(report=print).github_stats(REPO)

    assert stats == {}


@pytest.mark.parametrize("method", ["stats", "releases"])
@pytest.mark.parametrize(
    ("token", "authorization"),
    [
        ("ghp_test123", "Bearer ghp_test123"),
        (" ghp_test123\n", "Bearer ghp_test123"),
        ("   ", None),
    ],
    ids=["token", "padded token", "blank token"],
)
def test_github_requests_send_token(monkeypatch, method, token, authorization):
    monkeypatch.setenv("GITHUB_TOKEN", token)
    remote = HttpRemote(report=print)
    with patch("requests.get", return_value=response(200, {})) as get:
        if method == "stats":
            remote.github_stats(REPO)
        else:
            remote.github_releases(REPO, 1)

    assert get.call_args.kwargs["headers"].get("Authorization") == authorization


def test_github_releases_skip_drafts():
    entries = releases(3)
    entries[1]["draft"] = True
    entries[2]["prerelease"] = True
    reports: list[str] = []
    with patch("requests.get", return_value=response(200, entries)):
        result = HttpRemote(report=reports.append).github_releases(REPO, 10)

    assert [r["tag_name"] for r in result] == ["v3", "v1"]
    assert result[1] == {
        "tag_name": "v1",
        "name": "Release 1",
        "body": "",
        "published_at": "2026-01-01T00:00:00Z",
        "html_url": "https://github.com/owner/repo/releases/tag/v1",
        "prerelease": True,
    }
    assert reports == []


def test_github_releases_read_pages_until_a_short_one():
    pages = [response(200, releases(100)), response(200, releases(20))]
    with patch("requests.get", side_effect=pages) as get:
        result = HttpRemote(report=print).github_releases(REPO, 150)

    assert len(result) == 120
    assert get.call_args.args[0].endswith("/repos/owner/repo/releases?per_page=100&page=2")


def test_github_releases_stop_at_max():
    with patch("requests.get", return_value=response(200, releases(19))):
        result = HttpRemote(report=print).github_releases(REPO, 5)

    assert len(result) == 5


def test_github_releases_keep_pages_read_before_a_failure():
    reports: list[str] = []
    pages = [response(200, releases(100)), response(500)]
    with patch("requests.get", side_effect=pages):
        result = HttpRemote(report=reports.append).github_releases(REPO, 150)

    assert len(result) == 100
    assert reports == ["GitHub API returned status 500"]


def malformed() -> MagicMock:
    """
    Create a mock response whose body is not JSON

    Returns
    -------
    :
        The response.
    """
    resp = response(200)
    resp.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
    return resp


@pytest.mark.parametrize(
    ("outcome", "report"),
    [
        (requests.ConnectionError("offline"), "Failed to fetch GitHub releases: offline"),
        (response(403), "GitHub API rate limit reached; changelog may be incomplete"),
        (response(404), "GitHub repository owner/repo not found"),
        (response(500), "GitHub API returned status 500"),
        (malformed(), "GitHub API returned a malformed release list"),
    ],
    ids=["request error", "rate limit", "not found", "other status", "malformed"],
)
def test_github_releases_report_failures(outcome, report):
    reports: list[str] = []
    with patch("requests.get", side_effect=[outcome]):
        result = HttpRemote(report=reports.append).github_releases(REPO, 10)

    assert result == []
    assert reports == [report]


def test_pypi_release_dates():
    body = {
        "info": {"version": "1.26.0"},
        "releases": {"1.26.0": [{"upload_time_iso_8601": "2026-06-15T12:00:00Z"}]},
    }
    with patch("requests.get", return_value=response(200, body)):
        dates = HttpRemote(report=print).pypi_release_dates({"numpy"})

    assert dates == {"numpy": "2026-06-15"}


def test_pypi_release_dates_omit_failed_requests():
    with patch("requests.get", side_effect=Exception("timeout")):
        dates = HttpRemote(report=print).pypi_release_dates({"nonexistent-pkg"})

    assert dates == {}


def test_pypi_release_dates_of_no_packages():
    with patch("requests.get") as get:
        dates = HttpRemote(report=print).pypi_release_dates(set())

    assert dates == {}
    get.assert_not_called()


def test_offline_remote_makes_no_requests():
    remote = OfflineRemote()
    with patch("requests.get") as get:
        assert remote.github_stats(REPO) == {}
        assert remote.github_releases(REPO, 10) == []
        assert remote.pypi_release_dates({"numpy"}) == {}

    get.assert_not_called()
