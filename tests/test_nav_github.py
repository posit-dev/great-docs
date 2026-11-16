"""
Tests for provider branding and build-time repository navigation
"""

from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

from great_docs._project.repository import Repository
from great_docs._website.navigation import repository


@pytest.mark.parametrize("provider", ["github", "gitlab"])
@pytest.mark.parametrize("stats", [None, {}, {"stars": 0, "forks": 3}, {"stars": 12}])
def test_widget_destinations_branding_and_optional_counts(provider, stats) -> None:
    repo = Repository(
        provider,
        f"https://{provider}.com",
        "team/subgroup" if provider == "gitlab" else "owner",
        "repo",
    )
    item = repository.navbar_item(repo, "widget", stats)
    widget = BeautifulSoup(item["text"], "html.parser").select_one(f"span#{repository.WIDGET_ID}")
    assert widget is not None
    assert item["href"] == repo.url
    assert widget["data-provider"] == provider
    assert widget["data-label"] == repo.label
    assert widget["data-url"] == repo.url
    assert widget["data-issues-url"] == repo.issues_url
    assert widget["data-requests-url"] == repo.requests_url
    assert widget["data-releases-url"] == repo.releases_url
    assert widget["data-fork-url"] == repo.fork_url
    assert ("data-public-api" in widget.attrs) == (provider == "github")
    for count in ("stars", "forks"):
        value = stats.get(count) if stats else None
        assert widget.attrs.get(f"data-{count}") == (str(value) if value is not None else None)


def test_widget_escapes_attribute_values() -> None:
    repo = Repository("gitlab", "https://code.example.org/gitlab", 'group/quoted"&', "repo")
    item = repository.navbar_item(repo, "widget", None)
    widget = BeautifulSoup(item["text"], "html.parser").select_one("span")
    assert widget is not None
    assert widget["data-url"] == repo.url
    assert "quoted%22%26" in str(widget)


@pytest.mark.parametrize("provider", ["github", "gitlab"])
def test_icon_style_uses_provider_branding(provider) -> None:
    repo = Repository(provider, f"https://{provider}.com", "owner", "repo")
    assert repository.navbar_item(repo, "icon", None) == {
        "icon": provider,
        "href": repo.url,
        "aria-label": repo.label,
    }


def test_unknown_counts_are_not_fabricated() -> None:
    repo = Repository("gitlab", "https://gitlab.com", "group", "repo")
    item = repository.navbar_item(repo, "widget", {"stars": -1, "forks": True})
    assert "data-stars" not in item["text"]
    assert "data-forks" not in item["text"]
