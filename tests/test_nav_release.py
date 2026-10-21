"""
Tests for the latest release in the navbar

A navbar with a text title shows the badge in `website.navbar.title`.
A navbar with only a logo shows the release in a tooltip, supplied through
a header meta tag.
"""

from __future__ import annotations

import copy
import html
import re
from typing import Any

from great_docs._website.navigation.release import Release, add_to_navbar

RELEASE = Release(version="2.3.4", date="2025-06-15")
BADGE = '`<span class="version-badge" title="Released 2025-06-15">v2.3.4</span>`{=html}'


def _quarto_config(**navbar: Any) -> dict[str, Any]:
    """
    Build a minimal `_quarto.yml` mapping for a site titled `Pkg`

    Parameters
    ----------
    **navbar
        Entries for `website.navbar`.

    Returns
    -------
    :
        The configuration.
    """
    return {
        "website": {"title": "Pkg", "navbar": dict(navbar)},
        "format": {"html": {}},
    }


def _tooltips(config: dict[str, Any]) -> list[str]:
    """
    Unescape the tooltip HTML from each logo tooltip meta tag

    Parameters
    ----------
    config
        The `_quarto.yml` mapping.

    Returns
    -------
    :
        The tooltip HTML from each logo tooltip meta tag, in order.
    """
    header = config["format"]["html"].get("include-in-header", [])
    return [
        html.unescape(m.group(1))
        for entry in header
        if (m := re.search(r'name="gd-logo-tooltip" content="([^"]*)"', str(entry)))
    ]


def test_release_from_github_entry():
    release = Release.make({"tag_name": "v2.3.4", "published_at": "2025-06-15T18:30:00Z"})

    assert release == RELEASE


def test_release_without_date():
    assert Release.make({"tag_name": "1.0"}) == Release(version="1.0", date=None)


def test_release_from_tag_without_version():
    assert Release.make({"tag_name": "v"}) is None
    assert Release.make({"tag_name": ""}) is None


def test_badge_follows_the_text_title():
    config = _quarto_config(left=[])

    add_to_navbar(config, RELEASE, "en")

    assert config["website"]["navbar"]["title"] == f"Pkg {BADGE}"
    assert _tooltips(config) == []


def test_badge_without_date_has_no_hover_text():
    config = _quarto_config()

    add_to_navbar(config, Release(version="1.0", date=None), "en")

    assert config["website"]["navbar"]["title"] == (
        'Pkg `<span class="version-badge">v1.0</span>`{=html}'
    )


def test_logo_only_brand_gets_a_tooltip():
    config = _quarto_config(logo="logo.svg", title=False)

    add_to_navbar(config, RELEASE, "en")

    assert config["website"]["navbar"]["title"] is False
    assert _tooltips(config) == ["<code>v2.3.4</code><br>Released 2025-06-15"]


def test_logo_with_title_gets_the_badge():
    config = _quarto_config(logo="logo.svg")

    add_to_navbar(config, RELEASE, "en")

    assert config["website"]["navbar"]["title"] == f"Pkg {BADGE}"
    assert _tooltips(config) == []


def test_no_release_removes_an_earlier_badge():
    config = _quarto_config(logo="logo.svg", title=False)
    add_to_navbar(config, RELEASE, "en")
    text_config = _quarto_config()
    add_to_navbar(text_config, RELEASE, "en")

    add_to_navbar(config, None, "en")
    add_to_navbar(text_config, None, "en")

    assert _tooltips(config) == []
    assert "title" not in text_config["website"]["navbar"]


def test_repeated_calls_give_the_same_config():
    for navbar in ({}, {"logo": "logo.svg", "title": False}):
        config = _quarto_config(**navbar)
        add_to_navbar(config, RELEASE, "en")
        once = copy.deepcopy(config)

        add_to_navbar(config, RELEASE, "en")

        assert config == once


def test_release_line_follows_the_site_language():
    text_config = _quarto_config()
    logo_config = _quarto_config(logo="logo.svg", title=False)

    add_to_navbar(text_config, RELEASE, "fr")
    add_to_navbar(logo_config, RELEASE, "fr")

    assert 'title="Publié le 2025-06-15"' in text_config["website"]["navbar"]["title"]
    assert _tooltips(logo_config) == ["<code>v2.3.4</code><br>Publié le 2025-06-15"]


def test_version_is_escaped():
    text_config = _quarto_config()
    logo_config = _quarto_config(logo="logo.svg", title=False)
    release = Release(version='1<2"', date=None)

    add_to_navbar(text_config, release, "en")
    add_to_navbar(logo_config, release, "en")

    assert ">v1&lt;2&quot;</span>" in text_config["website"]["navbar"]["title"]
    assert _tooltips(logo_config) == ["<code>v1&lt;2&quot;</code>"]
