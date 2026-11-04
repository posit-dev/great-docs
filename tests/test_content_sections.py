from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from great_docs import Config
from great_docs._content import sections
from great_docs._content.pages import PageMap
from great_docs._layout import Layout
from great_docs._yaml import split_front_matter
from tests.support import write_config


def test_source_dirs_resolves_each_section_directory(tmp_path: Path):
    config = write_config(
        tmp_path,
        "sections:\n"
        "  - title: Examples\n    dir: examples\n"
        "  - title: Blog\n    dir: posts/../blog\n"
        "  - title: Listing only\n",
    )

    result = sections.source_dirs(config, Layout.make(tmp_path))

    assert result == {(tmp_path / "examples").resolve(), (tmp_path / "blog").resolve()}


def test_source_dirs_is_relative_to_the_configuration(tmp_path: Path):
    config_path = tmp_path / "docs" / "great-docs.yml"
    config_path.parent.mkdir()
    config_path.write_text("sections:\n  - title: Examples\n    dir: examples\n")
    layout = Layout.make(tmp_path, config_path)
    config = Config(layout.package_root, config_path=layout.config_path)

    assert sections.source_dirs(config, layout) == {(tmp_path / "docs" / "examples").resolve()}


def test_source_dirs_ignores_malformed_sections(tmp_path: Path):
    config = write_config(tmp_path, "sections: examples\n")

    assert sections.source_dirs(config, Layout.make(tmp_path)) == set()


def _without_dates(content: str, _source: Path) -> str:
    return content


def _copying(project: Path) -> dict[str, Any]:
    """
    Build arguments for copying pages without dates or a user guide

    Parameters
    ----------
    project
        The project's root directory.

    Returns
    -------
    :
        The page-copying arguments.
    """
    config = Config(project)
    layout = Layout.make(project)
    return {
        "layout": layout,
        "pages": PageMap.make(config, layout, None, []),
        "add_dates": _without_dates,
    }


def test_read_ignores_the_reserved_build_directory(tmp_path: Path):
    # A migrated layout: the build directory is docs/_quarto/default/, nested two
    # levels below the section source, so a direct-child comparison never sees it.
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    config_path = docs_dir / "great-docs.yml"
    config_path.write_text("sections:\n  - title: Notes\n    dir: .\n")
    layout = Layout.make(tmp_path, config_path)
    leftover = layout.build_dir / "reference/other.qmd"
    leftover.parent.mkdir(parents=True)
    leftover.write_text("# Leftover\n")
    (docs_dir / "notes.md").write_text("# Notes\n")
    config = Config(layout.package_root, config_path=layout.config_path)

    [section] = sections.read(config, layout, report=print)

    assert layout.build_dir == docs_dir / "_quarto/default"
    assert section.files == (docs_dir / "notes.md",)


def test_read_reports_each_skipped_entry(tmp_path: Path):
    (tmp_path / "empty").mkdir()
    config = write_config(
        tmp_path,
        "sections:\n"
        "  - examples\n"
        "  - title: Untitled\n"
        "  - title: Missing\n    dir: missing\n"
        "  - title: Empty\n    dir: empty\n",
    )
    reports: list[str] = []

    assert sections.read(config, Layout.make(tmp_path), report=reports.append) == []
    assert reports == [
        "Section entry must be a dict, skipping: examples",
        "Section missing 'title' or 'dir', skipping: {'title': 'Untitled'}",
        "Section directory 'missing' not found, skipping",
        "Section 'Empty' directory 'empty' has no .qmd/.md files",
    ]


