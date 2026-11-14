"""
Social card metadata rendered from site and page options
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from yaml12 import format_yaml

import great_docs
from great_docs._build.quarto import executable as quarto_executable
from great_docs._website import page_metadata, social_cards
from great_docs.config import Config

pytestmark = pytest.mark.skipif(
    shutil.which(quarto_executable()) is None, reason="Quarto is not installed"
)

IMAGE = "https://docs.example.com/pkg/card.png"
_TAG = re.compile(r'<meta (?:property|name)="((?:og|twitter):[\w:]+)" content="([^"]*)"')


def _render_site(
    tmp_path: Path, yaml: str, image_url: str | None, *, per_page: bool = False
) -> tuple[Path, str]:
    """
    Render a two-page site with the supplied social card settings

    Returns
    -------
    :
        The output directory and Quarto's console output.
    """
    (tmp_path / "great-docs.yml").write_text(yaml, encoding="utf-8")
    project = tmp_path / "proj"
    (project / "guide").mkdir(parents=True)
    quarto: dict = {"project": {"type": "website"}, "website": {"title": "Pkg"}}
    social_cards.register(quarto, Config(tmp_path), image_url, project)
    (project / "_quarto.yml").write_text(format_yaml(quarto), encoding="utf-8")
    (project / "index.qmd").write_text("---\ntitle: Home\n---\n\nWelcome text.\n", encoding="utf-8")
    (project / "guide" / "page.qmd").write_text(
        "---\ntitle: Page\n---\n\nPage text that is longer than thirty characters.\n",
        encoding="utf-8",
    )
    if per_page:
        page_metadata.write_to_pages(project, quarto, Config(tmp_path), "Site default")

    result = subprocess.run(
        [quarto_executable(), "render"], cwd=project, check=True, capture_output=True, text=True
    )
    return project / "_site", result.stdout + result.stderr


def _tags(page: Path) -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for name, content in _TAG.findall(page.read_text(encoding="utf-8")):
        tags.setdefault(name, []).append(content)
    return tags


def test_site_options_without_settings(tmp_path):
    site, _ = _render_site(tmp_path, "", None)

    tags = _tags(site / "guide" / "page.html")
    assert tags["og:site_name"] == ["Pkg"]
    assert tags["og:title"] == ["Page – Pkg"]
    assert tags["twitter:card"] == ["summary"]
    assert "og:image" not in tags


def test_site_options_with_image_and_handle(tmp_path):
    yaml = "social_cards:\n  twitter_site: myhandle\n"
    site, output = _render_site(tmp_path, yaml, IMAGE)

    tags = _tags(site / "guide" / "page.html")
    assert tags["og:image"] == [IMAGE]
    assert tags["twitter:image"] == [IMAGE]
    assert tags["twitter:card"] == ["summary_large_image"]
    assert tags["twitter:site"] == ["@myhandle"]
    assert IMAGE not in output


def test_page_options_merge_with_the_site_options(tmp_path):
    site, _ = _render_site(tmp_path, "", IMAGE, per_page=True)

    tags = _tags(site / "guide" / "page.html")
    assert tags["og:title"] == ["Page | Pkg"]
    assert tags["twitter:title"] == ["Page | Pkg"]
    assert tags["og:description"] == ["Page text that is longer than thirty characters."]
    assert tags["twitter:description"] == tags["og:description"]
    assert tags["og:image"] == [IMAGE]
    assert _tags(site / "index.html")["og:description"] == ["Site default"]


def test_pages_with_their_own_tags_keep_them_alone(tmp_path):
    """Leave out every generated card tag on a page whose header includes declare its own"""
    (tmp_path / "great-docs.yml").write_text("", encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assets = Path(great_docs.__file__).parent / "assets"
    shutil.copytree(assets / "_extensions" / "page-url", project / "_extensions" / "page-url")
    partial = (assets / "metadata.html").read_text(encoding="utf-8")
    (project / "metadata.html").write_text(
        partial + social_cards.OG_TYPE_PARTIAL + "\n", encoding="utf-8"
    )
    quarto: dict = {
        "project": {"type": "website"},
        "website": {"title": "Pkg"},
        "format": {"html": {"template-partials": ["metadata.html"]}},
        "filters": ["page-url"],
        "gd-base-url": "https://docs.example.com/pkg/",
        "gd-og-url": True,
    }
    social_cards.register(quarto, Config(tmp_path), IMAGE, project)
    (project / "_quarto.yml").write_text(format_yaml(quarto), encoding="utf-8")
    own = '<meta property="og:title" content="Mine">'
    (project / "own.qmd").write_text(
        f"---\ntitle: Own\nheader-includes: |\n  {own}\n---\n\nText.\n", encoding="utf-8"
    )
    (project / "plain.qmd").write_text("---\ntitle: Plain\n---\n\nText.\n", encoding="utf-8")
    page_metadata.write_to_pages(project, quarto, Config(tmp_path), None)

    subprocess.run([quarto_executable(), "render"], cwd=project, check=True, capture_output=True)

    # Quarto rewrites the first `og:title` to its page title on every page,
    # with or without card tags, so only the absence of other tags is ours
    assert _tags(project / "_site" / "own.html") == {"og:title": ["Own – Pkg"]}
    plain = _tags(project / "_site" / "plain.html")
    assert plain["og:type"] == ["website"]
    assert plain["og:url"] == ["https://docs.example.com/pkg/plain.html"]
    assert plain["og:title"] == ["Plain | Pkg"]
