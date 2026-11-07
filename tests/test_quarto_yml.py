import copy
from pathlib import Path
from typing import Any

import pytest
from yaml12 import parse_yaml

from great_docs import GreatDocs
from great_docs._content import user_guide
from great_docs._contribution import Contribution, InlineData, NavbarLink, Sidebar
from great_docs._utils import QUARTO_YML_HEADER, validate_build_dir
from great_docs._website import inline_data, quarto_yml
from great_docs._website.navigation import navbar
from tests.support import discover_user_guide, mock_config, user_guide_step, write_config

CONFIG = mock_config()
"""A configuration for contributions with language-independent placement"""


def test_write_adds_generated_header(tmp_path: Path):
    quarto_yml.write(tmp_path, {"project": {"type": "website"}})

    text = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")
    assert text.startswith(QUARTO_YML_HEADER)
    assert parse_yaml(text) == {"project": {"type": "website"}}


def test_write_puts_the_api_reference_last(tmp_path: Path):
    quarto_config = {
        "project": {"type": "website"},
        "api-reference": {"package": "pkg"},
        "format": {"html": {"theme": "flatly"}},
    }

    quarto_yml.write(tmp_path, quarto_config)

    assert list(quarto_yml.read(tmp_path)) == ["project", "format", "api-reference"]
    assert list(quarto_config) == ["project", "api-reference", "format"]


def test_write_initial_marks_build_directory_as_generated(tmp_path: Path):
    quarto_yml.write_initial(tmp_path)

    assert quarto_yml.read(tmp_path) == {
        "project": {"type": "website"},
        "format": {"html": {"theme": "flatly"}},
    }
    validate_build_dir(tmp_path)


def test_read_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        quarto_yml.read(tmp_path)


def test_read_empty_file(tmp_path: Path):
    (tmp_path / "_quarto.yml").write_text("", encoding="utf-8")

    assert quarto_yml.read(tmp_path) == {}


def test_edit_writes_on_clean_exit(tmp_path: Path):
    quarto_yml.write_initial(tmp_path)

    with quarto_yml.edit(tmp_path) as quarto_config:
        quarto_config["project"]["output-dir"] = "_site"

    assert quarto_yml.read(tmp_path)["project"]["output-dir"] == "_site"


def test_edit_leaves_file_unchanged_when_block_raises(tmp_path: Path):
    quarto_yml.write_initial(tmp_path)
    before = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")

    with pytest.raises(KeyError), quarto_yml.edit(tmp_path) as quarto_config:
        quarto_config["project"]["output-dir"] = "_site"
        raise KeyError("stop")

    assert (tmp_path / "_quarto.yml").read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        ("tooltips.js", ["tooltips.js"]),
        ({"file": "head.html"}, [{"file": "head.html"}]),
        (["a.js", "b.js"], ["a.js", "b.js"]),
    ],
    ids=["null", "string", "mapping", "list"],
)
def test_entries_stores_a_list_under_the_key(value: Any, expected: list[Any]):
    mapping = {"resources": value}

    items = quarto_yml.entries(mapping, "resources")
    items.append("added.js")

    assert mapping["resources"] == [*expected, "added.js"]


def test_entries_creates_a_missing_key():
    mapping: dict[str, Any] = {}

    assert quarto_yml.entries(mapping, "filters") == []
    assert mapping == {"filters": []}


def test_includes_creates_the_html_format():
    quarto_config: dict[str, Any] = {}

    quarto_yml.includes(quarto_config, "include-after-body").append({"text": "x"})

    assert quarto_config == {"format": {"html": {"include-after-body": [{"text": "x"}]}}}


def test_find_returns_the_first_entry_containing_the_marker():
    items = [{"text": "a.js"}, {"text": "tooltips.js"}, "tooltips.js"]

    assert quarto_yml.find(items, "tooltips") == 1
    assert quarto_yml.find(items, "missing") is None


