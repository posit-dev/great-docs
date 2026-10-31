"""
Tests for GitHub repository URL parsing
"""

from __future__ import annotations

import pytest

from great_docs._github import GithubRepo


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
