"""
JSON-LD structured data for the homepage and reference pages
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from great_docs._website.page_metadata import Page
from great_docs._website.seo.structured_data import StructuredData, licence_url
from great_docs.config import Config
from tests.support import write_config

BASE_URL = "https://example.org/pkg/"
METADATA = {
    "description": "A package",
    "license": "MIT",
    "urls": {"Repository": "https://github.com/o/pkg"},
}
_SCRIPT = re.compile(r'^<script type="application/ld\+json">(.*)</script>$')


def _data(
    tmp_path: Path, metadata: dict[str, Any] = METADATA, base_url: str | None = BASE_URL
) -> StructuredData:
    data = StructuredData.make(write_config(tmp_path), metadata, "Pkg", base_url)
    assert data is not None
    return data


def _page(tmp_path: Path, relative_path: str, content: str = "Body\n") -> Page:
    path = tmp_path / "site" / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return Page.make(path, tmp_path / "site")


def _parse(tag: str | None) -> dict[str, Any] | list[dict[str, Any]]:
    assert tag is not None
    match = _SCRIPT.match(tag)
    assert match, tag
    return json.loads(match.group(1))


@pytest.mark.parametrize(
    "yaml", ["seo:\n  structured_data:\n    enabled: false\n", "seo:\n  enabled: false\n"]
)
def test_make_is_none_when_disabled(tmp_path: Path, yaml: str) -> None:
    assert StructuredData.make(write_config(tmp_path, yaml), METADATA, "Pkg", BASE_URL) is None


def test_package_object(tmp_path: Path) -> None:
    config = write_config(tmp_path, "seo:\n  structured_data:\n    type: SoftwareApplication\n")
    data = StructuredData.make(config, METADATA, "Pkg", BASE_URL)
    assert data is not None
    assert data.package == {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Pkg",
        "description": "A package",
        "codeRepository": "https://github.com/o/pkg",
        "license": "https://opensource.org/licenses/MIT",
        "url": "https://example.org/pkg",
        "documentation": "https://example.org/pkg",
        "programmingLanguage": {"@type": "ComputerLanguage", "name": "Python"},
    }


def test_package_object_omits_empty_values(tmp_path: Path) -> None:
    data = StructuredData.make(write_config(tmp_path), {}, "", None)
    assert data is not None
    assert data.package == {
        "@context": "https://schema.org",
        "@type": "SoftwareSourceCode",
        "programmingLanguage": {"@type": "ComputerLanguage", "name": "Python"},
    }


def test_licence_url() -> None:
    assert licence_url("https://example.org/LICENSE") == "https://example.org/LICENSE"
    assert licence_url("MIT") == "https://opensource.org/licenses/MIT"
    assert licence_url("apache-2.0") == "https://opensource.org/licenses/Apache-2.0"
    assert licence_url("Proprietary") == "Proprietary"


def test_tag_on_the_homepage_and_reference_index(tmp_path: Path) -> None:
    data = _data(tmp_path)
    for rel in ("index.qmd", "reference/index.qmd"):
        assert _parse(data.tag(_page(tmp_path, rel))) == data.package


def test_tag_on_reference_pages_adds_a_web_page(tmp_path: Path) -> None:
    data = _data(tmp_path)
    for rel, name in (
        ("reference/Pipeline.run.qmd", "Pipeline.run"),
        ("reference/cli/build.qmd", "cli/build"),
    ):
        page = _page(tmp_path, rel)
        assert _parse(data.tag(page)) == [
            data.package,
            {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": f"{name} - Pkg",
                "isPartOf": {"@type": "WebSite", "name": "Pkg"},
                "url": BASE_URL + page.output_path,
            },
        ]


def test_no_tag_on_other_pages(tmp_path: Path) -> None:
    assert _data(tmp_path).tag(_page(tmp_path, "user-guide/intro.qmd")) is None


def test_no_tag_on_a_page_with_its_own(tmp_path: Path) -> None:
    text = '```{=html}\n<script type="application/ld+json">{}</script>\n```\n'
    assert _data(tmp_path).tag(_page(tmp_path, "index.qmd", text)) is None


@pytest.mark.parametrize(
    "text",
    [
        "Search engines read `application/ld+json` scripts.\n",
        "JSON-LD uses the `application/ld+json` media type.\n",
    ],
)
def test_tag_despite_mentions_of_json_ld(tmp_path: Path, text: str) -> None:
    assert _data(tmp_path).tag(_page(tmp_path, "index.qmd", text)) is not None


def test_no_tag_on_a_page_whose_header_includes_have_json_ld(tmp_path: Path) -> None:
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "schema.html").write_text(
        '<script type="application/ld+json">{}</script>', encoding="utf-8"
    )
    text = "---\ninclude-in-header: schema.html\n---\n\nBody\n"
    assert _data(tmp_path).tag(_page(tmp_path, "index.qmd", text)) is None


def test_add_to_raw_page(tmp_path: Path) -> None:
    data = _data(tmp_path)
    page = "<html><head></head></html>"
    assert data.add_to_raw_page(page, "demos/widget.html") == page
    added = data.add_to_raw_page(page, "reference/widget.html")
    assert added.count('type="application/ld+json"') == 1
    assert data.add_to_raw_page(added, "reference/widget.html") == added


def test_tag_escapes_the_script_body(tmp_path: Path) -> None:
    description = "Ends </script><script>alert(1)</script> & `code` ``more``"
    data = _data(tmp_path, {"description": description})
    tag = data.tag(_page(tmp_path, "index.qmd"))
    assert tag is not None and "\n" not in tag
    match = _SCRIPT.match(tag)
    assert match is not None
    body = match.group(1)
    assert not set("<>&") & set(body)
    assert json.loads(body)["description"] == description


def test_applies_unless_the_site_header_has_json_ld(tmp_path: Path) -> None:
    data = _data(tmp_path)
    assert data.applies({}, tmp_path)
    include = {"text": '<script type="application/ld+json">{}</script>'}
    site = {"format": {"html": {"include-in-header": [include]}}}
    assert not data.applies(site, tmp_path)
