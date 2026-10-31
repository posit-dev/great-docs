from pathlib import Path

from great_docs import Config
from great_docs._content import sections
from great_docs._layout import Layout
from tests.support import write_config


def test_source_dirs_resolves_each_section_directory(tmp_path: Path):
    config = write_config(
        tmp_path,
        "sections:\n"
        "  - title: Examples\n    dir: examples\n"
        "  - title: Blog\n    dir: posts/../blog\n"
        "  - title: Listing only\n",
    )

    result = sections.source_dirs(config, Layout.make(tmp_path))

    assert result == {(tmp_path / "examples").resolve(), (tmp_path / "blog").resolve()}


def test_source_dirs_is_relative_to_the_configuration(tmp_path: Path):
    config_path = tmp_path / "docs" / "great-docs.yml"
    config_path.parent.mkdir()
    config_path.write_text("sections:\n  - title: Examples\n    dir: examples\n")
    layout = Layout.make(tmp_path, config_path)
    config = Config(layout.package_root, config_path=layout.config_path)

    assert sections.source_dirs(config, layout) == {(tmp_path / "docs" / "examples").resolve()}


def test_source_dirs_ignores_malformed_sections(tmp_path: Path):
    config = write_config(tmp_path, "sections: examples\n")

    assert sections.source_dirs(config, Layout.make(tmp_path)) == set()