def test_add_include_skips_an_entry_whose_marker_is_present():
    quarto_config = {"format": {"html": {"include-after-body": ['<script src="/x.js?v=2">']}}}

    quarto_yml.add_include(quarto_config, "include-after-body", {"text": "x"}, marker="/x.js")

    assert quarto_config["format"]["html"]["include-after-body"] == ['<script src="/x.js?v=2">']


def test_add_include_without_a_marker_skips_an_equal_entry():
    entry = {"text": "<link rel='a'>\n<script src=\"/b.js\"></script>"}
    quarto_config = {"format": {"html": {"include-in-header": [dict(entry)]}}}

    quarto_yml.add_include(quarto_config, "include-in-header", entry)

    assert quarto_config["format"]["html"]["include-in-header"] == [entry]


@pytest.mark.parametrize(
    ("before", "expected"),
    [
        ("b.js", ["a.js", "new", "b.js"]),
        ("c.js", ["a.js", "b.js", "new"]),
        (None, ["a.js", "b.js", "new"]),
    ],
    ids=["anchor", "missing-anchor", "no-anchor"],
)
def test_add_include_inserts_before_its_anchor_or_appends(before: str | None, expected: list[str]):
    quarto_config = {"format": {"html": {"include-in-header": {"text": "a.js"}}}}
    quarto_yml.includes(quarto_config, "include-in-header").append({"text": "b.js"})

    quarto_yml.add_include(
        quarto_config, "include-in-header", {"text": "new"}, marker="new", before=before
    )

    entries = quarto_yml.includes(quarto_config, "include-in-header")
    assert [entry["text"] for entry in entries] == expected


def test_add_resources_appends_each_missing_name_once():
    quarto_config = {"project": {"resources": "objects.inv"}}

    quarto_yml.add_resources(quarto_config, ["a.js", "objects.inv", "a.js", "b.js"])

    assert quarto_config["project"]["resources"] == ["objects.inv", "a.js", "b.js"]


def test_add_render_excludes_starts_from_the_default_inputs():
    """A recursive `**` before the exclusions would override them (issue #228)"""
    quarto_config: dict[str, Any] = {"project": {"type": "website"}}

    quarto_yml.add_render_excludes(quarto_config, ["skill.md", ".well-known/**"])

    assert quarto_config["project"]["render"] == [
        *quarto_yml.RENDER_GLOBS,
        "!skill.md",
        "!.well-known/**",
    ]


def test_add_render_excludes_appends_each_missing_exclusion_once():
    quarto_config = {"project": {"render": "*.qmd"}}

    quarto_yml.add_render_excludes(quarto_config, ["a.html", "a.html"])
    quarto_yml.add_render_excludes(quarto_config, ["a.html", "b.html"])

    assert quarto_config["project"]["render"] == ["*.qmd", "!a.html", "!b.html"]


CHANGELOG = Contribution(navbar=(NavbarLink("Changelog", "changelog.qmd"),))


def test_apply_appends_navbar_links_in_order():
    reference = {"text": "Reference", "href": "reference/index.qmd"}
    quarto_config = {"website": {"navbar": {"left": [reference]}}}
    links = (NavbarLink("Changelog", "changelog.qmd"), NavbarLink("Blog", "blog/index.qmd"))

    quarto_yml.apply(quarto_config, Contribution(navbar=links), CONFIG)

    assert quarto_config["website"]["navbar"]["left"] == [
        reference,
        {"text": "Changelog", "href": "changelog.qmd"},
        {"text": "Blog", "href": "blog/index.qmd"},
    ]


@pytest.mark.parametrize("text", ["Changelog", "Journal des modifications"])
def test_apply_skips_a_link_whose_href_is_in_the_navbar(text: str):
    left = [{"text": text, "href": "changelog.qmd"}]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, CHANGELOG, CONFIG)

    assert left == [{"text": text, "href": "changelog.qmd"}]


def test_apply_adds_a_link_whose_text_is_in_the_navbar_with_another_href():
    news = {"text": "Changelog", "href": "https://example.com/news"}
    left = [news]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, CHANGELOG, CONFIG)

    assert left == [news, {"text": "Changelog", "href": "changelog.qmd"}]


