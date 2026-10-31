from pathlib import Path

import pytest

from great_docs._content.naming import (
    fix_numeric_prefix_links,
    published_path,
    section_slug,
    strip_numeric_prefix,
    title_from_name,
)


def test_strip_numeric_prefix_two_digit():
    assert strip_numeric_prefix("01-installation.qmd") == "installation.qmd"


def test_strip_numeric_prefix_no_prefix():
    assert strip_numeric_prefix("introduction.qmd") == "introduction.qmd"


@pytest.mark.parametrize(
    ("link", "fixed"),
    [
        ("[Theming](11-theming.qmd): colours", "[Theming](theming.qmd): colours"),
        ("[Config](05-configuration.qmd#options)", "[Config](configuration.qmd#options)"),
        ("[Config](05-configuration.qmd?v=2)", "[Config](configuration.qmd?v=2)"),
        ("[Guide](01-getting-started/02-install.qmd)", "[Guide](getting-started/install.qmd)"),
        ("[A](11-a.qmd) and [B](05_b.qmd)", "[A](a.qmd) and [B](b.qmd)"),
    ],
)
def test_links_to_missing_pages_lose_numeric_prefixes(tmp_path: Path, link: str, fixed: str):
    assert fix_numeric_prefix_links(link, tmp_path) == fixed


@pytest.mark.parametrize(
    "link",
    [
        "[Docs](https://example.com/11-theming.qmd)",
        "[Docs](http://example.com/05-config.qmd)",
        "[Docs](/root/11-theming.qmd)",
        "[Theming](theming.qmd)",
        "[Image](11-diagram.png)",
        "[Page](11-theming.html)",
    ],
)
def test_urls_and_links_to_other_files_are_left_alone(tmp_path: Path, link: str):
    assert fix_numeric_prefix_links(link, tmp_path) == link


def test_a_link_to_an_existing_page_keeps_its_prefixes(tmp_path: Path):
    post = tmp_path / "blog/2024-01-welcome/index.qmd"
    post.parent.mkdir(parents=True)
    post.write_text("# Welcome\n")
    link = "[Welcome](blog/2024-01-welcome/index.qmd#intro)"

    assert fix_numeric_prefix_links(link, tmp_path) == link


def test_section_slug_replaces_underscores_and_spaces():
    assert section_slug("My_Cool Dir") == "my-cool-dir"


@pytest.mark.parametrize(
    ("strip_prefix", "expected"),
    [(True, "basics/setup.qmd"), (False, "01-basics/02_setup.qmd")],
)
def test_published_path_strips_the_prefix_of_every_part(strip_prefix: bool, expected: str):
    relative = Path("01-basics/02_setup.qmd")

    assert published_path(relative, strip_prefix=strip_prefix) == Path(expected)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("my-cool_page", "My Cool Page"), ("01-introduction", "01 Introduction"), ("v1.2", "V1.2")],
)
def test_title_from_name_turns_separators_into_spaces(name: str, expected: str):
    assert title_from_name(name) == expected