def test_copy_pages_strips_numeric_prefixes_from_paths_and_links(tmp_path: Path):
    # Published page paths are resolved, so the expected paths must be resolved too
    project = tmp_path.resolve()
    source_dir = project / "examples"
    (source_dir / "01-topic-a").mkdir(parents=True)
    (source_dir / "02-topic-b").mkdir()
    intro = source_dir / "01-topic-a" / "intro.qmd"
    intro.write_text(
        "---\ntitle: Intro\n---\n\nSee [demo](../02-topic-b/widget_demo.qmd) for details.\n"
    )
    widget = source_dir / "02-topic-b" / "widget_demo.qmd"
    widget.write_text("---\ntitle: Widget Demo\n---\n\nDemo content\n")
    dest_dir = project / "great-docs" / "examples"
    # Declare the section so its links resolve to the configured published paths
    write_config(project, {"sections": [{"title": "Examples", "dir": "examples"}]})

    copied = sections.copy_pages([intro, widget], source_dir, dest_dir, **_copying(project))

    assert [page["filename"] for page in copied] == ["topic-a/intro.qmd", "topic-b/widget_demo.qmd"]
    assert (dest_dir / "topic-b" / "widget_demo.qmd").exists()
    assert not (dest_dir / "01-topic-a").exists()
    intro_content = (dest_dir / "topic-a" / "intro.qmd").read_text()
    assert "../topic-b/widget_demo.qmd" in intro_content
    assert "02-topic-b" not in intro_content


def test_copy_pages_reads_titles_descriptions_and_images(tmp_path: Path):
    source_dir = tmp_path / "recipes"
    source_dir.mkdir()
    page = source_dir / "01-first.qmd"
    page.write_text(
        "---\ntitle: First Recipe\ndescription: A recipe\nimage: first.png\n---\n\n# First\n"
    )

    copied = sections.copy_pages([page], source_dir, tmp_path / "out", **_copying(tmp_path))

    assert copied == [
        {
            "filename": "first.qmd",
            "title": "First Recipe",
            "description": "A recipe",
            "image": "first.png",
        }
    ]
    assert "bread-crumbs: false" in (tmp_path / "out" / "first.qmd").read_text()


def test_copy_pages_hides_breadcrumbs_of_a_page_without_front_matter(tmp_path: Path):
    source_dir = tmp_path / "sec"
    source_dir.mkdir()
    (source_dir / "02-raw.qmd").write_text("Just regular content\n")

    copied = sections.copy_pages(
        [source_dir / "02-raw.qmd"], source_dir, tmp_path / "out", **_copying(tmp_path)
    )

    assert copied[0]["title"] == "Raw"
    assert copied[0]["description"] == ""
    assert (tmp_path / "out" / "raw.qmd").read_text() == (
        "---\nbread-crumbs: false\n---\n\nJust regular content\n"
    )


def test_copy_pages_copies_a_page_with_malformed_front_matter(tmp_path: Path):
    source_dir = tmp_path / "recipes"
    source_dir.mkdir()
    (source_dir / "01-bad.qmd").write_text("---\n: invalid yaml [\n---\nContent here.\n")

    copied = sections.copy_pages(
        [source_dir / "01-bad.qmd"], source_dir, tmp_path / "out", **_copying(tmp_path)
    )

    assert copied[0]["title"] == "Bad"
    assert (tmp_path / "out" / "bad.qmd").exists()


def test_section_and_blog_fallback_titles_treat_underscores_as_spaces(tmp_path: Path):
    source_dir = tmp_path / "sec"
    source_dir.mkdir()
    page = source_dir / "03-my_file.qmd"
    page.write_text("Body\n")

    section = sections.copy_pages([page], source_dir, tmp_path / "section", **_copying(tmp_path))
    blog = sections.copy_posts([page], source_dir, tmp_path / "blog", **_copying(tmp_path))

    assert section[0]["title"] == "My File"
    assert blog[0]["title"] == "03 My File"


