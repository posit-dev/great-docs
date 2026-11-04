from pathlib import Path

from great_docs._content.walk import is_asset_dir


def test_a_directory_without_pages_is_an_asset_dir(tmp_path: Path):
    directory = tmp_path / "images"
    (directory / "dark").mkdir(parents=True)
    (directory / "dark" / "logo.png").write_bytes(b"PNG")

    assert is_asset_dir(directory)


def test_a_directory_with_a_nested_page_is_not_an_asset_dir(tmp_path: Path):
    directory = tmp_path / "chapter"
    (directory / "part").mkdir(parents=True)
    (directory / "part" / "page.qmd").write_text("---\ntitle: Test\n---\n", encoding="utf-8")

    assert not is_asset_dir(directory)


def test_an_underscore_directory_is_an_asset_dir_despite_its_pages(tmp_path: Path):
    directory = tmp_path / "_includes"
    directory.mkdir()
    (directory / "snippet.qmd").write_text("```python\nx = 1\n```\n", encoding="utf-8")

    assert is_asset_dir(directory)
