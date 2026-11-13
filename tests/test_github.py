"""
Tests for GitHub repository URL parsing and environment tokens
"""

from __future__ import annotations

import pytest

from great_docs._project.github import token_from_env
from great_docs._project.repository import Repository


@pytest.mark.parametrize(
    ("provider", "base", "route", "range_anchor"),
    [
        ("github", "https://github.com", "blob", "#L10-L20"),
        ("gitlab", "https://gitlab.com", "-/blob", "#L10-20"),
        ("gitlab", "https://code.example.org/gitlab", "-/blob", "#L10-20"),
    ],
)
def test_file_urls_escape_refs_and_paths(
    provider: str, base: str, route: str, range_anchor: str
) -> None:
    repository = Repository.parse(
        f"{base}/team/subteam/pkg" if provider == "gitlab" else f"{base}/team/pkg",
        provider=provider,
        base_url=base,
    )
    assert repository is not None
    prefix = f"{repository.url}/{route}/feature%2Fdocs%20v2/src/caf%C3%A9%20%23.py"

    assert repository.file_url("src/café #.py", "feature/docs v2") == prefix
    assert repository.file_url("src/café #.py", "feature/docs v2", 10) == prefix + "#L10"
    assert repository.file_url("src/café #.py", "feature/docs v2", 10, 10) == prefix + "#L10"
    assert repository.file_url("src/café #.py", "feature/docs v2", 10, 20) == prefix + range_anchor


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/posit-dev/great-docs",
            Repository("github", "https://github.com", "posit-dev", "great-docs"),
        ),
        (
            "https://github.com/posit-dev/great-docs.git",
            Repository("github", "https://github.com", "posit-dev", "great-docs"),
        ),
        (
            "git@github.com:posit-dev/great-docs.git",
            Repository("github", "https://github.com", "posit-dev", "great-docs"),
        ),
        ("https://github.com/o/r/", Repository("github", "https://github.com", "o", "r")),
        (
            "https://github.com/o/r/tree/main?tab=readme#top",
            Repository("github", "https://github.com", "o", "r"),
        ),
        ("https://gitlab.com/a/b", Repository("gitlab", "https://gitlab.com", "a", "b")),
        ("https://github.com/", None),
        ("http://github.com", None),
        ("https://github.com/owner/.git", None),
        ("", None),
        (None, None),
    ],
)
def test_parse(url, expected):
    assert Repository.parse(url) == expected


def test_url():
    assert (
        Repository("github", "https://github.com", "posit-dev", "great-docs").url
        == "https://github.com/posit-dev/great-docs"
    )


@pytest.mark.parametrize(
    ("github_token", "gh_token", "expected"),
    [
        ("ghp_a", "ghp_b", "ghp_a"),
        (None, "ghp_b", "ghp_b"),
        ("  ghp_a\n", None, "ghp_a"),
        ("   ", None, None),
        (None, None, None),
    ],
)
def test_token_from_env(monkeypatch, github_token, gh_token, expected):
    for name, value in [("GITHUB_TOKEN", github_token), ("GH_TOKEN", gh_token)]:
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    assert token_from_env() == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/group/subgroup/project",
        "https://gitlab.com/group/subgroup/project.git/",
        "git@gitlab.com:group/subgroup/project.git",
        "ssh://git@gitlab.com/group/subgroup/project.git",
        "https://gitlab.com/group/subgroup/project/-/blob/main/file.py?plain=1#L10",
    ],
)
def test_parse_nested_gitlab_repository(url: str) -> None:
    repository = Repository.parse(url)
    assert repository == Repository("gitlab", "https://gitlab.com", "group/subgroup", "project")
    assert repository.path == "group/subgroup/project"
    assert repository.url == "https://gitlab.com/group/subgroup/project"


@pytest.mark.parametrize(
    "url",
    [
        "ssh://git@github.com/o/r.git",
        "http://github.com/o/r",
        "https://github.com/o/r?tab=readme#readme",
    ],
)
def test_parse_additional_github_forms(url: str) -> None:
    repository = Repository.parse(url)
    assert repository is not None
    assert (repository.provider, repository.namespace, repository.name) == ("github", "o", "r")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com.evil.example/o/r",
        "https://evil.example/github.com/o/r",
        "https://github.com@evil.example/o/r",
        "https://user@github.com/o/r",
        "https://gitlab.com.evil.example/group/project",
        "https://gitlab.com/group",
        "https://gitlab.com/group/.git",
        "https://gitlab.com/group//project",
        "https://gitlab.com/group/../project",
        "https://gitlab.com/group/%2e%2e/project",
        "https://gitlab.com/group%2fsubgroup/project",
        "https://gitlab.com/group/project name",
        "https://gitlab.com:bad/group/project",
        "ftp://github.com/o/r",
        "file:///github.com/o/r",
        "owner/repo",
    ],
)
def test_reject_malformed_or_unrecognised_repository_urls(url: str) -> None:
    assert Repository.parse(url) is None


