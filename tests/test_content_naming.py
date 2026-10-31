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


def test_fix_numeric_prefix_links_basic():
    assert (
        fix_numeric_prefix_links("[Config](05-configuration.qmd)") == "[Config](configuration.qmd)"
    )


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
