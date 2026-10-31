"""
Typed YAML access and page front matter parsing
"""

from __future__ import annotations

import pytest

from great_docs._yaml import (
    YamlMapping,
    locate_front_matter,
    set_front_matter_option,
    split_front_matter,
)

MAPPING = YamlMapping(
    {
        "text": "a",
        "on": True,
        "fraction": 0.5,
        "count": 3,
        "items": ["a", "b"],
        "mixed": ["a", 1],
        "nested": {"inner": {"leaf": "x"}},
        "empty": None,
    }
)


@pytest.mark.parametrize(
    ("method", "key", "expected"),
    [
        ("string", "text", "a"),
        ("string", "count", None),
        ("string", "missing", None),
        ("number", "fraction", 0.5),
        ("number", "count", 3),
        ("number", "on", None),
        ("number", "missing", None),
        ("strings", "items", ["a", "b"]),
        ("strings", "text", ["a"]),
        ("strings", "mixed", []),
        ("strings", "count", []),
        ("strings", "missing", []),
        ("sequence", "mixed", ["a", 1]),
        ("sequence", "text", []),
        ("sequence", "missing", []),
        ("entries", "items", ["a", "b"]),
        ("entries", "text", ["a"]),
        ("entries", "nested", [{"inner": {"leaf": "x"}}]),
        ("entries", "empty", []),
        ("entries", "missing", []),
    ],
)
def test_reads_a_value_of_the_expected_type(method: str, key: str, expected: object):
    """Verify that accessors accept matching types and treat other values as absent"""
    assert getattr(MAPPING, method)(key) == expected


def test_entries_drops_null_items():
    assert YamlMapping({"k": ["a", None, {"text": "b"}]}).entries("k") == ["a", {"text": "b"}]


def test_mapping_chains_through_nested_mappings():
    assert MAPPING.mapping("nested").mapping("inner").string("leaf") == "x"


@pytest.mark.parametrize("key", ["missing", "text", "items"])
def test_mapping_is_empty_for_a_missing_or_non_mapping_value(key: str):
    """Verify that missing or non-mapping values allow subsequent reads to return defaults"""
    assert MAPPING.mapping(key).mapping("inner").string("leaf") is None


def test_get_and_membership_see_any_value():
    assert MAPPING.get("mixed") == ["a", 1]
    assert MAPPING.get("missing") is None
    assert MAPPING.get("missing", "d") == "d"
    assert MAPPING.get("empty", "d") is None
    assert "empty" in MAPPING
    assert "missing" not in MAPPING
    assert MAPPING
    assert not YamlMapping()


@pytest.mark.parametrize(
    ("content", "front_matter", "body"),
    [
        ("---\ntitle: T\n---\nBody\n", {"title": "T"}, "Body\n"),
        ("---\ntitle: T\n---", {"title": "T"}, ""),
        ("--- \t\ntitle: T\n---\nBody\n", {"title": "T"}, "Body\n"),
        ("Body\n", {}, "Body\n"),
        ("\n---\ntitle: T\n---\nBody\n", {}, "\n---\ntitle: T\n---\nBody\n"),
        ("---\ntitle: T\nBody\n", {}, "---\ntitle: T\nBody\n"),
        ("---\ntitle: [\n---\nBody\n", {}, "Body\n"),
        ("---\n- a\n- b\n---\nBody\n", {}, "Body\n"),
        ("---\nnote: |\n  a --- b\n---\nBody --- end\n", {"note": "a --- b\n"}, "Body --- end\n"),
    ],
    ids=[
        "block",
        "ends-at-closing-line",
        "trailing-whitespace-on-opening-line",
        "none",
        "leading-blank-line",
        "unclosed",
        "invalid-yaml",
        "list-block",
        "dashes-inside-a-value",
    ],
)
def test_splits_front_matter_from_the_body(content: str, front_matter: dict, body: str):
    """
    Verify that front matter starts on the first line and requires a closing delimiter

    Leading blank lines mean the page has no front matter, as in Quarto. A
    closed block that is not a YAML mapping still ends at its closing line.
    """
    assert split_front_matter(content) == (YamlMapping(front_matter), body)


def test_locates_the_end_of_the_closing_line():
    content = "---\ntitle: T\n---\nBody\n"
    block = locate_front_matter(content)
    assert block is not None
    assert content[block.end :] == "Body\n"
    assert block.mapping.string("title") == "T"


def test_locates_nothing_without_a_closed_block():
    assert locate_front_matter("---\ntitle: T\n") is None
    assert locate_front_matter("Body\n") is None


@pytest.mark.parametrize(
    ("content", "key", "value", "expected"),
    [
        ("---\ntitle: T\n---\n\nBody\n", "toc", False, "---\ntitle: T\ntoc: false\n---\n\nBody\n"),
        ("---\ntoc: true\nx: 1\n---\nBody", "toc", False, "---\ntoc: false\nx: 1\n---\nBody"),
        ("# Body\n", "toc", True, "---\ntoc: true\n---\n\n# Body\n"),
        ("---\ntitle: T\n---\n", "depth", 3, "---\ntitle: T\ndepth: 3\n---\n"),
        ("---\ntitle: T\n---\n", "format", "html", '---\ntitle: T\nformat: "html"\n---\n'),
    ],
    ids=["appends", "replaces", "creates-block", "integer", "string"],
)
def test_sets_a_front_matter_option(content: str, key: str, value: bool | int | str, expected: str):
    assert set_front_matter_option(content, key, value) == expected


def test_setting_an_option_keeps_dashes_inside_a_value():
    content = "---\ntitle: A---B\n---\nBody\n"

    result = set_front_matter_option(content, "toc", False)

    assert result == "---\ntitle: A---B\ntoc: false\n---\nBody\n"
