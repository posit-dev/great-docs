"""
Search descriptions and social card options in page front matter
"""

from __future__ import annotations

from pathlib import Path

import pytest
from yaml12 import parse_yaml

from great_docs._website import head, social_cards
from great_docs._website.page_metadata import Page, add_to_page, write_to_pages
from great_docs._website.seo.structured_data import StructuredData
from great_docs._yaml import split_front_matter
from great_docs.config import Config
from tests.support import write_config

LONG = "This sentence is comfortably longer than thirty characters."
SITE = {"website": {"title": "Pkg"}}


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _front_matter(path: Path) -> dict:
    front_matter, _ = split_front_matter(path.read_text(encoding="utf-8"))
    return dict(front_matter.data)


def test_add_to_page_keeps_the_author_front_matter():
    content = "---\ntitle: A  # a comment\n---\n\nBody\n"
    assert add_to_page(content, {"description-meta": "Desc"}) == (
        "---\ndescription-meta: Desc\ntitle: A  # a comment\n---\n\nBody\n"
    )


def test_add_to_page_joins_front_matter_with_a_padded_opening_line():
    content = "--- \ntitle: A\n---\n\nBody\n"
    assert add_to_page(content, {"description-meta": "Desc"}) == (
        "---\ndescription-meta: Desc\ntitle: A\n---\n\nBody\n"
    )


def test_add_to_page_creates_front_matter():
    assert add_to_page("Body\n", {"description-meta": "Desc"}) == (
        "---\ndescription-meta: Desc\n---\n\nBody\n"
    )


def test_add_to_page_quotes_yaml():
    entries = {"description-meta": "Colon: and \\*star", "open-graph": {"title": "A: B"}}
    front_matter, _ = split_front_matter(add_to_page("Body\n", entries))
    assert front_matter.data == entries


def test_page_reads_front_matter_and_output_path(tmp_path: Path) -> None:
    index = _write(tmp_path, "reference/index.qmd", "---\ntitle: R\n---\n\nBody\n")
    guide = _write(tmp_path, "guide.md", "Guide\n")

    page = Page.make(index, tmp_path)
    assert (page.output_path, page.front_matter.data, page.body) == (
        "reference/index.html",
        {"title": "R"},
        "\nBody\n",
    )
    page = Page.make(guide, tmp_path)
    assert (page.output_path, page.front_matter.data, page.body) == ("guide.html", {}, "Guide\n")


def test_writes_only_pages_quarto_renders(tmp_path: Path):
    config = write_config(tmp_path, "social_cards: false\n")
    site = tmp_path / "site"
    prose = _write(site, "user-guide/intro.qmd", f"---\ntitle: Intro\n---\n\n{LONG}\n")
    code = _write(site, "notes.md", "```\ncode\n```\n")
    own = _write(site, "own.qmd", f"---\ndescription: Own\n---\n\n{LONG}\n")
    partial = _write(site, "_partial.qmd", f"{LONG}\n")
    hidden = _write(site, "_site/page.md", f"{LONG}\n")
    skill = _write(site, "skill.md", f"{LONG}\n")
    quarto_config = {"project": {"render": ["*.qmd", "*.md", "!skill.md"]}}

    changed = write_to_pages(site, quarto_config, config, "Site default")

    assert sorted(changed) == sorted([prose, code])
    assert _front_matter(prose)["description-meta"] == LONG
    assert _front_matter(code)["description-meta"] == "Site default"
    for untouched in (own, partial, hidden, skill):
        assert "description-meta" not in untouched.read_text()


def test_defers_to_a_header_description(tmp_path: Path):
    config = write_config(tmp_path, "social_cards: false\n")
    page = _write(tmp_path, "page.qmd", f"{LONG}\n")
    quarto_config = {
        "format": {
            "html": {"include-in-header": [{"text": '<meta name="description" content="x">'}]}
        }
    }

    assert write_to_pages(tmp_path, quarto_config, config, "Site default") == []
    assert "description-meta" not in page.read_text()