def test_apply_skips_a_link_whose_own_item_is_in_the_navbar():
    """Keep one Reference item, whichever reference page it opens"""
    left = [{"text": "Référence", "href": "reference/index.qmd"}]
    cli = Contribution(navbar=(NavbarLink("Référence", "reference/cli/index.qmd"),))

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, cli, CONFIG)

    assert left == [{"text": "Référence", "href": "reference/index.qmd"}]


def test_apply_adds_a_link_beside_another_own_item():
    guide = {"text": "User Guide", "href": "user-guide/index.qmd"}
    left = [guide]
    cli = Contribution(navbar=(NavbarLink("Reference", "reference/cli/index.qmd"),))

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, cli, CONFIG)

    assert left == [guide, {"text": "Reference", "href": "reference/cli/index.qmd"}]


@pytest.mark.parametrize(
    "quarto_config",
    [{}, {"website": {}}, {"website": {"navbar": {}}}, {"website": {"navbar": {"right": []}}}],
)
def test_apply_without_a_left_navbar_changes_nothing(quarto_config: dict[str, Any]):
    before = copy.deepcopy(quarto_config)

    quarto_yml.apply(quarto_config, CHANGELOG, CONFIG)

    assert quarto_config == before


TAGS = Contribution(navbar=(NavbarLink("Tags", "tags/index.qmd", before="reference/index.qmd"),))


def test_apply_inserts_a_link_before_its_anchor():
    """Match the insertion target by its path even when its label differs"""
    guide = {"text": "User Guide", "href": "user-guide/index.qmd"}
    reference = {"text": "API", "href": "reference/index.qmd"}
    left = [guide, reference]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, TAGS, CONFIG)

    assert left == [guide, {"text": "Tags", "href": "tags/index.qmd"}, reference]


def test_apply_appends_a_link_whose_anchor_is_missing():
    """Append the link when its insertion target is absent"""
    guide = {"text": "User Guide", "href": "user-guide/index.qmd"}
    left = [guide]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, TAGS, CONFIG)

    assert left == [guide, {"text": "Tags", "href": "tags/index.qmd"}]


def test_apply_skips_a_link_the_navbar_already_has():
    """Preserve a built site's navbar when it already links the contributed page"""
    reference = {"text": "Reference", "href": "reference/index.qmd"}
    left = [{"text": "Tags", "href": "tags/index.qmd"}, reference]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, TAGS, CONFIG)

    assert left == [{"text": "Tags", "href": "tags/index.qmd"}, reference]


CLI_SIDEBAR = Sidebar("cli-reference", "CLI Reference", ("reference/cli/app.qmd",))
CLI_ENTRY = {"id": "cli-reference", "title": "CLI Reference", "contents": ["reference/cli/app.qmd"]}


@pytest.mark.parametrize("quarto_config", [{}, {"website": {}}, {"website": {"sidebar": None}}])
def test_apply_creates_the_sidebar_list(quarto_config: dict[str, Any]):
    quarto_yml.apply(quarto_config, Contribution(sidebars=(CLI_SIDEBAR,)), CONFIG)

    assert quarto_config["website"]["sidebar"] == [CLI_ENTRY]


def test_apply_appends_a_sidebar_after_the_others():
    reference = {"id": "reference", "contents": ["reference/index.qmd"]}
    quarto_config = {"website": {"sidebar": [reference]}}

    quarto_yml.apply(quarto_config, Contribution(sidebars=(CLI_SIDEBAR,)), CONFIG)

    assert quarto_config["website"]["sidebar"] == [reference, CLI_ENTRY]


def test_apply_moves_a_sidebar_with_the_same_id_last():
    """Replace all sidebars with the same `id` and append the new sidebar"""
    reference = {"id": "reference", "contents": ["reference/index.qmd"]}
    old = {"id": "cli-reference", "title": "Old", "contents": ["old.qmd"]}
    mcp = {"id": "mcp-reference", "contents": ["reference/mcp/index.qmd"]}
    quarto_config = {"website": {"sidebar": [reference, old, mcp, old]}}

    quarto_yml.apply(quarto_config, Contribution(sidebars=(CLI_SIDEBAR,)), CONFIG)

    assert quarto_config["website"]["sidebar"] == [reference, mcp, CLI_ENTRY]


