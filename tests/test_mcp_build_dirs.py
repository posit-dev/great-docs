import asyncio
import shutil
from pathlib import Path

import pytest
from mcp.types import CompletionArgument, ResourceTemplateReference

from great_docs._layout import Layout
from great_docs._utils import QUARTO_YML_HEADER, is_in_great_docs_build_dir
from great_docs.mcp import _sibling_build_dirs, handle_completion


@pytest.mark.parametrize("conflict", ["versions", "ownership"])
def test_clean_build_validates_before_removing_historical_output(
    tmp_path: Path, conflict: str
) -> None:
    from great_docs.mcp import _handle_build

    source = tmp_path / "docs"
    source.mkdir()
    versions = "versions: ['2.0', 'v1.5.0', '1.5.0']\n" if conflict == "versions" else ""
    (source / "great-docs.yml").write_text(versions)
    historical = source / "_quarto/v1.5.0"
    historical.mkdir(parents=True)
    (historical / "_quarto.yml").write_text(QUARTO_YML_HEADER)
    (historical / "index.qmd").write_bytes(b"old generated page\x00")
    if conflict == "ownership":
        (source / "_site").mkdir()
        (source / "_site/notes.txt").write_bytes(b"user notes\x00")
    before = {path: path.read_bytes() for path in source.rglob("*") if path.is_file()}

    with pytest.raises(ValueError):
        asyncio.run(_handle_build({"project_path": str(tmp_path), "clean": True}))

    assert all(path.is_file() and path.read_bytes() == content for path, content in before.items())


class TestSiblingBuildDirs:
    def _make_build_dir(self, path: Path) -> None:
        path.mkdir(parents=True)
        (path / "_quarto.yml").write_text(
            QUARTO_YML_HEADER + "project:\n  type: website\n", encoding="utf-8"
        )

    def test_finds_marked_dirs_only(self, tmp_path: Path):
        self._make_build_dir(tmp_path / "great-docs-0.2")
        self._make_build_dir(tmp_path / "great-docs-0.1")
        (tmp_path / "great-docs-notes").mkdir()
        (tmp_path / "great-docs").mkdir()

        result = _sibling_build_dirs(tmp_path)

        assert [d.name for d in result] == ["great-docs-0.1", "great-docs-0.2"]

    def test_empty_when_no_versions_built(self, tmp_path: Path):
        (tmp_path / "great-docs").mkdir()
        assert _sibling_build_dirs(tmp_path) == []

    def test_skips_symlinked_dir(self, tmp_path: Path):
        real_target = tmp_path / "real-target"
        self._make_build_dir(real_target)
        (tmp_path / "great-docs-0.1").symlink_to(real_target, target_is_directory=True)

        result = _sibling_build_dirs(tmp_path)

        assert result == []

    @pytest.mark.parametrize("directory", ["docs", "website"])
    def test_selected_layout(self, tmp_path: Path, directory: str) -> None:
        source = tmp_path / directory
        source.mkdir()
        config = source / "great-docs.yml"
        config.write_text("module: sample\n")
        layout = Layout.make(tmp_path, config)
        historical = source / "_quarto/v1.5.0"
        self._make_build_dir(historical)
        assert _sibling_build_dirs(tmp_path, layout=layout) == [historical]
        assert is_in_great_docs_build_dir(
            (directory, "_quarto", "v1.5.0", "index.qmd"), tmp_path, layout
        )
        assert not is_in_great_docs_build_dir(
            (directory, "examples", "_quarto", "v1.5.0", "index.qmd"), tmp_path, layout
        )
        assert not is_in_great_docs_build_dir(
            (directory, "_quarto", "notes", "index.qmd"), tmp_path, layout
        )


class TestCleanRemovesSiblings:
    """
    Deletion coverage for historical build directories

    A clean build must remove marked historical output while preserving the
    current build and unmarked directories.
    """

    def _make_build_dir(self, path: Path) -> None:
        path.mkdir(parents=True)
        (path / "_quarto.yml").write_text(
            QUARTO_YML_HEADER + "project:\n  type: website\n", encoding="utf-8"
        )

    def test_clean_removes_siblings_but_keeps_current_and_unmarked(self, tmp_path: Path):
        self._make_build_dir(tmp_path / "great-docs-0.1")
        (tmp_path / "great-docs").mkdir()
        (tmp_path / "great-docs" / "index.html").write_text("current build", encoding="utf-8")
        unmarked = tmp_path / "great-docs-notes"
        unmarked.mkdir()
        (unmarked / "notes.txt").write_text("keep me", encoding="utf-8")

        for d in _sibling_build_dirs(tmp_path):
            shutil.rmtree(d)

        assert not (tmp_path / "great-docs-0.1").exists()
        assert (tmp_path / "great-docs").is_dir()
        assert (tmp_path / "great-docs" / "index.html").exists()
        assert unmarked.is_dir()
        assert (unmarked / "notes.txt").read_text(encoding="utf-8") == "keep me"


class TestPageCompletionExcludesBuildDirs:
    """
    Coverage for page completion over project sources

    Build directories contain regenerated copies of `.qmd` files. Page
    completion must list the original source paths without those duplicates.
    """

    def _complete(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str = ""):
        monkeypatch.chdir(tmp_path)
        ref = ResourceTemplateReference(type="ref/resource", uri="great-docs://page/{path}")
        argument = CompletionArgument(name="path", value=value)
        result = asyncio.run(handle_completion(ref, argument))
        return result.values if result is not None else []

    def test_excludes_pages_under_latest_build_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "great-docs").mkdir()
        (tmp_path / "great-docs" / "index.qmd").write_text("", encoding="utf-8")
        (tmp_path / "own-page.qmd").write_text("", encoding="utf-8")

        values = self._complete(tmp_path, monkeypatch)

        assert "own-page.qmd" in values
        assert not any(v.startswith("great-docs/") for v in values)

    def test_excludes_pages_under_versioned_build_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "great-docs-0.2").mkdir()
        (tmp_path / "great-docs-0.2" / "_quarto.yml").write_text(
            QUARTO_YML_HEADER, encoding="utf-8"
        )
        (tmp_path / "great-docs-0.2" / "index.qmd").write_text("", encoding="utf-8")
        (tmp_path / "own-page.qmd").write_text("", encoding="utf-8")

        values = self._complete(tmp_path, monkeypatch)

        assert "own-page.qmd" in values
        assert not any(v.startswith("great-docs-0.2/") for v in values)

    def test_includes_pages_in_unmarked_build_like_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        notes = tmp_path / "great-docs-notes"
        notes.mkdir()
        (notes / "page.qmd").write_text("", encoding="utf-8")

        values = self._complete(tmp_path, monkeypatch)

        assert "great-docs-notes/page.qmd" in values

    def test_includes_nested_user_dir_with_similar_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        nested = tmp_path / "docs" / "great-docs-examples"
        nested.mkdir(parents=True)
        (nested / "page.qmd").write_text("", encoding="utf-8")

        values = self._complete(tmp_path, monkeypatch)

        assert "docs/great-docs-examples/page.qmd" in values