def test_custom_gitlab_requires_explicit_provider() -> None:
    url = "https://code.example.org:8443/group/subgroup/project"
    assert Repository.parse(url) is None
    assert Repository.parse(url, provider="gitlab") == Repository(
        "gitlab", "https://code.example.org:8443", "group/subgroup", "project"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://code.example.org:8443/gitlab/group/subgroup/project/-/tree/main",
        "ssh://git@code.example.org:2222/group/subgroup/project.git",
        "git@code.example.org:group/subgroup/project.git",
    ],
)
def test_explicit_web_base_controls_prefix_and_port(url: str) -> None:
    assert Repository.parse(
        url, provider="gitlab", base_url="https://code.example.org:8443/gitlab/"
    ) == Repository("gitlab", "https://code.example.org:8443/gitlab", "group/subgroup", "project")


@pytest.mark.parametrize(
    ("url", "provider", "base_url"),
    [
        ("https://github.com/o/r", "gitlab", None),
        ("https://gitlab.com/g/p", "github", None),
        ("https://example.org/g/p", "github", None),
        (None, "other", None),
        (None, None, "https://example.org/gitlab"),
        (None, "gitlab", "https://github.com"),
        (None, "gitlab", "ftp://example.org"),
        (None, "gitlab", "https://user@example.org"),
        (None, "gitlab", "https://example.org?query=1"),
        (None, "gitlab", "https://example.org/../gitlab"),
        ("https://other.example/g/p", "gitlab", "https://example.org"),
        ("https://example.org/g/p", "gitlab", "https://example.org/gitlab"),
        ("https://example.org/gitlab-other/g/p", "gitlab", "https://example.org/gitlab"),
        ("https://example.org:8443/g/p", "gitlab", "https://example.org"),
    ],
)
def test_explicit_settings_reject_contradictions(
    url: str | None, provider: str | None, base_url: str | None
) -> None:
    with pytest.raises(ValueError):
        Repository.parse(url, provider=provider, base_url=base_url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/o/r/tree/feature%2Fdocs/path%20name",
            Repository("github", "https://github.com", "o", "r"),
        ),
        (
            "https://gitlab.com/g/p/-/blob/feature%2Fdocs/a%20b.py",
            Repository("gitlab", "https://gitlab.com", "g", "p"),
        ),
    ],
)
def test_page_suffixes_do_not_constrain_repository_identity(url: str, expected: Repository) -> None:
    assert Repository.parse(url) == expected


@pytest.mark.parametrize("name", ["p%23suffix", "p%3Fsuffix", "caf%C3%A9"])
def test_identity_web_url_quotes_repository_components(name: str) -> None:
    repository = Repository.parse(f"https://gitlab.com/g/{name}")
    assert repository is not None
    assert repository.url == f"https://gitlab.com/g/{name}"


@pytest.mark.parametrize(
    ("url", "base_url"),
    [
        ("https://[2001:db8::1]:8443/team/pkg", "https://[2001:db8::1]:8443"),
        ("ssh://git@[2001:db8::1]:2222/team/pkg.git", "https://[2001:db8::1]:2222"),
        ("ssh://git@[2001:db8::1]:22/team/pkg.git", "https://[2001:db8::1]"),
        ("https://code.example.org:22/team/pkg", "https://code.example.org:22"),
    ],
)
def test_instance_origins_preserve_address_and_web_ports(url: str, base_url: str) -> None:
    repository = Repository.parse(url, provider="gitlab")
    assert repository == Repository("gitlab", base_url, "team", "pkg")
    assert repository.url == f"{base_url}/team/pkg"


def test_explicit_ipv6_web_base_controls_ssh_origin() -> None:
    repository = Repository.parse(
        "ssh://git@[2001:db8::1]:2222/team/pkg.git",
        provider="gitlab",
        base_url="https://[2001:db8::1]:8443/gitlab",
    )
    assert repository is not None
    assert repository.url == "https://[2001:db8::1]:8443/gitlab/team/pkg"


@pytest.mark.parametrize("scheme", ["scp", "ssh"])
@pytest.mark.parametrize("namespace", ["team", "gitlab/team"])
def test_ssh_project_paths_are_independent_of_http_prefix(scheme: str, namespace: str) -> None:
    url = (
        f"git@code.example.org:{namespace}/project.git"
        if scheme == "scp"
        else f"ssh://git@code.example.org:2222/{namespace}/project.git"
    )
    repository = Repository.parse(
        url, provider="gitlab", base_url="https://code.example.org/gitlab"
    )
    assert repository == Repository(
        "gitlab", "https://code.example.org/gitlab", namespace, "project"
    )
    assert repository.url == f"https://code.example.org/gitlab/{namespace}/project"
