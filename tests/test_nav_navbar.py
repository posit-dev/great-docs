from pathlib import Path
from typing import Any

import pytest

from great_docs import GreatDocs
from great_docs._cliref import render as cli_render
from great_docs._contribution import NavbarLink
from great_docs._website import quarto_yml
from great_docs._website.navigation import navbar
from tests.support import discover_user_guide, sections_step, user_guide_step, write_config

DEMOS = NavbarLink(text="Demos", href="demos/index.qmd")
DEMOS_ITEM = {"text": "Demos", "href": "demos/index.qmd"}

GUIDE = {"text": "User Guide", "href": "user-guide/index.qmd"}
REFERENCE = {"text": "Reference", "href": "reference/index.qmd"}
CHANGELOG = {"text": "Changelog", "href": "changelog.qmd"}
BLOG = {"text": "Blog", "href": "blog/index.qmd"}

GUIDE_FR = {"text": "Guide d'utilisation", "href": "user-guide/index.qmd"}
REFERENCE_FR = {"text": "Référence", "href": "reference/index.qmd"}
CHANGELOG_FR = {"text": "Journal des modifications", "href": "changelog.qmd"}


def _quarto_config(*items: dict[str, str]) -> dict[str, Any]:
    return {"website": {"navbar": {"left": [dict(item) for item in items]}}}


def _labels(quarto_config: dict[str, Any]) -> list[str]:
    return [item["text"] for item in quarto_config["website"]["navbar"]["left"]]


def test_add_link_goes_before_reference(tmp_path: Path):
    quarto_config = _quarto_config(GUIDE, REFERENCE)

    assert navbar.add_link(quarto_config, DEMOS, write_config(tmp_path))
    assert quarto_config["website"]["navbar"]["left"] == [GUIDE, DEMOS_ITEM, REFERENCE]


def test_add_link_finds_reference_by_href(tmp_path: Path):
    config = write_config(tmp_path, {"site": {"lang": "fr"}})
    quarto_config = _quarto_config(GUIDE_FR, REFERENCE_FR, CHANGELOG_FR)

    navbar.add_link(quarto_config, DEMOS, config)

    assert _labels(quarto_config) == [
        "Guide d'utilisation",
        "Demos",
        "Référence",
        "Journal des modifications",
    ]


def test_add_link_follows_the_named_item(tmp_path: Path):
    quarto_config = _quarto_config(BLOG, GUIDE, REFERENCE)

    navbar.add_link(quarto_config, DEMOS, write_config(tmp_path), after="Blog")

    assert _labels(quarto_config) == ["Blog", "Demos", "User Guide", "Reference"]


@pytest.mark.parametrize("after", ["Reference", "Référence"])
def test_add_link_follows_a_translated_item_named_in_either_language(tmp_path: Path, after: str):
    config = write_config(tmp_path, {"site": {"lang": "fr"}})
    quarto_config = _quarto_config(GUIDE_FR, REFERENCE_FR, CHANGELOG_FR)

    navbar.add_link(quarto_config, DEMOS, config, after=after)

    assert _labels(quarto_config) == [
        "Guide d'utilisation",
        "Référence",
        "Demos",
        "Journal des modifications",
    ]


def test_add_link_follows_an_item_whose_label_names_great_docs_item(tmp_path: Path):
    """A label of Great Docs' own item finds a user's item with that text when none has its href"""
    external = {"text": "Reference", "href": "https://example.com/api"}
    quarto_config = _quarto_config(external, BLOG)

    navbar.add_link(quarto_config, DEMOS, write_config(tmp_path), after="Reference")

    assert _labels(quarto_config) == ["Reference", "Demos", "Blog"]


def test_add_link_goes_before_reference_when_the_named_item_is_missing(tmp_path: Path):
    quarto_config = _quarto_config(GUIDE, REFERENCE)

    navbar.add_link(quarto_config, DEMOS, write_config(tmp_path), after="Nonexistent")

    assert _labels(quarto_config) == ["User Guide", "Demos", "Reference"]


def test_add_link_goes_last_without_reference(tmp_path: Path):
    quarto_config = _quarto_config(BLOG)

    navbar.add_link(quarto_config, DEMOS, write_config(tmp_path))

    assert _labels(quarto_config) == ["Blog", "Demos"]


def test_add_link_skips_an_href_already_present(tmp_path: Path):
    quarto_config = _quarto_config({"text": "Examples", "href": "demos/index.qmd"}, REFERENCE)

    added = navbar.add_link(quarto_config, DEMOS, write_config(tmp_path))

    assert not added
    assert _labels(quarto_config) == ["Examples", "Reference"]


def test_add_link_adds_a_label_present_with_another_href(tmp_path: Path):
    quarto_config = _quarto_config({"text": "Demos", "href": "https://example.com"})

    assert navbar.add_link(quarto_config, DEMOS, write_config(tmp_path))
    assert _labels(quarto_config) == ["Demos", "Demos"]


def test_add_link_needs_a_left_side(tmp_path: Path):
    quarto_config: dict[str, Any] = {"website": {"sidebar": []}}

    assert not navbar.add_link(quarto_config, DEMOS, write_config(tmp_path))
    assert quarto_config == {"website": {"sidebar": []}}


def test_reorder_puts_listed_labels_first(tmp_path: Path):
    config = write_config(tmp_path, "navbar_order:\n  - User Guide\n  - Reference\n")
    quarto_config = _quarto_config(REFERENCE, CHANGELOG, GUIDE, DEMOS_ITEM)

    navbar.reorder(quarto_config, config)

    assert _labels(quarto_config) == ["User Guide", "Reference", "Changelog", "Demos"]