def test_cards_match_the_title_and_description(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", f"---\ntitle: Intro\n---\n\n{LONG}\n")

    write_to_pages(tmp_path, SITE, write_config(tmp_path), "Site default")

    card = {"title": "Intro | Pkg", "description": LONG}
    assert _front_matter(page) == {
        "description-meta": LONG,
        "open-graph": card,
        "twitter-card": card,
        "title": "Intro",
    }


def test_cards_without_seo(tmp_path: Path):
    """
    Keep Quarto's matching card and page titles when SEO is disabled
    """
    page = _write(tmp_path, "page.qmd", f"---\ntitle: Intro\n---\n\n{LONG}\n")

    write_to_pages(tmp_path, SITE, write_config(tmp_path, "seo:\n  enabled: false\n"), None)

    front_matter = _front_matter(page)
    assert "description-meta" not in front_matter
    assert front_matter["open-graph"] == {"description": LONG}


def test_cards_reuse_a_written_description_meta(tmp_path: Path):
    page = _write(
        tmp_path, "ref.qmd", f"---\ntitle: f\ndescription-meta: From docstring\n---\n\n{LONG}\n"
    )

    write_to_pages(tmp_path, SITE, write_config(tmp_path), "Site default")

    assert _front_matter(page)["open-graph"]["description"] == "From docstring"


def test_cards_leave_a_page_description_to_quarto(tmp_path: Path):
    page = _write(tmp_path, "own.qmd", f"---\ntitle: Own\ndescription: Mine\n---\n\n{LONG}\n")

    write_to_pages(tmp_path, SITE, write_config(tmp_path), "Site default")

    assert _front_matter(page)["open-graph"] == {"title": "Own | Pkg"}


@pytest.mark.parametrize("key", social_cards.PAGE_KEYS)
@pytest.mark.parametrize("value", ["true", "\n  title: Mine"])
def test_cards_leave_pages_that_set_their_own(tmp_path: Path, key: str, value: str):
    page = _write(tmp_path, "page.qmd", f"---\ntitle: Intro\n{key}: {value}\n---\n\n{LONG}\n")

    write_to_pages(tmp_path, SITE, write_config(tmp_path), "Site default")

    front_matter = _front_matter(page)
    assert front_matter["description-meta"] == LONG
    assert all(k not in front_matter or k == key for k in social_cards.PAGE_KEYS)


def test_cards_on_untitled_pages(tmp_path: Path):
    """
    Use the site name for both card and page titles on untitled pages
    """
    page = _write(tmp_path, "index.qmd", f"{LONG}\n")

    write_to_pages(tmp_path, SITE, write_config(tmp_path), None)

    assert _front_matter(page)["open-graph"] == {"description": LONG}


@pytest.mark.parametrize("seo", ["true", "false"])
def test_cards_on_pages_with_an_empty_title(tmp_path: Path, seo: str):
    """
    Use the site name without Quarto's leading dash for an empty title
    """
    page = _write(tmp_path, "index.qmd", f'---\ntitle: ""\n---\n\n{LONG}\n')

    write_to_pages(tmp_path, SITE, write_config(tmp_path, f"seo:\n  enabled: {seo}\n"), None)

    assert _front_matter(page)["open-graph"]["title"] == "Pkg"


def test_cards_with_an_invalid_template(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", f"---\ntitle: Intro\n---\n\n{LONG}\n")
    config = write_config(tmp_path, "seo:\n  title_template: '{site_name} only'\n")

    write_to_pages(tmp_path, SITE, config, None)

    assert "title" not in _front_matter(page)["open-graph"]


def test_cards_escape_the_template_and_site_name(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", "---\ntitle: '`f` *now*'\n---\n\nShort.\n")
    config = write_config(tmp_path, "seo:\n  title_template: '{page_title} @ {site_name}'\n")

    write_to_pages(tmp_path, {"website": {"title": "my_pkg"}}, config, None)

    assert _front_matter(page)["open-graph"] == {"title": "`f` *now* \\@ my\\_pkg"}


def test_cards_use_the_title_of_the_site_being_rendered(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", "---\ntitle: Intro\n---\n\nShort.\n")
    quarto_config = {"website": {"title": "Pkg (0.1)"}}

    write_to_pages(tmp_path, quarto_config, write_config(tmp_path), None)

    assert _front_matter(page)["open-graph"] == {"title": "Intro | Pkg (0.1)"}


def test_cards_defer_to_header_open_graph_tags(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", f"---\ntitle: Intro\n---\n\n{LONG}\n")
    tag = '<meta property="og:title" content="Mine">'
    quarto_config = {**SITE, "format": {"html": {"include-in-header": [{"text": tag}]}}}

    write_to_pages(tmp_path, quarto_config, write_config(tmp_path), None)

    assert "open-graph" not in _front_matter(page)


def test_nothing_without_seo_or_cards(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", f"{LONG}\n")
    config = write_config(tmp_path, "seo:\n  enabled: false\nsocial_cards: false\n")

    assert write_to_pages(tmp_path, SITE, config, "Site default") == []
    assert page.read_text() == f"{LONG}\n"


def test_written_front_matter_parses(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", "---\ntitle: 'A: B'\n---\n\nShort.\n")

    write_to_pages(tmp_path, SITE, write_config(tmp_path), "Default: text")

    front_matter = parse_yaml(page.read_text().split("---")[1])
    assert front_matter["open-graph"]["title"] == "A: B | Pkg"


@pytest.mark.parametrize(
    "include",
    [
        'include-in-header:\n  text: \'<meta property="og:title" content="Mine">\'',
        'header-includes: |\n  <meta property="og:title" content="Mine">',
        "include-in-header: head.html",
    ],
)
def test_cards_off_for_pages_with_their_own_tags(tmp_path: Path, include: str):
    """Switch off generated tags, which Quarto would add beside the page's own"""
    (tmp_path / "guide").mkdir()
    (tmp_path / "guide" / "head.html").write_text('<meta property="og:title" content="Mine">')
    page = _write(tmp_path, "guide/page.qmd", f"---\ntitle: Intro\n{include}\n---\n\n{LONG}\n")

    write_to_pages(tmp_path, SITE, write_config(tmp_path), None)

    front_matter = _front_matter(page)
    assert front_matter["website"] == {"open-graph": False, "twitter-card": False}
    assert front_matter[social_cards.OWN_CARDS_KEY] is True
    assert "open-graph" not in front_matter


def test_cards_reuse_a_header_description(tmp_path: Path):
    page = _write(tmp_path, "page.qmd", f"---\ntitle: Intro\n---\n\n{LONG}\n")
    tag = '<meta name="description" content="From the header &amp; *more*">'
    quarto_config = {**SITE, "format": {"html": {"include-in-header": [{"text": tag}]}}}

    write_to_pages(tmp_path, quarto_config, write_config(tmp_path), None)

    front_matter = _front_matter(page)
    assert "description-meta" not in front_matter
    assert front_matter["open-graph"]["description"] == "From the header & \\*more\\*"


def test_scale_to_fit_tag_from_directory_metadata(tmp_path: Path) -> None:
    config = write_config(tmp_path, "seo:\n  enabled: false\nsocial_cards: false\n")
    _write(tmp_path, "guide/_metadata.yml", 'scale-to-fit: [".wide"]\n')
    guide = _write(tmp_path, "guide/a.md", f"{LONG}\n")
    other = _write(tmp_path, "other/b.qmd", f"---\ntitle: B\n---\n\n{LONG}\n")

    assert write_to_pages(tmp_path, SITE, config, None) == [guide]
    assert _front_matter(guide)[head.HEAD_TAGS] == [
        '`<meta name="gd-scale-to-fit-page" data-selectors="[&quot;.wide&quot;]">`{=html}'
    ]
    assert other.read_text() == f"---\ntitle: B\n---\n\n{LONG}\n"


def _structured_data(tmp_path: Path) -> StructuredData:
    (tmp_path / "data").mkdir(exist_ok=True)
    data = StructuredData.make(write_config(tmp_path / "data"), {"description": "Pkg"}, "Pkg", None)
    assert data is not None
    return data


def _json_ld(path: Path) -> list[str]:
    tags = _front_matter(path).get(head.HEAD_TAGS, [])
    return [tag for tag in tags if "application/ld+json" in tag]


@pytest.fixture
def json_ld_config(tmp_path: Path) -> Config:
    return write_config(tmp_path, "seo:\n  enabled: false\nsocial_cards: false\n")


def test_json_ld_on_the_homepage_and_reference_pages(
    tmp_path: Path, json_ld_config: Config
) -> None:
    index = _write(tmp_path, "index.qmd", "Home\n")
    reference = _write(tmp_path, "reference/foo.qmd", "Foo\n")
    guide = _write(tmp_path, "user-guide/intro.qmd", "Intro\n")

    write_to_pages(tmp_path, SITE, json_ld_config, None, _structured_data(tmp_path))

    assert len(_json_ld(index)) == len(_json_ld(reference)) == 1
    assert _json_ld(guide) == []


def test_json_ld_follows_existing_head_tags(tmp_path: Path, json_ld_config: Config) -> None:
    first = '<meta name="a" content="b">'
    index = _write(tmp_path, "index.qmd", head.add_tags("Home\n", [first]))

    write_to_pages(tmp_path, SITE, json_ld_config, None, _structured_data(tmp_path))

    tags = _front_matter(index)[head.HEAD_TAGS]
    assert len(tags) == 2
    assert first in tags[0]
    assert "application/ld+json" in tags[1]


def test_no_json_ld_on_a_page_with_its_own(tmp_path: Path, json_ld_config: Config) -> None:
    text = '```{=html}\n<script type="application/ld+json">{}</script>\n```\n'
    index = _write(tmp_path, "index.qmd", text)

    assert write_to_pages(tmp_path, SITE, json_ld_config, None, _structured_data(tmp_path)) == []
    assert index.read_text() == text


def test_no_json_ld_when_the_site_header_has_it(tmp_path: Path, json_ld_config: Config) -> None:
    _write(tmp_path, "index.qmd", "Home\n")
    _write(tmp_path, "reference/foo.qmd", "Foo\n")
    include = {"text": '<script type="application/ld+json">{}</script>'}
    quarto_config = {**SITE, "format": {"html": {"include-in-header": [include]}}}

    assert (
        write_to_pages(tmp_path, quarto_config, json_ld_config, None, _structured_data(tmp_path))
        == []
    )


def test_json_ld_written_once(tmp_path: Path, json_ld_config: Config) -> None:
    index = _write(tmp_path, "index.qmd", "---\ntitle: Home\n---\n\nHome\n")
    data = _structured_data(tmp_path)

    write_to_pages(tmp_path, SITE, json_ld_config, None, data)
    first = index.read_text()
    assert write_to_pages(tmp_path, SITE, json_ld_config, None, data) == []
    assert index.read_text() == first
