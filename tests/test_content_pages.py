from pathlib import Path

import pytest

from great_docs._content.pages import PageMap, output_destination, section_destination
from great_docs._layout import Layout
from tests.support import write_config


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    (tmp_path / "great-docs.yml").write_text("", encoding="utf-8")
    return Layout.make(tmp_path)


def write_page(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Page\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("directory", "published"),
    [
        ("examples", "examples"),
        ("docs/examples", "docs/examples"),
        ("My_Cool Dir", "my-cool-dir"),
    ],
)
def test_a_section_publishes_under_the_slug_of_its_directory(
    layout: Layout, directory: str, published: str
):
    section = {"title": "Ignored", "dir": directory}

    assert section_destination(layout, section) == layout.build_dir / published


@pytest.mark.parametrize("section", [{}, {"dir": ""}, {"dir": 42}])
def test_a_section_without_a_directory_has_no_destination(
    layout: Layout, section: dict[str, object]
):
    assert section_destination(layout, section) is None


def test_an_output_outside_the_build_directory_is_rejected(layout: Layout):
    with pytest.raises(ValueError, match="inside the build directory"):
        output_destination(layout, "../escape")


def test_homepage_sources_publish_as_the_homepage(tmp_path: Path, layout: Layout):
    readme = write_page(tmp_path / "README.md")

    pages = PageMap.make(write_config(tmp_path), layout, None, [readme])

    assert pages.destination(readme.resolve()) == layout.build_dir / "index.qmd"


def test_an_automatic_user_guide_drops_numeric_prefixes(tmp_path: Path, layout: Layout):
    guide = tmp_path / "user_guide"
    page = write_page(guide / "01-basics/02-setup.qmd")

    pages = PageMap.make(write_config(tmp_path), layout, guide, [])

    assert pages.destination(page.resolve()) == layout.build_dir / "user-guide/basics/setup.qmd"


def test_an_explicit_user_guide_keeps_its_file_names(tmp_path: Path, layout: Layout):
    guide = tmp_path / "user_guide"
    page = write_page(guide / "01-basics/02-setup.qmd")
    config = write_config(
        tmp_path, {"user_guide": [{"section": "Basics", "contents": ["01-basics/02-setup.qmd"]}]}
    )

    pages = PageMap.make(config, layout, guide, [])

    assert pages.destination(page.resolve()) == (
        layout.build_dir / "user-guide/01-basics/02-setup.qmd"
    )


def test_a_blog_keeps_its_post_names_and_a_section_drops_prefixes(tmp_path: Path, layout: Layout):
    post = write_page(tmp_path / "news/2024-01-welcome/index.qmd")
    example = write_page(tmp_path / "examples/01-intro.qmd")
    config = write_config(
        tmp_path,
        {
            "sections": [
                {"title": "News", "dir": "news", "type": "blog"},
                {"title": "Examples", "dir": "examples"},
            ]
        },
    )

    pages = PageMap.make(config, layout, None, [])

    assert pages.destination(post.resolve()) == layout.build_dir / "news/2024-01-welcome/index.qmd"
    assert pages.destination(example.resolve()) == layout.build_dir / "examples/intro.qmd"


def test_custom_pages_publish_under_their_output(tmp_path: Path, layout: Layout):
    page = write_page(tmp_path / "pages/01-landing.html")
    config = write_config(tmp_path, {"custom_pages": {"dir": "pages", "output": "site"}})

    pages = PageMap.make(config, layout, None, [])

    assert pages.destination(page.resolve()) == layout.build_dir.resolve() / "site/01-landing.html"


def test_a_page_outside_every_root_has_no_destination(tmp_path: Path, layout: Layout):
    page = write_page(tmp_path / "notes/draft.qmd")

    pages = PageMap.make(write_config(tmp_path), layout, None, [])

    assert pages.destination(page.resolve()) is None


def test_custom_pages_with_an_escaping_output_have_no_destination(tmp_path: Path, layout: Layout):
    page = write_page(tmp_path / "pages/landing.html")
    config = write_config(tmp_path, {"custom_pages": {"dir": "pages", "output": "../escape"}})

    pages = PageMap.make(config, layout, None, [])

    assert pages.destination(page.resolve()) is None
