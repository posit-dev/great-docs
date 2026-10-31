import copy
from pathlib import Path
from typing import Any

import pytest
from yaml12 import parse_yaml

from great_docs._contribution import Contribution, NavbarLink
from great_docs._utils import QUARTO_YML_HEADER, validate_build_dir
from great_docs._website import quarto_yml
from tests.support import write_config


def test_write_adds_generated_header(tmp_path: Path):
    config = write_config(tmp_path)

    quarto_yml.write(tmp_path, {"project": {"type": "website"}}, config)

    text = (tmp_path / "_quarto.yml").read_text(encoding="utf-8")
    assert text.startswith(QUARTO_YML_HEADER)
    assert parse_yaml(text) == {"project": {"type": "website"}}


def test_write_translates_generated_navbar_labels(tmp_path: Path):
    config = write_config(tmp_path, {"site": {"lang": "de"}})
    navbar = {
        "left": [{"text": "User Guide", "href": "user-guide/"}, {"text": "Blog", "href": "blog/"}],
        "right": [{"text": "Changelog", "href": "changelog.qmd"}],
    }

    quarto_yml.write(tmp_path, {"website": {"navbar": navbar}}, config)

    written = quarto_yml.read(tmp_path)["website"]["navbar"]
    assert [item["text"] for item in written["left"]] == ["Benutzerhandbuch", "Blog"]
    assert [item["text"] for item in written["right"]] == ["Änderungsprotokoll"]


def test_write_keeps_english_labels(tmp_path: Path):
    config = write_config(tmp_path)
    navbar = {"left": [{"text": "Reference", "href": "reference/"}]}

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


@pytest.mark.parametrize(
    "quarto_config",
    [{}, {"website": {}}, {"website": {"navbar": {}}}, {"website": {"navbar": {"right": []}}}],
)
def test_apply_without_a_left_navbar_changes_nothing(quarto_config: dict[str, Any]):
    before = copy.deepcopy(quarto_config)

    quarto_yml.apply(quarto_config, CHANGELOG)

    assert quarto_config == before
