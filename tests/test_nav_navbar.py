from pathlib import Path
from typing import Any

from great_docs._contribution import NavbarLink
from great_docs._website.navigation import navbar
from tests.support import write_config

RECIPES = NavbarLink(text="Recipes", href="recipes/index.qmd")


def _quarto_config(*labels: str) -> dict[str, Any]:
    left = [{"text": label, "href": f"{label.lower()}.qmd"} for label in labels]
    return {"website": {"navbar": {"left": left}}}


def _labels(quarto_config: dict[str, Any]) -> list[str]:
    return [item["text"] for item in quarto_config["website"]["navbar"]["left"]]


def test_add_link_goes_before_reference():
    quarto_config = _quarto_config("User Guide", "Reference")

    assert navbar.add_link(quarto_config, RECIPES)
    assert _labels(quarto_config) == ["User Guide", "Recipes", "Reference"]
    assert quarto_config["website"]["navbar"]["left"][1] == {
        "text": "Recipes",
        "href": "recipes/index.qmd",
    }


def test_add_link_follows_the_named_item():
    quarto_config = _quarto_config("Home", "User Guide", "Reference")

    navbar.add_link(quarto_config, RECIPES, after="Home")

    assert _labels(quarto_config) == ["Home", "Recipes", "User Guide", "Reference"]


def test_add_link_goes_before_reference_when_the_named_item_is_missing():
    quarto_config = _quarto_config("Guide", "Reference")

    navbar.add_link(quarto_config, RECIPES, after="Nonexistent")

    assert _labels(quarto_config) == ["Guide", "Recipes", "Reference"]


def test_add_link_goes_last_without_reference():
    quarto_config = _quarto_config("Home")

    navbar.add_link(quarto_config, RECIPES)

    assert _labels(quarto_config) == ["Home", "Recipes"]


def test_add_link_skips_a_label_already_present():
    quarto_config = _quarto_config("Recipes", "Reference")

    added = navbar.add_link(quarto_config, NavbarLink(text="Recipes", href="recipes/other.qmd"))

    assert not added
    assert quarto_config["website"]["navbar"]["left"] == [
        {"text": "Recipes", "href": "recipes.qmd"},
        {"text": "Reference", "href": "reference.qmd"},
    ]


def test_add_link_needs_a_left_side():
    quarto_config: dict[str, Any] = {"website": {"sidebar": []}}

    assert not navbar.add_link(quarto_config, RECIPES)
    assert quarto_config == {"website": {"sidebar": []}}


def test_reorder_puts_listed_labels_first(tmp_path: Path):
    config = write_config(tmp_path, "navbar_order:\n  - User Guide\n  - Reference\n")
    quarto_config = _quarto_config("Reference", "Changelog", "User Guide", "Demos")

    navbar.reorder(quarto_config, config)

    assert _labels(quarto_config) == ["User Guide", "Reference", "Changelog", "Demos"]


def test_reorder_without_navbar_order_keeps_the_order(tmp_path: Path):
    config = write_config(tmp_path)
    quarto_config = _quarto_config("Reference", "Changelog")

    navbar.reorder(quarto_config, config)

    assert _labels(quarto_config) == ["Reference", "Changelog"]


def test_reorder_leaves_an_empty_left_side(tmp_path: Path):
    config = write_config(tmp_path, "navbar_order:\n  - Reference\n")
    quarto_config = _quarto_config()

    navbar.reorder(quarto_config, config)

    assert quarto_config == {"website": {"navbar": {"left": []}}}