def test_copy_posts_keeps_paths_and_front_matter(tmp_path: Path):
    source_dir = tmp_path / "blog"
    (source_dir / "2024" / "post-1").mkdir(parents=True)
    content = "---\ntitle: My Post\ndescription: About stuff\n---\nBody text\n"
    (source_dir / "my-post.qmd").write_text(content)
    (source_dir / "2024" / "post-1" / "index.qmd").write_text("Nested\n")
    files = [source_dir / "my-post.qmd", source_dir / "2024" / "post-1" / "index.qmd"]

    copied = sections.copy_posts(files, source_dir, tmp_path / "out", **_copying(tmp_path))

    assert copied == [
        {"filename": "my-post.qmd", "title": "My Post", "description": "About stuff"},
        {"filename": "2024/post-1/index.qmd", "title": "Index", "description": ""},
    ]
    assert (tmp_path / "out" / "my-post.qmd").read_text() == content
    assert (tmp_path / "out" / "2024" / "post-1" / "index.qmd").read_text() == "Nested\n"


def test_copy_posts_titles_a_post_with_malformed_front_matter_by_its_name(tmp_path: Path):
    source_dir = tmp_path / "blog"
    source_dir.mkdir()
    (source_dir / "bad.qmd").write_text("---\n: [invalid yaml\n---\nBody\n")

    copied = sections.copy_posts(
        [source_dir / "bad.qmd"], source_dir, tmp_path / "out", **_copying(tmp_path)
    )

    assert copied[0]["title"] == "Bad"


def test_copy_posts_copies_files_and_asset_directories_beside_posts(tmp_path: Path):
    source_dir = tmp_path / "blog"
    (source_dir / "datasets").mkdir(parents=True)
    (source_dir / "post.qmd").write_text("---\ntitle: Post\n---\nHello\n")
    (source_dir / "image.png").write_bytes(b"\x89PNG")
    (source_dir / "datasets" / "data.csv").write_text("a,b\n1,2\n")

    sections.copy_posts(
        [source_dir / "post.qmd"], source_dir, tmp_path / "out", **_copying(tmp_path)
    )

    assert (tmp_path / "out" / "image.png").read_bytes() == b"\x89PNG"
    assert (tmp_path / "out" / "datasets" / "data.csv").exists()


def test_blog_index_lists_posts_newest_first():
    content = sections.blog_index("My Blog")

    assert content.startswith('---\ntitle: "My Blog"\nlisting:\n')
    assert 'sort: "date desc"' in content
    assert "bread-crumbs: false" in content
    assert "body-classes: gd-blog-index" in content


def test_card_index_lists_each_page_but_the_index():
    pages: list[sections.Page] = [
        {"filename": "index.qmd", "title": "Index", "description": ""},
        {"filename": "intro.qmd", "title": "Intro", "description": "Getting started"},
        {"filename": "advanced.qmd", "title": "Advanced", "description": ""},
    ]

    content = sections.card_index("Recipes", pages)

    assert content.startswith('---\ntitle: "Recipes"\nbread-crumbs: false\n---\n')
    assert 'href="intro.qmd"' in content
    assert "Getting started" in content
    assert 'href="advanced.qmd"' in content
    assert 'href="index.qmd"' not in content
    assert content.count("section-card-desc") == 1


def test_card_index_without_pages():
    assert "*No pages found.*" in sections.card_index("Empty", [])


def test_card_index_puts_image_cards_before_plain_cards():
    pages: list[sections.Page] = [
        {"filename": "plain.qmd", "title": "Plain", "description": "No image", "image": ""},
        {"filename": "featured.qmd", "title": "Featured", "description": "", "image": "hero.png"},
        {"filename": "also-plain.qmd", "title": "Also Plain", "description": "Text only"},
    ]

    content = sections.card_index("Mixed", pages)

    assert content.count("<img") == 1
    assert 'src="hero.png"' in content
    assert (
        content.index("section-cards-2col")
        < content.index("<hr>")
        < content.index("section-cards-list")
    )
    assert content.index("Plain") < content.index("Also Plain")


def test_card_index_with_one_column_of_image_cards():
    pages: list[sections.Page] = [
        {"filename": "a.qmd", "title": "A", "description": "", "image": "a.png"},
        {"filename": "b.qmd", "title": "B", "description": "", "image": "b.png"},
    ]

    content = sections.card_index("Gallery", pages, columns=1)

    assert "section-cards-1col" in content
    assert "section-cards-2col" not in content
    assert "section-cards-list" not in content
    assert "<hr>" not in content