def test_apply_without_sidebars_leaves_the_sidebar_key_absent():
    quarto_config: dict[str, Any] = {"website": {"navbar": {"left": []}}}

    quarto_yml.apply(quarto_config, CHANGELOG, CONFIG)

    assert "sidebar" not in quarto_config["website"]


def test_apply_adds_only_the_missing_resources_and_render_excludes():
    contribution = Contribution(resources=("raw.html", "logo.png"), render_excludes=("raw.html",))
    quarto_config: dict[str, Any] = {
        "project": {"resources": ["logo.png"], "render": ["*.qmd", "!raw.html"]}
    }

    quarto_yml.apply(quarto_config, contribution, CONFIG)

    assert quarto_config["project"]["resources"] == ["logo.png", "raw.html"]
    assert quarto_config["project"]["render"] == ["*.qmd", "!raw.html"]


def test_apply_without_project_files_leaves_the_project_absent():
    quarto_config: dict[str, Any] = {"website": {"navbar": {"left": []}}}

    quarto_yml.apply(quarto_config, CHANGELOG, CONFIG)

    assert "project" not in quarto_config


UNTITLED_SIDEBAR = Sidebar("reference", None, ({"text": "Index", "href": "reference/index.qmd"},))


def test_apply_writes_a_sidebar_without_a_title_key():
    """Omit the title key for an untitled sidebar, as in the API reference sidebar"""
    quarto_config: dict[str, Any] = {"website": {"sidebar": []}}

    quarto_yml.apply(quarto_config, Contribution(sidebars=(UNTITLED_SIDEBAR,)), CONFIG)

    assert quarto_config["website"]["sidebar"] == [
        {"id": "reference", "contents": [{"text": "Index", "href": "reference/index.qmd"}]}
    ]


TAGS_SCRIPT = {"file": "page-tags.js"}
OTHER_SCRIPT = {"file": "other.js"}


@pytest.mark.parametrize(
    "quarto_config",
    [
        {},
        {"format": {"html": {}}},
        {"format": {"html": {"include-after-body": "page-tags.js"}}},
        {"format": {"html": {"include-after-body": [OTHER_SCRIPT, TAGS_SCRIPT, TAGS_SCRIPT]}}},
        {"format": {"html": {"include-after-body": [OTHER_SCRIPT]}}},
        {"format": {"html": {"include-after-body": [{"text": "<script>window.__GD_X__=1;"}]}}},
        {"website": {"navbar": {"left": []}}},
    ],
    ids=["empty", "no-includes", "string", "script-twice", "script-missing", "assigned", "website"],
)
@pytest.mark.parametrize("data", [{"n": 1}, {"svg": "</svg>"}], ids=["plain", "closing-tag"])
def test_apply_adds_inline_data_as_inline_data_add_does(
    quarto_config: dict[str, Any], data: dict[str, Any]
):
    """Assign data before other additions to preserve the tags step's configuration key order"""
    expected = copy.deepcopy(quarto_config)
    inline_data.add(expected, "__GD_X__", data, before="page-tags.js")
    quarto_yml.apply(expected, CHANGELOG, CONFIG)
    contribution = Contribution(
        navbar=CHANGELOG.navbar,
        inline_data=(InlineData("__GD_X__", data, before="page-tags.js"),),
    )

    quarto_yml.apply(quarto_config, contribution, CONFIG)

    assert quarto_config == expected
    assert list(quarto_config) == list(expected)


GUIDE_ITEM = {"text": "User Guide", "href": "user-guide/index.qmd"}
REFERENCE_ITEM = {"text": "Reference", "href": "reference/index.qmd"}
BLOG_ITEM = {"text": "Blog", "href": "blog/index.qmd"}

