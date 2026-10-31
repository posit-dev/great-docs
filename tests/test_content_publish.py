from pathlib import Path

import pytest

from great_docs._content import publish
from great_docs._content.pages import PageMap
from great_docs._layout import Layout
from tests.support import write_config


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    (tmp_path / "great-docs.yml").write_text("", encoding="utf-8")
    return Layout.make(tmp_path)


def page_map(root: Path, layout: Layout, guide: Path | None = None) -> PageMap:
    return PageMap.make(write_config(root), layout, guide, [])


def test_copy_asset_keeps_an_identical_copy(tmp_path: Path, layout: Layout):
    source = tmp_path / "logo.svg"
    source.write_text("logo")

    first = publish.copy_asset(layout, source, layout.build_dir / "logo.svg")
    second = publish.copy_asset(layout, source, layout.build_dir / "logo.svg")

    assert first == second
    assert second.read_text() == "logo"


def test_copy_asset_refuses_a_destination_outside_the_build_directory(
    tmp_path: Path, layout: Layout
):
    source = tmp_path / "logo.svg"
    source.write_text("logo")

    with pytest.raises(ValueError, match="escapes the build directory"):
        publish.copy_asset(layout, source, tmp_path / "logo-copy.svg")


@pytest.mark.parametrize(
    "markup",
    ["![Logo](images/logo.png)", '<img src="images/logo.png">', "[Download](images/logo.png)"],
)
def test_a_referenced_file_is_copied_beside_the_page(tmp_path: Path, layout: Layout, markup: str):
    (tmp_path / "images").mkdir()
    (tmp_path / "images/logo.png").write_bytes(b"image")

    result = publish.rebase_references(
        markup,
        tmp_path / "README.md",
        layout.build_dir / "index.qmd",
        layout=layout,
        pages=page_map(tmp_path, layout),
    )

    assert result == markup
    assert (layout.build_dir / "images/logo.png").read_bytes() == b"image"


@pytest.mark.parametrize(
    "reference",
    [
        "https://example.com/logo.png",
        "//example.com/logo.png",
        "data:image/png;base64,abc",
        "#anchor",
        "images/missing.png",
    ],
)
def test_urls_anchors_and_missing_files_are_left_alone(
    tmp_path: Path, layout: Layout, reference: str
):
    markup = f"![Logo]({reference})"

    result = publish.rebase_references(
        markup,
        tmp_path / "README.md",
        layout.build_dir / "index.qmd",
        layout=layout,
        pages=page_map(tmp_path, layout),
    )

    assert result == markup


def test_a_link_to_a_page_points_at_its_published_path(tmp_path: Path, layout: Layout):
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "01-start.qmd").write_text("# Start")
    (guide / "02-next.qmd").write_text("# Next")

    result = publish.rebase_references(
        "[Next](02-next.qmd#more)",
        guide / "01-start.qmd",
        layout.build_dir / "user-guide/start.qmd",
        layout=layout,
        pages=page_map(tmp_path, layout, guide),
    )

    assert result == "[Next](next.qmd#more)"


def test_a_bibliography_is_shared_and_keeps_the_front_matter_valid(tmp_path: Path, layout: Layout):
    source = tmp_path / "user_guide/page.qmd"
    source.parent.mkdir()
    (tmp_path / "refs.bib").write_text("@book{example, title={Example}}\n")
    content = "---\ntitle: Page\nbibliography: ../refs.bib\n---\n\nText\n"

    result = publish.rebase_references(
        content,
        source,
        layout.build_dir / "user-guide/page.qmd",
        layout=layout,
        pages=page_map(tmp_path, layout),
    )

    assert result == "---\ntitle: Page\nbibliography: ../_shared/refs.bib\n---\n\nText\n"
    assert (layout.build_dir / "_shared/refs.bib").is_file()


def test_front_matter_that_is_not_a_mapping_is_left_alone(tmp_path: Path, layout: Layout):
    content = "---\n- a\n---\n\nText\n"

    result = publish.rebase_references(
        content,
        tmp_path / "page.qmd",
        layout.build_dir / "page.qmd",
        layout=layout,
        pages=page_map(tmp_path, layout),
    )

    assert result == content


def stamp(content: str, source: Path) -> str:
    return f"{content}<!-- dates of {source.name} -->\n"


def test_a_page_is_written_with_its_includes_and_rebased_links(tmp_path: Path, layout: Layout):
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "snippet.py").write_text("x = 1\n")
    (guide / "02-next.qmd").write_text("# Next")
    source = guide / "01-start.qmd"
    source.write_text(
        "---\ntitle: Start\n---\n\n{{< include snippet.py >}}\n\n[Next](02-next.qmd)\n"
    )
    destination = layout.build_dir / "user-guide/start.qmd"

    front_matter = publish.page(
        source,
        destination,
        layout=layout,
        pages=page_map(tmp_path, layout, guide),
        add_dates=stamp,
        strip_prefix=True,
        breadcrumbs=None,
    )

    assert front_matter.string("title") == "Start"
    assert destination.read_text() == (
        "---\ntitle: Start\n---\n\n```python\nx = 1\n```\n\n[Next](next.qmd)\n"
        "<!-- dates of 01-start.qmd -->\n"
    )


def test_a_page_moved_to_the_homepage_has_no_dates(tmp_path: Path, layout: Layout):
    source = tmp_path / "user_guide/intro.qmd"
    source.parent.mkdir()
    source.write_text("# Intro\n")
    pages = page_map(tmp_path, layout)
    destination = layout.build_dir / "user-guide/intro.qmd"

    publish.page(
        source,
        destination,
        layout=layout,
        pages=pages,
        add_dates=stamp,
        strip_prefix=True,
        breadcrumbs=None,
        published=pages.homepage,
    )

    assert destination.read_text() == "# Intro\n"
