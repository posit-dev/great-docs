from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from great_docs._website.seo import description
from great_docs._website.seo.description import (
    FirstParagraph,
    add_to_raw_page,
    as_metadata,
    default_description,
    first_paragraph,
    metadata_value,
    page_description,
    plain_text,
)
from great_docs._yaml import YamlMapping, split_front_matter

LONG = "This sentence is comfortably longer than thirty characters."


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("Return the `sum` of values", "Return the sum of values"),
        ("See [the guide](guide.qmd) now", "See the guide now"),
        ("Calls [](`~pkg.mod.func`) first", "Calls func first"),
        ("Calls [](`pkg.mod.func`) first", "Calls pkg.mod.func first"),
        ("A [styled]{.lead} word", "A styled word"),
        ("Very **bold** and *soft* and __also__ _this_", "Very bold and soft and also this"),
        ("Keep read_csv and 2 * 3", "Keep read_csv and 2 * 3"),
        ("Drop <tags> and ![logo](logo.png) here", "Drop tags and here"),
        ("Tom \\& Jerry \\*literal\\*", "Tom & Jerry *literal*"),
        ("  spread\n   over   lines ", "spread over lines"),
        ("![only an image](a.png)", None),
        ("Introduced by Knuth [@knuth1984], who argued", "Introduced by Knuth, who argued"),
        ("As shown [see @parnas1972, p. 3; @knuth1984].", "As shown."),
        ("Keep `[@key]` and [mail](mailto:a@b.org)", "Keep [@key] and mail"),
        ("Escaped \\[\\@key\\] stays", "Escaped [@key] stays"),
    ],
)
def test_plain_text(markdown: str, expected: str | None):
    assert plain_text(markdown) == expected


def test_plain_text_truncates_at_a_word_boundary():
    text = plain_text("word " * 60)
    assert text is not None
    assert len(text) <= description.MAX_LENGTH
    assert text.endswith("word...")


def test_as_metadata_escapes_markdown_syntax():
    # Quarto parses `description-meta` as Markdown, so each of these would
    # otherwise become emphasis, math, a citation or a subscript in the tag
    assert as_metadata("a*b* $x$ @c H~2~O x^2^ [l] `c` d_e \\") == (
        "a\\*b\\* \\$x\\$ \\@c H\\~2\\~O x\\^2\\^ \\[l\\] \\`c\\` d\\_e \\\\"
    )


def test_metadata_value():
    assert metadata_value("Return the `sum`") == "Return the sum"
    assert metadata_value("") is None
    assert metadata_value(None) is None


@pytest.mark.parametrize(
    "body",
    [
        f"{LONG}\n",
        f"# Title\n\n## Subtitle\n\n{LONG}\n",
        f"Title\n=====\n\n{LONG}\n",
        f"<!-- A comment\nover two lines -->\n\n{LONG}\n",
    ],
)
def test_first_paragraph_after_headings_and_comments(body: str):
    assert first_paragraph(body) == FirstParagraph(text=LONG)


def test_first_paragraph_joins_lines():
    body = "This paragraph is written\nacross two separate lines.\n\nSecond paragraph."
    assert first_paragraph(body).text == "This paragraph is written across two separate lines."


@pytest.mark.parametrize(
    ("body", "fallback"),
    [
        (f"```{{python}}\nx = 1\n```\n\n{LONG}", "starts with a code block"),
        (f"~~~\nx = 1\n~~~\n\n{LONG}", "starts with a code block"),
        (f"    x = 1\n\n{LONG}", "starts with a code block"),
        (f"::: {{.callout-note}}\n{LONG}\n:::", "starts with a callout or other fenced div"),
        (f"![Logo](logo.png)\n\n{LONG}", "starts with an image"),
        (f"- one\n- two\n\n{LONG}", "starts with a list"),
        (f"1. one\n\n{LONG}", "starts with a list"),
        (f"| a | b |\n|---|---|\n\n{LONG}", "starts with a table"),
        (f"<div>\n</div>\n\n{LONG}", "starts with an HTML block"),
        (f"{{{{< include _intro.qmd >}}}}\n\n{LONG}", "starts with a shortcode"),
        (f"> quoted\n\n{LONG}", "starts with a block quote"),
        (f"$$\nx\n$$\n\n{LONG}", "starts with display math"),
        (f"Too short.\n\n{LONG}", "opens with a paragraph of 30 characters or fewer"),
        ("# Only a title\n", "has no content"),
        ("", "has no content"),
    ],
)
def test_first_paragraph_falls_back(body: str, fallback: str):
    assert first_paragraph(body) == FirstParagraph(fallback=fallback)


