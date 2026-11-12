"""Tests for `window.greatDocsVersions` in `version-selector.js`, run with Node in a stub page."""

from __future__ import annotations

import shutil
from typing import Any

import pytest

from tests.version_selector_page import run_selector

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

VERSIONS = [
    {"tag": "2.0", "label": "2.0 (latest)", "latest": True, "path_prefix": ""},
    {"tag": "1.5", "label": "1.5", "path_prefix": "v/1.5"},
    {"tag": "1.0", "label": "1.0", "path_prefix": "v/1.0", "eol": True},
]


def _map(pages: dict[str, list[str]], **fields: Any) -> dict[str, Any]:
    return {"versions": VERSIONS, "pages": pages, **fields}


EVERY_VERSION = ["2.0", "1.5", "1.0"]
GUIDE = _map({"index.html": EVERY_VERSION, "user-guide/intro.html": EVERY_VERSION})


class TestApi:
    def test_absent_without_a_version_map(self):
        result = run_selector(pathname="/user-guide/intro.html")
        assert result == {"api": False, "links": None, "banner": None, "stored": None}

    def test_absent_with_an_empty_version_list(self):
        assert not run_selector(map={"versions": [], "pages": {}})["api"]

    def test_lists_copies_of_the_versions_in_order(self):
        result = run_selector(map=GUIDE, pathname="/user-guide/intro.html")
        assert result["list"] == VERSIONS
        assert result["listIsCopy"]

    def test_ready_before_the_document_loads(self):
        result = run_selector(map=GUIDE, pathname="/v/1.5/index.html", loading=True)
        assert result["current"] == "1.5"
        assert result["urls"]["2.0"] == "/index.html"
        assert result["links"] is None

    def test_unknown_tag(self):
        result = run_selector(map=GUIDE, pathname="/index.html", tags=["3.0", "latest"])
        assert result["urls"] == {"3.0": None, "latest": None}


class TestUrlFor:
    def test_latest_at_the_root(self):
        result = run_selector(map=GUIDE, pathname="/user-guide/intro.html", offset="../")
        assert result["current"] == "2.0"
        assert result["urls"] == {
            "2.0": "/user-guide/intro.html",
            "1.5": "/v/1.5/user-guide/intro.html",
            "1.0": "/v/1.0/user-guide/intro.html",
        }

    def test_versioned_path(self):
        result = run_selector(map=GUIDE, pathname="/v/1.5/user-guide/intro.html")
        assert result["current"] == "1.5"
        assert result["urls"] == {
            "2.0": "/user-guide/intro.html",
            "1.5": "/v/1.5/user-guide/intro.html",
            "1.0": "/v/1.0/user-guide/intro.html",
        }

    def test_version_root(self):
        result = run_selector(map=GUIDE, pathname="/v/1.0/", tags=["2.0"])
        assert result["current"] == "1.0"
        assert result["urls"] == {"2.0": "/index.html"}

    def test_missing_page_falls_back_to_the_version_root(self):
        site = _map({"index.html": EVERY_VERSION, "reference/new.html": ["2.0"]})
        result = run_selector(map=site, pathname="/reference/new.html", offset="../")
        assert result["urls"] == {
            "2.0": "/reference/new.html",
            "1.5": "/v/1.5/index.html",
            "1.0": "/v/1.0/index.html",
        }

    def test_missing_page_uses_its_fallback(self):
        site = _map(
            {"index.html": EVERY_VERSION, "reference/new.html": ["2.0"]},
            fallbacks={"reference/new.html": "reference/index.html"},
        )
        result = run_selector(map=site, pathname="/reference/new.html", offset="../")
        assert result["urls"]["1.5"] == "/v/1.5/reference/index.html"

    def test_subpath_deployment_on_a_versioned_page(self):
        result = run_selector(map=GUIDE, pathname="/docs/v/1.5/user-guide/intro.html")
        assert result["urls"] == {
            "2.0": "/docs/user-guide/intro.html",
            "1.5": "/docs/v/1.5/user-guide/intro.html",
            "1.0": "/docs/v/1.0/user-guide/intro.html",
        }

    def test_subpath_deployment_on_the_latest_version(self):
        result = run_selector(map=GUIDE, pathname="/docs/user-guide/intro.html", offset="../")
        assert result["current"] == "2.0"
        assert result["urls"]["2.0"] == "/docs/user-guide/intro.html"
        assert result["urls"]["1.5"] == "/docs/v/1.5/user-guide/intro.html"


class TestSelectorAgrees:
    @pytest.mark.parametrize(
        ("pathname", "offset"),
        [
            ("/user-guide/intro.html", "../"),
            ("/docs/v/1.5/user-guide/intro.html", None),
            ("/v/1.0/reference/new.html", None),
        ],
    )
    def test_links_match_url_for(self, pathname: str, offset: str | None):
        site = _map({**GUIDE["pages"], "reference/new.html": ["2.0", "1.0"]})
        options: dict[str, Any] = {"map": site, "pathname": pathname}
        if offset is not None:
            options["offset"] = offset
        result = run_selector(**options)
        assert result["links"] == result["urls"]

    def test_banner_links_to_the_latest_url(self):
        result = run_selector(map=GUIDE, pathname="/v/1.0/user-guide/intro.html")
        assert result["banner"] == result["urls"]["2.0"] == "/user-guide/intro.html"

    def test_clicking_a_link_keeps_its_version(self):
        result = run_selector(map=GUIDE, pathname="/user-guide/intro.html", click="1.5")
        assert result["stored"] == "1.5"
