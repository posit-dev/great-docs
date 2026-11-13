"""
Tests for GitHub and PyPI data retrieval over HTTP
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from great_docs._project.repository import Repository
from great_docs._project.remote import HttpRemote, OfflineRemote

REPO = Repository("github", "https://github.com", "owner", "repo")


@pytest.fixture(autouse=True)
def no_token(monkeypatch):
    """Send requests without credentials unless a test supplies them"""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)


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


def test_repository_stats():
    body = {"stargazers_count": 42, "forks_count": 7}
    with patch("requests.get", return_value=response(200, body)):
        stats = HttpRemote(report=print).repository_stats(REPO)

    assert stats == {"stars": 42, "forks": 7}


@pytest.mark.parametrize(
    "outcome",
    [requests.ConnectionError("offline"), response(404)],
    ids=["request error", "status 404"],
)
def test_repository_stats_unknown(outcome):
    with patch("requests.get", side_effect=[outcome]):
        stats = HttpRemote(report=print).repository_stats(REPO)

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
            remote.repository_stats(REPO)
        else:
            remote.repository_releases(REPO, 1)

    assert get.call_args.kwargs["headers"].get("Authorization") == authorization


def test_repository_releases_skip_drafts():
    entries = releases(3)
    entries[1]["draft"] = True
    entries[2]["prerelease"] = True
    reports: list[str] = []
    with patch("requests.get", return_value=response(200, entries)):
        result = HttpRemote(report=reports.append).repository_releases(REPO, 10)

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


def test_repository_releases_read_pages_until_a_short_one():
    pages = [response(200, releases(100)), response(200, releases(20))]
    with patch("requests.get", side_effect=pages) as get:
        result = HttpRemote(report=print).repository_releases(REPO, 150)

    assert len(result) == 120
    assert get.call_args.args[0].endswith("/repos/owner/repo/releases?per_page=100&page=2")


def test_repository_releases_stop_at_max():
    with patch("requests.get", return_value=response(200, releases(19))):
        result = HttpRemote(report=print).repository_releases(REPO, 5)

    assert len(result) == 5


def test_repository_releases_keep_pages_read_before_a_failure():
    reports: list[str] = []
    pages = [response(200, releases(100)), response(500)]
    with patch("requests.get", side_effect=pages):
        result = HttpRemote(report=reports.append).repository_releases(REPO, 150)

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
def test_repository_releases_report_failures(outcome, report):
    reports: list[str] = []
    with patch("requests.get", side_effect=[outcome]):
        result = HttpRemote(report=reports.append).repository_releases(REPO, 10)

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


@pytest.mark.parametrize(
    "outcome",
    [requests.ConnectionError("timeout"), response(404), malformed()],
    ids=["request error", "status 404", "malformed"],
)
def test_pypi_release_dates_omit_failed_requests(outcome):
    with patch("requests.get", side_effect=[outcome]):
        dates = HttpRemote(report=print).pypi_release_dates({"nonexistent-pkg"})

    assert dates == {}


def test_pypi_release_dates_raise_on_an_unexpected_response():
    with patch("requests.get", return_value=response(200, ["not", "a", "mapping"])):
        with pytest.raises(AttributeError):
            HttpRemote(report=print).pypi_release_dates({"numpy"})


def test_pypi_release_dates_of_no_packages():
    with patch("requests.get") as get:
        dates = HttpRemote(report=print).pypi_release_dates(set())

    assert dates == {}
    get.assert_not_called()


def test_offline_remote_makes_no_requests():
    remote = OfflineRemote()
    with patch("requests.get") as get:
        assert remote.repository_stats(REPO) == {}
        assert remote.repository_releases(REPO, 10) == []
        assert remote.pypi_release_dates({"numpy"}) == {}

    get.assert_not_called()


def test_gitlab_identity_never_reaches_github_api() -> None:
    repository = Repository("gitlab", "https://gitlab.com", "group/subgroup", "project")
    with patch("requests.get", return_value=response(404)) as get:
        remote = HttpRemote(report=print)
        assert remote.repository_stats(repository) == {}
        assert remote.repository_releases(repository, 10) == []
    assert get.call_count == 2
    assert all(call.args[0].startswith("https://gitlab.com/api/v4/") for call in get.call_args_list)


GITLAB = Repository("gitlab", "https://code.example.org/gitlab", "team/subgroup", "project")


def gitlab_releases(count: int, **fields: Any) -> list[dict[str, Any]]:
    """Create GitLab API releases with provider-specific fields"""
    return [
        {
            "tag_name": f"v{i}",
            "name": f"Version {i}",
            "description": "Fixed #12 and !34 by @ada.user",
            "released_at": "2026-01-01T00:00:00Z",
            "_links": {"self": GITLAB.release_url(f"v{i}")},
            **fields,
        }
        for i in range(count, 0, -1)
    ]


def test_gitlab_project_path_is_encoded_once_and_prefix_is_retained() -> None:
    with patch(
        "requests.get", return_value=response(200, {"star_count": 0, "forks_count": 7})
    ) as get:
        result = HttpRemote(report=print).repository_stats(GITLAB)
    assert result == {"stars": 0, "forks": 7}
    assert (
        get.call_args.args[0]
        == "https://code.example.org/gitlab/api/v4/projects/team%2Fsubgroup%2Fproject"
    )
    assert get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("provider", ["github", "gitlab"])
@pytest.mark.parametrize(
    "data", [None, [], "invalid", {"star_count": None, "forks_count": True}, {"star_count": -1}]
)
def test_invalid_project_counts_stay_unknown(provider, data) -> None:
    repo = REPO if provider == "github" else GITLAB
    with patch("requests.get", return_value=response(200, data)):
        assert HttpRemote(report=print).repository_stats(repo) == {}


@pytest.mark.parametrize("method", ["stats", "releases"])
@pytest.mark.parametrize(
    "private,job,header",
    [(" token \n", "job", {"PRIVATE-TOKEN": "token"}), ("", "job", None), ("", "", {})],
)
def test_gitlab_authentication_is_endpoint_specific(
    monkeypatch, method, private, job, header
) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", private)
    monkeypatch.setenv("CI_JOB_TOKEN", job)
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret")
    if header is None:
        header = {"JOB-TOKEN": "job"} if method == "releases" else {}
    with patch(
        "requests.get", return_value=response(200, [] if method == "releases" else {})
    ) as get:
        remote = HttpRemote(report=print)
        if method == "stats":
            remote.repository_stats(GITLAB)
        else:
            remote.repository_releases(GITLAB, 10)
    assert get.call_args.kwargs["headers"] == {"Accept": "application/json", **header}


def test_gitlab_credentials_are_never_sent_to_github(monkeypatch) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "gitlab-secret")
    monkeypatch.setenv("CI_JOB_TOKEN", "job-secret")
    with patch("requests.get", return_value=response(200, [])) as get:
        HttpRemote(report=print).repository_releases(REPO, 10)
    assert get.call_args.kwargs["headers"] == {"Accept": "application/vnd.github+json"}


def test_gitlab_json_redirect_is_not_followed_with_credentials(monkeypatch) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "private-secret")
    redirect = response(302)
    redirect.headers = {"Location": "https://foreign.example.org/collect"}
    reports: list[str] = []
    with patch("requests.get", return_value=redirect) as get:
        assert HttpRemote(report=reports.append).repository_stats(GITLAB) == {}
    assert get.call_count == 1
    assert get.call_args.kwargs["allow_redirects"] is False
    assert "redirected" in reports[0]
    assert "private-secret" not in " ".join(reports)


def test_gitlab_releases_normalise_nullable_fields_and_skip_upcoming() -> None:
    entries = gitlab_releases(1, name=None, description=None, prerelease=True)
    entries += gitlab_releases(1, upcoming_release=True)
    entries += gitlab_releases(1, released_at="2999-01-01T00:00:00Z")
    with patch("requests.get", return_value=response(200, entries)):
        result = HttpRemote(report=print).repository_releases(GITLAB, 10)
    assert result == [
        {
            "tag_name": "v1",
            "name": "",
            "body": "",
            "published_at": "2026-01-01T00:00:00Z",
            "html_url": GITLAB.release_url("v1"),
            "prerelease": False,
        }
    ]


def test_gitlab_releases_keep_published_pages_before_a_failure() -> None:
    reports: list[str] = []
    pages = [response(200, gitlab_releases(100)), response(429)]
    with patch("requests.get", side_effect=pages) as get:
        result = HttpRemote(report=reports.append).repository_releases(GITLAB, 150)
    assert len(result) == 100
    assert get.call_args.args[0].endswith("?per_page=100&page=2")
    assert "rate limit" in reports[0]


def test_gitlab_releases_read_through_future_only_pages_and_stop_at_maximum() -> None:
    pages = [
        response(200, gitlab_releases(2, released_at="2999-01-01T00:00:00+00:00")),
        response(200, gitlab_releases(2)),
    ]
    with patch("requests.get", side_effect=pages) as get:
        result = HttpRemote(report=print).repository_releases(GITLAB, 2)
    assert len(result) == 2
    assert get.call_count == 2


@pytest.mark.parametrize(
    "outcome",
    [
        response(401),
        response(403),
        response(404),
        response(429),
        response(500),
        requests.Timeout("timed out"),
        response(200, {}),
        response(200, [None, {"tag_name": 12}, {"tag_name": "v1", "released_at": "invalid"}]),
    ],
)
def test_gitlab_releases_report_unavailable_or_malformed_data(outcome) -> None:
    reports: list[str] = []
    with patch("requests.get", side_effect=[outcome]):
        assert HttpRemote(report=reports.append).repository_releases(GITLAB, 10) == []
    assert reports


@pytest.mark.parametrize("provider", ["github", "gitlab"])
@pytest.mark.parametrize("maximum", [0, -1])
def test_non_positive_release_maximum_makes_no_request(provider, maximum) -> None:
    with patch("requests.get") as get:
        assert (
            HttpRemote(report=print).repository_releases(
                REPO if provider == "github" else GITLAB, maximum
            )
            == []
        )
    get.assert_not_called()
