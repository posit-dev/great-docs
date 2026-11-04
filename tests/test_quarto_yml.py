import copy
from pathlib import Path
from typing import Any

import pytest
from yaml12 import parse_yaml

from great_docs._contribution import Contribution, NavbarLink, Sidebar
from great_docs._utils import QUARTO_YML_HEADER, validate_build_dir
from great_docs._website import quarto_yml
from tests.support import write_config


def test_write_adds_generated_header(tmp_path: Path):
    config = write_config(tmp_path)

    quarto_yml.write(tmp_path, {"project": {"type": "website"}}, config)

    text = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")
    assert text.startswith(QUARTO_YML_HEADER)
    assert parse_yaml(text) == {"project": {"type": "website"}}


def test_write_keeps_navbar_labels_on_a_translated_site(tmp_path: Path):
    """Leave a user's English label as written; Great Docs translates its own when it makes them"""
    config = write_config(tmp_path, {"site": {"lang": "de"}})
    navbar = {
        "left": [{"text": "Reference", "href": "https://example.com/api"}],
        "right": [{"text": "Changelog", "href": "changelog.qmd"}],
    }

    quarto_yml.write(tmp_path, {"website": {"navbar": navbar}}, config)

    assert quarto_yml.read(tmp_path)["website"]["navbar"] == navbar


def test_write_initial_marks_build_directory_as_generated(tmp_path: Path):
    quarto_yml.write_initial(tmp_path, write_config(tmp_path))

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


def test_read_seeds_missing_file(tmp_path: Path):
    assert quarto_yml.read(tmp_path, seed_website=True) == {
        "website": {"sidebar": [], "navbar": {"left": []}}
    }


def test_read_seeds_only_absent_website_keys(tmp_path: Path):
    (tmp_path / "_quarto.yml").write_text(
        "project:\n  type: website\nwebsite:\n  navbar:\n    right: []\n", encoding="utf-8"
    )

    assert quarto_yml.read(tmp_path, seed_website=True) == {
        "project": {"type": "website"},
        "website": {"navbar": {"right": []}, "sidebar": []},
    }


def test_edit_writes_on_clean_exit(tmp_path: Path):
    config = write_config(tmp_path)
    quarto_yml.write_initial(tmp_path, config)

    with quarto_yml.edit(tmp_path, config) as quarto_config:
        quarto_config["project"]["output-dir"] = "_site"

    assert quarto_yml.read(tmp_path)["project"]["output-dir"] == "_site"


def test_edit_leaves_file_unchanged_when_block_raises(tmp_path: Path):
    config = write_config(tmp_path)
    quarto_yml.write_initial(tmp_path, config)
    before = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")

    with pytest.raises(KeyError), quarto_yml.edit(tmp_path, config) as quarto_config:
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

    quarto_yml.apply(quarto_config, Contribution(navbar=links))

    assert quarto_config["website"]["navbar"]["left"] == [
        reference,
        {"text": "Changelog", "href": "changelog.qmd"},
        {"text": "Blog", "href": "blog/index.qmd"},
    ]


@pytest.mark.parametrize("text", ["Changelog", "Journal des modifications"])
def test_apply_skips_a_link_whose_href_is_in_the_navbar(text: str):
    left = [{"text": text, "href": "changelog.qmd"}]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, CHANGELOG)

    assert left == [{"text": text, "href": "changelog.qmd"}]


def test_apply_adds_a_link_whose_text_is_in_the_navbar_with_another_href():
    news = {"text": "Changelog", "href": "https://example.com/news"}
    left = [news]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, CHANGELOG)

    assert left == [news, {"text": "Changelog", "href": "changelog.qmd"}]


def test_apply_skips_a_link_whose_own_item_is_in_the_navbar():
    """Keep one Reference item, whichever reference page it opens"""
    left = [{"text": "Référence", "href": "reference/index.qmd"}]
    cli = Contribution(navbar=(NavbarLink("Référence", "reference/cli/index.qmd"),))

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, cli)

    assert left == [{"text": "Référence", "href": "reference/index.qmd"}]


def test_apply_adds_a_link_beside_another_own_item():
    guide = {"text": "User Guide", "href": "user-guide/index.qmd"}
    left = [guide]
    cli = Contribution(navbar=(NavbarLink("Reference", "reference/cli/index.qmd"),))

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, cli)

    assert left == [guide, {"text": "Reference", "href": "reference/cli/index.qmd"}]


