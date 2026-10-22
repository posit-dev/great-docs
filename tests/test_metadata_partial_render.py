"""
Translations, text direction and page dates in pages rendered by Quarto
"""

import shutil
import subprocess
from pathlib import Path

import pytest

import great_docs
from great_docs._website import head, page_dates

BUNDLED = Path(great_docs.__file__).parent / "assets" / "metadata.html"

pytestmark = pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")


def test_partial_and_direction_reach_the_page(tmp_path: Path):
    """
    Render literal dollar signs and right-to-left text direction

    The partial uses `$$` to escape each literal `$` in the translation bundle.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "metadata.html").write_text(
        '<meta charset="utf-8" />\n<title>$pagetitle$</title>\n'
        '<meta name="gd-i18n" content="a$$b">\n',
        encoding="utf-8",
    )
    (project / "_quarto.yml").write_text(
        "project:\n  type: website\nwebsite:\n  title: t\n"
        "format:\n  html:\n    dir: rtl\n    template-partials:\n      - metadata.html\n",
        encoding="utf-8",
    )
    (project / "index.qmd").write_text("---\ntitle: T\n---\n\nText\n", encoding="utf-8")

    subprocess.run(["quarto", "render"], cwd=project, check=True, capture_output=True)

    page = (project / "_site" / "index.html").read_text(encoding="utf-8")
    assert page.count('<meta name="gd-i18n" content="a$b">') == 1
    assert 'dir="rtl"' in page[page.index("<html") : page.index(">", page.index("<html"))]


def test_page_dates_reach_the_page(tmp_path: Path) -> None:
    """
    Preserve head tags from two writers through Quarto rendering

    Apply the generated-page marker to every page beneath its directory.
    """
    project = tmp_path / "proj"
    (project / "reference").mkdir(parents=True)
    (project / "metadata.html").write_text(
        BUNDLED.read_text(encoding="utf-8").rstrip("\n")
        + "\n"
        + page_dates.partial_lines("2026-10-16T12:00:00")
        + "\n",
        encoding="utf-8",
    )
    (project / "_quarto.yml").write_text(
        "project:\n  type: website\nwebsite:\n  title: t\n"
        "format:\n  html:\n    template-partials:\n      - metadata.html\n",
        encoding="utf-8",
    )
    page = head.add_tags(
        "---\ntitle: T\n---\n\nText\n", [head.meta_element("gd-page-author", 'O\'Brien & "Co"')]
    )
    page = head.add_tags(page, [head.meta_element("other", "x`y")])
    (project / "index.qmd").write_text(page, encoding="utf-8")
    (project / "reference" / "_metadata.yml").write_text(
        f"{page_dates.AUTO_GENERATED}: true\n", encoding="utf-8"
    )
    (project / "reference" / "f.qmd").write_text("---\ntitle: F\n---\n\nText\n", encoding="utf-8")

    subprocess.run(["quarto", "render"], cwd=project, check=True, capture_output=True)

    page = (project / "_site" / "index.html").read_text(encoding="utf-8")
    generated = (project / "_site" / "reference" / "f.html").read_text(encoding="utf-8")
    build_time = '<meta name="gd-build-time" content="2026-10-16T12:00:00">'
    # Pandoc decodes the apostrophe, which needs no escape in a double-quoted value.
    assert page.count('<meta name="gd-page-author" content="O\'Brien &amp; &quot;Co&quot;">') == 1
    assert page.count('<meta name="other" content="x`y">') == 1
    assert 'name="gd-auto-generated"' not in page
    assert generated.count('<meta name="gd-auto-generated" content="true">') == 1
    assert 'name="gd-page-' not in generated
    assert page.count(build_time) == generated.count(build_time) == 1


def test_robots_front_matter_reaches_the_page(tmp_path: Path):
    """Emit a robots meta tag only on pages that set `robots`"""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "metadata.html").write_text(BUNDLED.read_text(encoding="utf-8"), encoding="utf-8")
    (project / "_quarto.yml").write_text(
        "project:\n  type: website\nwebsite:\n  title: t\n"
        "format:\n  html:\n    template-partials:\n      - metadata.html\n",
        encoding="utf-8",
    )
    (project / "index.qmd").write_text("---\ntitle: T\n---\n\nText\n", encoding="utf-8")
    (project / "draft.qmd").write_text(
        '---\ntitle: D\nrobots: "noindex, nofollow"\n---\n\nText\n', encoding="utf-8"
    )

    subprocess.run(["quarto", "render"], cwd=project, check=True, capture_output=True)

    draft = (project / "_site" / "draft.html").read_text(encoding="utf-8")
    index = (project / "_site" / "index.html").read_text(encoding="utf-8")
    head_end = draft.index("</head>")
    assert draft[:head_end].count('<meta name="robots" content="noindex, nofollow">') == 1
    assert 'name="robots"' not in index