def test_card_index_without_images_has_only_plain_cards():
    pages: list[sections.Page] = [
        {"filename": "a.qmd", "title": "A", "description": "Desc A"},
    ]

    content = sections.card_index("Docs", pages)

    assert "section-cards-list" in content
    assert "section-cards-2col" not in content
    assert "<hr>" not in content
    assert "<img" not in content


@pytest.mark.parametrize("index", [sections.blog_index, partial(sections.card_index, pages=[])])
@pytest.mark.parametrize("title", ['Say "hi"', "C:\\temp", "Été: notes"])
def test_generated_index_keeps_the_title(index: Callable[[str], str], title: str):
    front_matter, _ = split_front_matter(index(title))

    assert front_matter.string("title") == title


def test_card_index_escapes_page_values():
    pages: list[sections.Page] = [
        {
            "filename": 'say-"hi".qmd',
            "title": "A < B & C",
            "description": "Use <b> & 'quotes'",
            "image": 'a"b.png',
        },
    ]

    content = sections.card_index("Cards", pages)

    assert 'href="say-&quot;hi&quot;.qmd"' in content
    assert 'src="a&quot;b.png"' in content
    assert ">A &lt; B &amp; C</div>" in content
    assert ">Use &lt;b&gt; &amp; 'quotes'</div>" in content


def _page(filename: str, title: str) -> sections.Page:
    return {"filename": filename, "title": title, "description": ""}


def test_sidebar_starts_with_the_index():
    pages = [_page("page1.qmd", "Page 1"), _page("page2.qmd", "Page 2")]

    result = sections.sidebar("Recipes", "recipes", pages, has_index=True)

    assert result == {
        "id": "recipes",
        "title": "Recipes",
        "contents": [
            {"text": "Recipes", "href": "recipes/index.qmd"},
            {"text": "Page 1", "href": "recipes/page1.qmd"},
            {"text": "Page 2", "href": "recipes/page2.qmd"},
        ],
    }


def test_sidebar_is_omitted_for_a_single_item():
    pages = [_page("only.qmd", "Only")]

    assert sections.sidebar("Solo", "solo", pages, has_index=False) is None


def test_sidebar_groups_subdirectories_in_source_order():
    # Numeric prefixes are stripped before this point, so the pages arrive in source
    # order with clean names that do not sort alphabetically.
    pages = [
        _page("top.qmd", "Top"),
        _page("foundations/page.qmd", "Foundations Page"),
        _page("effect-estimation/page.qmd", "Effect Page"),
        _page("applied-models/page.qmd", "Applied Page"),
    ]

    result = sections.sidebar("Examples", "examples", pages, has_index=False)

    assert result is not None
    assert [item.get("section", item.get("text")) for item in result["contents"]] == [
        "Top",
        "Foundations",
        "Effect Estimation",
        "Applied Models",
    ]
    assert result["contents"][1]["contents"] == [
        {"text": "Foundations Page", "href": "examples/foundations/page.qmd"}
    ]


def test_sidebar_titles_subdirectories_without_prefixes_or_by_dir_titles():
    pages = [
        _page("01-getting-started/install.qmd", "Install"),
        _page("02-results-and-reporting/report.qmd", "Report"),
        _page("03-advanced/config.qmd", "Config"),
    ]
    dir_titles = {"results-and-reporting": "Results/Reporting"}

    result = sections.sidebar("Demos", "demos", pages, has_index=True, dir_titles=dir_titles)

    assert result is not None
    assert [item["section"] for item in result["contents"][1:]] == [
        "Getting Started",
        "Results/Reporting",
        "Advanced",
    ]


