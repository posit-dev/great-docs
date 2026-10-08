"""
Canonical links in pages rendered by Quarto
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_EXTENSION = Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions" / "canonical"

pytestmark = pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")


def _render_site(tmp_path: Path, base: str | None) -> Path:
    """
    Render a three-page site and return its output directory
    """
    project = tmp_path / "proj"
    (project / "_extensions").mkdir(parents=True)
    (project / "guide").mkdir()
    shutil.copytree(_EXTENSION, project / "_extensions" / "canonical")

    base_line = f'gd-canonical-base-url: "{base}"\n' if base else ""
    (project / "_quarto.yml").write_text(
        f"project:\n  type: website\n{base_line}filters:\n  - canonical\nwebsite:\n  title: t\n",
        encoding="utf-8",
    )
    for page in ("index.qmd", "guide/index.qmd", "guide/page.qmd"):
        (project / page).write_text("---\ntitle: T\n---\n\nText\n", encoding="utf-8")

    subprocess.run(["quarto", "render"], cwd=project, check=True, capture_output=True)
    return project / "_site"


def _canonicals(page: Path) -> list[str]:
    return re.findall(r'<link rel="canonical" href="([^"]*)">', page.read_text(encoding="utf-8"))


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
