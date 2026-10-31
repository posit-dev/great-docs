"""
Tests for GitHub repository URL parsing and environment tokens
"""

from __future__ import annotations

import pytest

from great_docs._github import GithubRepo, token_from_env


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/posit-dev/great-docs", GithubRepo("posit-dev", "great-docs")),
        ("https://github.com/posit-dev/great-docs.git", GithubRepo("posit-dev", "great-docs")),
        ("git@github.com:posit-dev/great-docs.git", GithubRepo("posit-dev", "great-docs")),
        ("https://github.com/o/r/", GithubRepo("o", "r")),
        ("https://github.com/o/r/tree/main?tab=readme#top", GithubRepo("o", "r")),
        ("https://gitlab.com/a/b", None),
        ("https://github.com/", None),
        ("http://github.com", None),
        ("https://github.com/owner/.git", None),
        ("", None),
        (None, None),
    ],
)
def test_parse(url, expected):
    assert GithubRepo.parse(url) == expected


def test_url():
    assert GithubRepo("posit-dev", "great-docs").url == "https://github.com/posit-dev/great-docs"


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
