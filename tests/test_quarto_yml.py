from pathlib import Path

import pytest
from yaml12 import parse_yaml

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
