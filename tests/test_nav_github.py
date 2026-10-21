"""
Tests for the GitHub entry in the navbar

The widget style uses a link with a raw `<span>` as its text. Quarto
renders the span unescaped. The icon style uses a plain GitHub icon link.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from great_docs._website.navigation import github

REPO_URL = "https://github.com/owner/repo"


def _widget_attrs(item: dict[str, str]) -> dict[str, str]:
    """
    Parse the attributes of the widget element in a navbar item's text

    Parameters
    ----------
    item
        A navbar entry built for the widget style.

    Returns
    -------
    :
        The attributes of the single `span` with the widget ID.
    """
    spans = BeautifulSoup(item["text"], "html.parser").select(f"span#{github.WIDGET_ID}")
    assert len(spans) == 1
    return {k: str(v) for k, v in spans[0].attrs.items()}


def test_widget_item_links_to_repo_and_carries_stats():
    item = github.navbar_item(REPO_URL, "owner", "repo", "widget", {"stars": 12, "forks": 3})

    assert item["href"] == REPO_URL
    assert _widget_attrs(item) == {
        "id": github.WIDGET_ID,
        "data-owner": "owner",
        "data-repo": "repo",
        "data-stars": "12",
        "data-forks": "3",
    }


def test_widget_item_without_stats_omits_counts():
    item = github.navbar_item(REPO_URL, "owner", "repo", "widget", None)

    attrs = _widget_attrs(item)
    assert "data-stars" not in attrs
    assert "data-forks" not in attrs


def test_widget_item_escapes_attribute_values():
    item = github.navbar_item(REPO_URL, 'o"w&n', "repo", "widget", None)

    assert _widget_attrs(item)["data-owner"] == 'o"w&n'


def test_icon_item_for_icon_style_or_missing_repo():
    icon = {"icon": "github", "href": REPO_URL}

    assert github.navbar_item(REPO_URL, "owner", "repo", "icon", None) == icon
    assert github.navbar_item(REPO_URL, None, "repo", "widget", None) == icon
    assert github.navbar_item(REPO_URL, "owner", None, "widget", None) == icon


def test_set_navbar_item_replaces_icon_and_legacy_widget_entries():
    item = {"icon": "github", "href": REPO_URL}
    navbar = {
        "right": [
            {"icon": "github", "href": "old"},
            {"text": "Other"},
            {"text": '<div id="github-widget" data-owner="o" data-repo="r"></div>'},
        ]
    }

    github.set_navbar_item(navbar, item)

    assert navbar["right"] == [item, {"text": "Other"}, item]


def test_set_navbar_item_appends_after_other_items():
    item = {"icon": "github", "href": REPO_URL}
    navbar = {"right": ["text-only", {"text": "Other"}]}
    empty: dict = {}

    github.set_navbar_item(navbar, item)
    github.set_navbar_item(empty, item)

    assert navbar["right"] == ["text-only", {"text": "Other"}, item]
    assert empty["right"] == [item]