@pytest.mark.parametrize(
    "order",
    [
        ["Reference", "User Guide"],
        ["Référence", "Guide d'utilisation"],
        ["Référence", "User Guide"],
    ],
)
def test_reorder_finds_translated_items_by_either_label(tmp_path: Path, order: list[str]):
    config = write_config(tmp_path, {"site": {"lang": "fr"}, "navbar_order": order})
    quarto_config = _quarto_config(GUIDE_FR, REFERENCE_FR, DEMOS_ITEM)

    navbar.reorder(quarto_config, config)

    assert _labels(quarto_config) == ["Référence", "Guide d'utilisation", "Demos"]


def test_reorder_finds_reference_with_a_custom_title(tmp_path: Path):
    config = write_config(tmp_path, {"navbar_order": ["Reference", "User Guide"]})
    quarto_config = _quarto_config(GUIDE, {"text": "API", "href": "reference/index.qmd"})

    navbar.reorder(quarto_config, config)

    assert _labels(quarto_config) == ["API", "User Guide"]


def test_reorder_matches_other_labels_as_written(tmp_path: Path):
    config = write_config(tmp_path, {"navbar_order": ["Blog", "reference"]})
    quarto_config = _quarto_config(DEMOS_ITEM, REFERENCE, BLOG)

    navbar.reorder(quarto_config, config)

    assert _labels(quarto_config) == ["Blog", "Demos", "Reference"]


def test_reorder_without_navbar_order_keeps_the_order(tmp_path: Path):
    config = write_config(tmp_path)
    quarto_config = _quarto_config(REFERENCE, CHANGELOG)

    navbar.reorder(quarto_config, config)

    assert _labels(quarto_config) == ["Reference", "Changelog"]


def test_reorder_leaves_an_empty_left_side(tmp_path: Path):
    config = write_config(tmp_path, "navbar_order:\n  - Reference\n")
    quarto_config = _quarto_config()

    navbar.reorder(quarto_config, config)

    assert quarto_config == {"website": {"navbar": {"left": []}}}


def test_icon_labels_add_the_translated_label_of_an_english_key(tmp_path: Path):
    config = write_config(tmp_path, {"site": {"lang": "fr"}})

    icons = navbar.icon_labels({"Reference": "<svg/>", "Blog": "<svg b/>"}, config)

    assert icons == {"Reference": "<svg/>", "Blog": "<svg b/>", "Référence": "<svg/>"}


def test_icon_labels_keep_an_english_key_for_an_item_shown_in_english(tmp_path: Path):
    """A user's section titled `Changelog` keeps its English text and its icon on a French site"""
    config = write_config(tmp_path, {"site": {"lang": "fr"}})

    icons = navbar.icon_labels({"Changelog": "<svg/>"}, config)

    assert icons["Changelog"] == "<svg/>"


def test_icon_labels_prefer_a_translated_key_the_user_wrote(tmp_path: Path):
    config = write_config(tmp_path, {"site": {"lang": "fr"}})

    icons = navbar.icon_labels({"Référence": "<svg fr/>", "Reference": "<svg en/>"}, config)

    assert icons == {"Référence": "<svg fr/>", "Reference": "<svg en/>"}


def test_icon_labels_leave_an_english_site_unchanged(tmp_path: Path):
    icons = navbar.icon_labels({"Reference": "<svg/>"}, write_config(tmp_path))

    assert icons == {"Reference": "<svg/>"}


def _french_site(tmp_path: Path, settings: str, *left: dict[str, str]) -> GreatDocs:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    write_config(tmp_path, f"site:\n  lang: fr\n{settings}")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True)
    website: dict[str, Any] = {"navbar": {"left": [dict(item) for item in left]}, "sidebar": []}
    quarto_yml.write(docs.build_dir, {"website": website})
    return docs


def _built_labels(docs: GreatDocs) -> list[str]:
    return [item["text"] for item in quarto_yml.read(docs.build_dir)["website"]["navbar"]["left"]]


def test_user_guide_link_precedes_the_translated_reference(tmp_path: Path):
    docs = _french_site(tmp_path, "", DEMOS_ITEM, REFERENCE_FR)
    (tmp_path / "user_guide").mkdir()
    (tmp_path / "user_guide" / "intro.qmd").write_text("---\ntitle: Intro\n---\n")
    guide = discover_user_guide(docs)
    assert guide is not None

    user_guide_step(docs, guide)

    assert _built_labels(docs) == ["Demos", "Guide d'utilisation", "Référence"]


def test_cli_reference_link_is_labelled_in_the_site_language(tmp_path: Path):
    docs = _french_site(tmp_path, "", BLOG)

    contribution = cli_render.contribution(docs._config, ["reference/cli/index.qmd"])
    with quarto_yml.edit(docs.build_dir) as quarto_config:
        quarto_yml.apply(quarto_config, contribution, docs._config)

    assert _built_labels(docs) == ["Blog", "Référence"]


@pytest.mark.parametrize(("title", "label"), [("Recipes", "Recettes"), ("Examples", "Examples")])
def test_a_section_titled_recipes_is_labelled_in_the_site_language(
    tmp_path: Path, title: str, label: str
):
    sections = f"sections:\n  - title: {title}\n    dir: recipes\n"
    docs = _french_site(tmp_path, sections, REFERENCE_FR)
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "first.qmd").write_text("---\ntitle: First\n---\n")

    sections_step(docs, discover_user_guide(docs))

    assert _built_labels(docs) == [label, "Référence"]