def test_first_paragraph_drops_bracketed_citations():
    assert first_paragraph(f"{LONG} [@knuth1984]\n") == FirstParagraph(text=LONG)


def test_first_paragraph_falls_back_on_an_in_text_citation():
    body = f"As @parnas1972 showed, {LONG}\n"
    assert first_paragraph(body, citations=True) == FirstParagraph(
        fallback="opens with a paragraph that cites a reference in its text"
    )
    # Without a bibliography, Quarto shows `@parnas1972` as written
    assert first_paragraph(body).text == f"As @parnas1972 showed, {LONG}"


@pytest.mark.parametrize(
    "paragraph",
    [
        "Write to team@example.org for help with the package.",
        "Follow https://example.org/@team for news about the package.",
        "Mention `@decorator` and \\@handle in the opening paragraph.",
        "See the [maintainer](https://example.org/@team) for the package.",
    ],
)
def test_first_paragraph_keeps_at_signs_that_are_not_citations(paragraph: str):
    assert first_paragraph(f"{paragraph}\n", citations=True).text is not None


@pytest.mark.parametrize(
    ("bibliography", "front_matter", "expected"),
    [
        ([], "", False),
        (["references.bib"], "", True),
        ([], "bibliography: page.bib\n", True),
        ([], "references:\n  - id: knuth1984\n", True),
    ],
)
def test_resolves_citations(bibliography: list[str], front_matter: str, expected: bool):
    config: Any = SimpleNamespace(bibliography=bibliography)
    parsed, _ = split_front_matter(f"---\n{front_matter}---\n\nText\n")
    assert description.resolves_citations(parsed, config) is expected


def _config(default: str | None = None) -> Any:
    return SimpleNamespace(seo_default_description=default)


def test_default_description_prefers_the_configured_value():
    assert default_description(_config("Configured `docs`"), "Package") == "Configured docs"
    assert default_description(_config(), "Package") == "Package"
    assert default_description(_config(), None) is None


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (f"---\ntitle: A\n---\n\n{LONG}\n", LONG),
        (f"---\ntitle: A\n---\n\n```\ncode\n```\n\n{LONG}\n", "Site default"),
        (f"{LONG}\n", LONG),
        (f"---\ndescription: Own\n---\n\n{LONG}\n", None),
        (f"---\ndescription-meta: Own\n---\n\n{LONG}\n", None),
    ],
)
def test_page_description(content: str, expected: str | None) -> None:
    front_matter, body = split_front_matter(content)
    assert page_description(front_matter, body, "Site default") == expected


def test_page_description_without_a_default() -> None:
    assert page_description(YamlMapping(), "```\ncode\n```\n", None) is None


def test_page_description_with_an_in_text_citation():
    body = f"As @parnas1972 showed, {LONG}\n"
    assert page_description(YamlMapping(), body, "Site default", citations=True) == "Site default"


def test_add_to_raw_page():
    page = "<html><head><title>T</title></head><body></body></html>"
    result = add_to_raw_page(page, 'Tom & "Jerry"')
    assert '<meta name="description" content="Tom &amp; &quot;Jerry&quot;">' in result
    assert add_to_raw_page(page, None) == page

    described = page.replace("</head>", '<meta name="description" content="x"></head>')
    assert add_to_raw_page(described, "Default") == described