NAVBARS: dict[str, list[dict[str, str]]] = {
    "with-reference": [GUIDE_ITEM, REFERENCE_ITEM, BLOG_ITEM],
    "cli-reference": [BLOG_ITEM, {"text": "Reference", "href": "reference/cli/index.qmd"}],
    "without-reference": [BLOG_ITEM, GUIDE_ITEM],
    "empty": [],
    "translated": [
        {"text": "Guide d'utilisation", "href": "user-guide/index.qmd"},
        {"text": "Référence", "href": "reference/index.qmd"},
    ],
    "same-href": [{"text": "Cookbook", "href": "recipes/cookbook.qmd"}, REFERENCE_ITEM],
    "same-own-item": [{"text": "Recipes", "href": "recipes/index.qmd"}, REFERENCE_ITEM],
}


@pytest.mark.parametrize("lang", ["en", "fr"])
@pytest.mark.parametrize("after", [None, "Blog", "User Guide", "Guide d'utilisation", "Missing"])
@pytest.mark.parametrize("left", NAVBARS.values(), ids=NAVBARS.keys())
def test_apply_places_an_authored_link_as_add_link_does(
    tmp_path: Path, left: list[dict[str, str]], after: str | None, lang: str
):
    """Skip an authored link under `recipes/` only when its exact `href` is present"""
    config = write_config(tmp_path, {"site": {"lang": lang}})
    link = NavbarLink("Cookbook", "recipes/cookbook.qmd", kind="authored", after=after)
    quarto_config = {"website": {"navbar": {"left": copy.deepcopy(left)}}}
    expected = copy.deepcopy(quarto_config)
    navbar.add_link(expected, link, config, after=after)

    quarto_yml.apply(quarto_config, Contribution(navbar=(link,)), config)

    assert quarto_config == expected


GUIDE_NAVBARS = {
    **NAVBARS,
    "same-href": [BLOG_ITEM, {"text": "Start", "href": "user-guide/intro.qmd"}, REFERENCE_ITEM],
    "other-guide-page": [{"text": "FAQ", "href": "user-guide/faq.qmd"}, REFERENCE_ITEM],
}


@pytest.mark.parametrize("lang", ["en", "fr"])
@pytest.mark.parametrize("left", GUIDE_NAVBARS.values(), ids=GUIDE_NAVBARS.keys())
def test_apply_places_the_user_guide_as_the_user_guide_step_does(
    tmp_path: Path, left: list[dict[str, str]], lang: str
):
    """Add the guide's link despite links to other guide pages, unlike a generated link"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "user_guide").mkdir()
    (tmp_path / "user_guide" / "intro.qmd").write_text("---\ntitle: Intro\n---\n")
    config = write_config(tmp_path, {"site": {"lang": lang}})
    docs = GreatDocs(project_path=str(tmp_path))
    guide = discover_user_guide(docs)
    assert guide is not None
    quarto_config: dict[str, Any] = {
        "website": {"navbar": {"left": copy.deepcopy(left)}, "sidebar": []}
    }
    docs.layout.build_dir.mkdir(parents=True)
    quarto_yml.write(docs.layout.build_dir, copy.deepcopy(quarto_config))
    user_guide_step(docs, guide)
    sidebar = user_guide.sidebar(guide)
    link = NavbarLink(navbar.USER_GUIDE.label(config), user_guide.entry(guide), kind="user_guide")
    contribution = Contribution(
        navbar=(link,),
        sidebars=(Sidebar(sidebar["id"], sidebar["title"], tuple(sidebar["contents"])),),
    )

    quarto_yml.apply(quarto_config, contribution, config)

    assert quarto_config == quarto_yml.read(docs.layout.build_dir)


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "authored", "before": "reference/index.qmd"},
        {"kind": "user_guide", "before": "reference/index.qmd"},
        {"after": "Blog"},
        {"kind": "user_guide", "after": "Blog"},
    ],
)
def test_navbar_link_rejects_a_placement_its_kind_ignores(fields: dict[str, Any]):
    with pytest.raises(ValueError, match="placement"):
        NavbarLink("Demos", "demos/index.qmd", **fields)
