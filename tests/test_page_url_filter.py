"""
Canonical-link and Open Graph URL tags in Quarto output
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_EXTENSION = Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions" / "page-url"

pytestmark = pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")


def _render_site(
    tmp_path: Path, base: str | None, *, canonical: bool = True, og_url: bool = False
) -> Path:
    """
    Render a three-page site and return its output directory
    """
    project = tmp_path / "proj"
    (project / "_extensions").mkdir(parents=True)
    (project / "guide").mkdir()
    shutil.copytree(_EXTENSION, project / "_extensions" / "page-url")

    base_line = ""
    if base:
        base_line = f'gd-base-url: "{base}"\ngd-canonical: {str(canonical).lower()}\n'
        base_line += f"gd-og-url: {str(og_url).lower()}\n"
    (project / "_quarto.yml").write_text(
        f"project:\n  type: website\n{base_line}filters:\n  - page-url\nwebsite:\n  title: t\n",
        encoding="utf-8",
    )
    for page in ("index.qmd", "guide/index.qmd", "guide/page.qmd"):
        (project / page).write_text("---\ntitle: T\n---\n\nText\n", encoding="utf-8")

    subprocess.run(["quarto", "render"], cwd=project, check=True, capture_output=True)
    return project / "_site"


def _canonicals(page: Path) -> list[str]:
    return re.findall(r'<link rel="canonical" href="([^"]*)">', page.read_text(encoding="utf-8"))


def _og_urls(page: Path) -> list[str]:
    return re.findall(
        r'<meta property="og:url" content="([^"]*)">', page.read_text(encoding="utf-8")
    )


def test_canonical_links_use_page_and_directory_urls(tmp_path):
    site = _render_site(tmp_path, "https://docs.example.com/pkg/")

    assert _canonicals(site / "index.html") == ["https://docs.example.com/pkg/"]
    assert _canonicals(site / "guide" / "index.html") == ["https://docs.example.com/pkg/guide/"]
    assert _canonicals(site / "guide" / "page.html") == [
        "https://docs.example.com/pkg/guide/page.html"
    ]


def test_omits_canonical_links_without_a_base_url(tmp_path):
    site = _render_site(tmp_path, None)

    assert _canonicals(site / "index.html") == []


def test_og_urls_match_the_canonical_links(tmp_path):
    site = _render_site(tmp_path, "https://docs.example.com/pkg/", og_url=True)

    for page in ("index.html", "guide/index.html", "guide/page.html"):
        assert _og_urls(site / page) == _canonicals(site / page)
        assert len(_og_urls(site / page)) == 1


def test_og_urls_without_canonical_links(tmp_path):
    site = _render_site(tmp_path, "https://docs.example.com/pkg/", canonical=False, og_url=True)

    assert _canonicals(site / "guide" / "page.html") == []
    assert _og_urls(site / "guide" / "page.html") == [
        "https://docs.example.com/pkg/guide/page.html"
    ]


def test_canonical_links_without_og_urls(tmp_path):
    site = _render_site(tmp_path, "https://docs.example.com/pkg/")

    assert _og_urls(site / "guide" / "page.html") == []