@pytest.mark.parametrize(
    "quarto_config",
    [{}, {"website": {}}, {"website": {"navbar": {}}}, {"website": {"navbar": {"right": []}}}],
)
def test_apply_without_a_left_navbar_changes_nothing(quarto_config: dict[str, Any]):
    before = copy.deepcopy(quarto_config)

    quarto_yml.apply(quarto_config, CHANGELOG)

    assert quarto_config == before


TAGS = Contribution(navbar=(NavbarLink("Tags", "tags/index.qmd", before="reference/index.qmd"),))


def test_apply_inserts_a_link_before_its_anchor():
    """Match the insertion target by its path even when its label differs"""
    guide = {"text": "User Guide", "href": "user-guide/index.qmd"}
    reference = {"text": "API", "href": "reference/index.qmd"}
    left = [guide, reference]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, TAGS)

    assert left == [guide, {"text": "Tags", "href": "tags/index.qmd"}, reference]


def test_apply_appends_a_link_whose_anchor_is_missing():
    """Append the link when its insertion target is absent"""
    guide = {"text": "User Guide", "href": "user-guide/index.qmd"}
    left = [guide]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, TAGS)

    assert left == [guide, {"text": "Tags", "href": "tags/index.qmd"}]


def test_apply_inserts_an_anchored_link_once():
    """Insert a positioned link only once across repeated contributions"""
    reference = {"text": "Reference", "href": "reference/index.qmd"}
    left = [reference]

    quarto_yml.apply({"website": {"navbar": {"left": left}}}, TAGS)
    quarto_yml.apply({"website": {"navbar": {"left": left}}}, TAGS)

    assert left == [{"text": "Tags", "href": "tags/index.qmd"}, reference]


CLI_SIDEBAR = Sidebar("cli-reference", "CLI Reference", ("reference/cli/app.qmd",))
CLI_ENTRY = {"id": "cli-reference", "title": "CLI Reference", "contents": ["reference/cli/app.qmd"]}


@pytest.mark.parametrize("quarto_config", [{}, {"website": {}}, {"website": {"sidebar": None}}])
def test_apply_creates_the_sidebar_list(quarto_config: dict[str, Any]):
    quarto_yml.apply(quarto_config, Contribution(sidebars=(CLI_SIDEBAR,)))

    assert quarto_config["website"]["sidebar"] == [CLI_ENTRY]


def test_apply_appends_a_sidebar_after_the_others():
    reference = {"id": "reference", "contents": ["reference/index.qmd"]}
    quarto_config = {"website": {"sidebar": [reference]}}

    quarto_yml.apply(quarto_config, Contribution(sidebars=(CLI_SIDEBAR,)))

    assert quarto_config["website"]["sidebar"] == [reference, CLI_ENTRY]


def test_apply_replaces_the_sidebar_with_the_same_id_in_place():
    reference = {"id": "reference", "contents": ["reference/index.qmd"]}
    old = {"id": "cli-reference", "title": "Old", "contents": ["old.qmd"]}
    mcp = {"id": "mcp-reference", "contents": ["reference/mcp/index.qmd"]}
    quarto_config = {"website": {"sidebar": [reference, old, mcp]}}

    quarto_yml.apply(quarto_config, Contribution(sidebars=(CLI_SIDEBAR,)))

    assert quarto_config["website"]["sidebar"] == [reference, CLI_ENTRY, mcp]


def test_apply_without_sidebars_leaves_the_sidebar_key_absent():
    quarto_config: dict[str, Any] = {"website": {"navbar": {"left": []}}}

    quarto_yml.apply(quarto_config, CHANGELOG)

    assert "sidebar" not in quarto_config["website"]


def test_apply_adds_resources_and_render_excludes_once():
    contribution = Contribution(resources=("raw.html", "logo.png"), render_excludes=("raw.html",))
    quarto_config: dict[str, Any] = {"project": {"resources": ["logo.png"]}}

    quarto_yml.apply(quarto_config, contribution)
    quarto_yml.apply(quarto_config, contribution)

    assert quarto_config["project"]["resources"] == ["logo.png", "raw.html"]
    assert quarto_config["project"]["render"] == [*quarto_yml.RENDER_GLOBS, "!raw.html"]


def test_apply_without_project_files_leaves_the_project_absent():
    quarto_config: dict[str, Any] = {"website": {"navbar": {"left": []}}}

    quarto_yml.apply(quarto_config, CHANGELOG)

    assert "project" not in quarto_config