def test_sidebar_follows_sidebar_groups_then_lists_ungrouped_pages():
    pages = [
        _page("intro.qmd", "Introduction"),
        _page("extra.qmd", "Extra"),
        _page("advanced.qmd", "Advanced"),
    ]
    sidebar_groups = [
        {"section": "Getting Started", "contents": ["intro.qmd", "missing.qmd"]},
        {"section": "Deep Dive", "contents": ["advanced.qmd"]},
        {"section": "Empty", "contents": ["missing.qmd"]},
    ]

    result = sections.sidebar(
        "Recipes", "recipes", pages, has_index=False, sidebar_groups=sidebar_groups
    )

    assert result is not None
    assert result["contents"] == [
        {
            "section": "Getting Started",
            "contents": [{"text": "Introduction", "href": "recipes/intro.qmd"}],
        },
        {
            "section": "Deep Dive",
            "contents": [{"text": "Advanced", "href": "recipes/advanced.qmd"}],
        },
        {"text": "Extra", "href": "recipes/extra.qmd"},
    ]


def test_publish_gives_a_sidebar_to_pages_in_one_subdirectory(tmp_path: Path):
    project = tmp_path.resolve()
    subdirectory = project / "examples" / "01-basics"
    subdirectory.mkdir(parents=True)
    (subdirectory / "first.qmd").write_text("---\ntitle: First\n---\n")
    (subdirectory / "second.qmd").write_text("---\ntitle: Second\n---\n")
    config = write_config(project, {"sections": [{"title": "Examples", "dir": "examples"}]})
    layout = Layout.make(project)
    [section] = sections.read(config, layout, report=print)
    section.destination.mkdir(parents=True)

    published = sections.publish(
        section,
        config=config,
        layout=layout,
        pages=PageMap.make(config, layout, None, []),
        add_dates=_without_dates,
    )

    assert published.sidebar is not None
    assert published.sidebar["contents"] == [
        {
            "section": "Basics",
            "contents": [
                {"text": "First", "href": "examples/basics/first.qmd"},
                {"text": "Second", "href": "examples/basics/second.qmd"},
            ],
        }
    ]
    first = (section.destination / "basics" / "first.qmd").read_text()
    assert "gd-section-no-sidebar" not in first


def _no_sidebar(dest_dir: Path, content: str) -> str:
    (dest_dir / "page.qmd").write_text(content)
    sections.add_no_sidebar_class([_page("page.qmd", "Page")], dest_dir)
    return (dest_dir / "page.qmd").read_text()


def test_add_no_sidebar_class_adds_the_class(tmp_path: Path):
    content = _no_sidebar(tmp_path, "---\ntitle: Page\n---\nContent\n")

    front_matter, body = split_front_matter(content)
    assert front_matter.string("body-classes") == "gd-section-no-sidebar"
    assert body == "Content\n"


def test_add_no_sidebar_class_joins_existing_classes(tmp_path: Path):
    content = _no_sidebar(tmp_path, "---\nbody-classes: [wide, dark]\n---\nContent\n")

    front_matter, _ = split_front_matter(content)
    assert front_matter.string("body-classes") == "wide dark gd-section-no-sidebar"


def test_add_no_sidebar_class_adds_the_class_once(tmp_path: Path):
    original = "---\ntitle: Page\nbody-classes: gd-section-no-sidebar\n---\nContent\n"

    assert _no_sidebar(tmp_path, original) == original


def test_add_no_sidebar_class_skips_pages_without_front_matter(tmp_path: Path):
    assert _no_sidebar(tmp_path, "No front matter here\n") == "No front matter here\n"


def test_add_no_sidebar_class_survives_missing_pages_and_malformed_front_matter(tmp_path: Path):
    (tmp_path / "bad.qmd").write_text("---\n: invalid yaml: [unclosed\n---\nContent\n")

    sections.add_no_sidebar_class(
        [_page("bad.qmd", "Bad"), _page("missing.qmd", "Missing")], tmp_path
    )

    assert not (tmp_path / "missing.qmd").exists()
