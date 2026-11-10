"""
Tests for reference page generation and source links
"""

from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from great_docs import GreatDocs
from great_docs._apiref.api_reference import APIReference
from great_docs._build import reference
from great_docs._build.log import BuildLog
from great_docs._build.pipeline import Run
from great_docs._build.steps import Outcome, Skipped
from great_docs._interlinks.sphinx_inventory import decode
from great_docs._reference import discovery_cache
from great_docs._reference.exports import Exports
from great_docs._utils import QUARTO_YML_HEADER
from great_docs._website import quarto_yml
from great_docs._website.ai_agents import llms_txt
from tests.support import (
    StubRemote,
    make_run,
    prepare_build_directory,
    write_config,
    write_pyproject,
)


@pytest.mark.parametrize("dynamic", [False, True])
def test_case_collision_links_match_pages_from_an_uninstalled_source_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dynamic: bool
) -> None:
    """Keep early navigation links consistent with the pages generated later"""
    name = "case_paths_source"
    source = tmp_path / "src"
    package = source / name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        'class Foo:\n    """The Foo class"""\n\ndef foo():\n    """The foo function"""\n',
        encoding="utf-8",
    )
    write_pyproject(tmp_path, name)
    write_config(
        tmp_path,
        {"dynamic": dynamic, "reference": [{"title": "API", "contents": ["Foo", "foo"]}]},
    )
    docs = GreatDocs(project_path=str(tmp_path))
    docs._remote = StubRemote()
    original_paths = list(sys.path)
    assert str(source) not in original_paths

    try:
        for _ in range(2):
            monkeypatch.chdir(tmp_path)
            monkeypatch.setattr(sys, "path", original_paths.copy())
            sys.modules.pop(name, None)
            run = make_run(docs)
            prepare_build_directory(docs, run)
            sidebar = run.contributions[0].sidebars[0]
            index_path = llms_txt.write_index(
                docs.layout,
                run.api_block,
                {},
                site_url=None,
                report=lambda _: None,
            )
            assert index_path is not None
            llms_index = index_path.read_text(encoding="utf-8")
            monkeypatch.chdir(docs.layout.build_dir)
            outcome, ref = reference.api(
                run, docs._config, docs.layout, BuildLog(stream=io.StringIO())
            )

            assert outcome == "API reference generated"
            assert ref is not None
            assert [page.path for page in ref.manifest.pages] == ["Foo", "foo-function"]
            assert [link["href"] for link in sidebar.contents[1]["contents"]] == [
                "reference/Foo.qmd",
                "reference/foo-function.qmd",
            ]
            assert "[Foo](reference/Foo.html)" in llms_index
            assert "[foo](reference/foo-function.html)" in llms_index
            reference_dir = docs.layout.build_dir / "reference"
            assert {p.name for p in reference_dir.glob("*.qmd")} == {
                "index.qmd",
                "Foo.qmd",
                "foo-function.qmd",
            }
            index = (reference_dir / "index.qmd").read_text(encoding="utf-8")
            assert "Foo.qmd#" in index
            assert "foo-function.qmd#" in index
            inventory = decode((docs.layout.build_dir / "objects.inv").read_bytes())
            assert {entry.uri.split("#")[0] for entry in inventory.entries} == {
                "reference/Foo.html",
                "reference/foo-function.html",
            }
    finally:
        sys.modules.pop(name, None)


def _source_linked_project(root: Path, name: str, branch: str) -> GreatDocs:
    """
    Create a project whose API reference links to a branch of its GitHub repository

    Parameters
    ----------
    root
        The directory in which to create the project.
    name
        The package name, unique within the test session.
    branch
        The configured source-link branch.

    Returns
    -------
    :
        The project with its build directory's Quarto configuration written.
    """
    root.mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\n\n'
        f'[project.urls]\nRepository = "https://github.com/owner/{name}"\n',
        encoding="utf-8",
    )
    (root / "great-docs.yml").write_text(f"source:\n  branch: {branch}\n", encoding="utf-8")
    (root / name).mkdir()
    (root / name / "__init__.py").write_text(
        'def greet():\n    """Say hello."""\n    return "hi"\n', encoding="utf-8"
    )
    docs = GreatDocs(project_path=str(root))
    docs.layout.build_dir.mkdir(parents=True)
    block = {
        "package": name,
        "dynamic": False,
        "dir": "reference",
        "sections": [{"title": "Functions", "contents": [{"name": "greet"}]}],
    }
    (docs.layout.build_dir / "_quarto.yml").write_text(
        yaml.safe_dump({"api-reference": block}), encoding="utf-8"
    )
    return docs


def _write_api_reference(docs: GreatDocs) -> Outcome:
    """
    Run the API reference step in the build directory, as a build does

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The step's outcome.
    """
    quarto_config = quarto_yml.read(docs.layout.build_dir)
    run = make_run(docs, quarto_config=quarto_config, api_block=quarto_config["api-reference"])
    outcome, _ = reference.api(run, docs._config, docs.layout, BuildLog(stream=io.StringIO()))
    return outcome


def _discoverable_project(root: Path, name: str) -> GreatDocs:
    """
    Create a project whose package exports one documented function

    Parameters
    ----------
    root
        The project directory.
    name
        The package name, unique within the test session.

    Returns
    -------
    :
        The project.
    """
    _ = write_pyproject(root, name)
    (root / name).mkdir()
    (root / name / "__init__.py").write_text(
        '__all__ = ["greet"]\n\n\ndef greet():\n    """Say hello."""\n',
        encoding="utf-8",
    )
    _ = write_config(root)
    return GreatDocs(project_path=str(root))


def _configure(docs: GreatDocs, *, refresh: bool) -> Run:
    """
    Configure the API reference as build preparation does

    Parameters
    ----------
    docs
        The project.
    refresh
        Whether to rediscover the package's exports.

    Returns
    -------
    :
        The build state holding the API reference block.
    """
    run = make_run(docs)
    reference.add_api_block(run, docs._config, refresh=refresh)
    return run


def _cache_file(docs: GreatDocs) -> Path:
    """
    Locate the project's cached API discovery

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The cache file's path.
    """
    return docs._config.cache_dir / discovery_cache.PATH


def _spy_on_discovery() -> AbstractContextManager[MagicMock]:
    """
    Record calls to export discovery while letting it run

    Returns
    -------
    :
        A context manager yielding the recording mock.
    """
    return patch.object(Exports, "sections", autospec=True, side_effect=Exports.sections)


def test_no_refresh_reuses_the_discovery_of_the_last_build(tmp_path: Path):
    """
    Reuse the last build's discovery while the package and configuration are unchanged
    """
    docs = _discoverable_project(tmp_path, "cache_reuse")
    discovered = _configure(docs, refresh=True)

    with _spy_on_discovery() as sections:
        reused = _configure(docs, refresh=False)

    sections.assert_not_called()
    assert reused.has_api_reference
    assert reused.api_block == discovered.api_block
    assert reference.api_config(reused) == "Reused cached API discovery"


def test_no_refresh_discovers_when_a_package_file_changes(tmp_path: Path):
    """
    Rediscover the exports after a package file changes
    """
    docs = _discoverable_project(tmp_path, "cache_edit")
    _ = _configure(docs, refresh=True)
    (tmp_path / "cache_edit" / "__init__.py").write_text(
        '__all__ = ["greet", "part"]\n\n\n'
        'def greet():\n    """Say hello."""\n\n\n'
        'def part():\n    """Say goodbye."""\n',
        encoding="utf-8",
    )

    with _spy_on_discovery() as sections:
        run = _configure(docs, refresh=False)

    sections.assert_called_once()
    assert run.api_block is not None
    assert "part" in str(run.api_block["sections"])
    assert reference.api_config(run) == "API reference discovered"


def test_no_refresh_reuses_the_discovery_of_a_moved_project(tmp_path: Path):
    """
    Reuse the discovery saved before the project moved to another directory
    """
    (tmp_path / "before").mkdir()
    docs = _discoverable_project(tmp_path / "before", "cache_move")
    discovered = _configure(docs, refresh=True)
    moved = shutil.copytree(tmp_path / "before", tmp_path / "after")

    with _spy_on_discovery() as sections:
        reused = _configure(GreatDocs(project_path=str(moved)), refresh=False)

    sections.assert_not_called()
    assert reused.api_block == discovered.api_block


def test_no_refresh_discovers_when_a_package_file_is_renamed(tmp_path: Path):
    """
    Rediscover the exports after a package file is renamed with its content unchanged
    """
    docs = _discoverable_project(tmp_path, "cache_rename")
    package = tmp_path / "cache_rename"
    _ = (package / "helpers.py").write_text("VALUE = 1\n", encoding="utf-8")
    _ = _configure(docs, refresh=True)
    _ = (package / "helpers.py").rename(package / "utilities.py")

    with _spy_on_discovery() as sections:
        _ = _configure(docs, refresh=False)

    sections.assert_called_once()


def test_no_refresh_discovers_when_the_configuration_changes(tmp_path: Path):
    """
    Rediscover the exports after `great-docs.yml` changes
    """
    docs = _discoverable_project(tmp_path, "cache_config")
    _ = _configure(docs, refresh=True)
    docs._config = write_config(tmp_path, "exclude:\n  - greet\n")

    with _spy_on_discovery() as sections:
        _ = _configure(docs, refresh=False)

    sections.assert_called_once()


def test_refresh_rediscovers_and_rewrites_the_cache(tmp_path: Path):
    """
    Rediscover the exports with `refresh` even when the cache matches, and save the result
    """
    docs = _discoverable_project(tmp_path, "cache_refresh")
    discovered = _configure(docs, refresh=True)
    # A cache entry under the current key, with sections no discovery would produce
    cache_file = _cache_file(docs)
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    saved["sections"] = [{"title": "Stale", "contents": ["greet"]}]
    _ = cache_file.write_text(json.dumps(saved), encoding="utf-8")

    with _spy_on_discovery() as sections:
        refreshed = _configure(docs, refresh=True)

    sections.assert_called_once()
    assert refreshed.api_block == discovered.api_block
    assert _configure(docs, refresh=False).api_block == discovered.api_block


@pytest.mark.parametrize(
    "content",
    ["{not json", '["a", "list"]', '{"key": 1}', '{"key": "abc", "sections": "text"}'],
)
def test_no_refresh_discovers_when_the_cache_is_unusable(tmp_path: Path, content: str):
    """
    Treat an unreadable or malformed cache as absent and replace it
    """
    docs = _discoverable_project(tmp_path, "cache_corrupt")
    discovered = _configure(docs, refresh=True)
    _ = _cache_file(docs).write_text(content, encoding="utf-8")

    with _spy_on_discovery() as sections:
        run = _configure(docs, refresh=False)

    sections.assert_called_once()
    assert run.api_block == discovered.api_block
    assert reference.api_config(_configure(docs, refresh=False)) == "Reused cached API discovery"


def test_api_config_skips_a_site_without_an_api_reference(tmp_path: Path):
    """
    Skip the step when build preparation found no API reference
    """
    write_config(tmp_path, "module: mypkg\n")
    docs = GreatDocs(project_path=str(tmp_path))

    assert reference.api_config(make_run(docs, has_api_reference=False)) == Skipped(
        "no API reference"
    )


def test_api_links_each_project_in_a_process_to_its_own_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Link each project's reference pages to its own repository and branch
    """
    pages: list[str] = []
    for name, branch in [("srclinks_a", "branch-a"), ("srclinks_b", "branch-b")]:
        docs = _source_linked_project(tmp_path / name, name, branch)
        monkeypatch.syspath_prepend(str(docs.layout.package_root))
        monkeypatch.chdir(docs.layout.build_dir)
        _ = _write_api_reference(docs)
        pages.append(
            (docs.layout.build_dir / "reference" / "greet.qmd").read_text(encoding="utf-8")
        )

    assert "github.com/owner/srclinks_a/blob/branch-a/srclinks_a/__init__.py" in pages[0]
    assert "github.com/owner/srclinks_b/blob/branch-b/srclinks_b/__init__.py" in pages[1]


def test_api_imports_the_package_from_the_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Import the documented package from the project root, as Quarto does
    """
    docs = _source_linked_project(tmp_path / "srclinks_path", "srclinks_path", "main")
    root = str(docs.layout.package_root)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.chdir(docs.layout.build_dir)

    assert _write_api_reference(docs) == "API reference generated"

    assert root in sys.path


def test_api_retry_with_static_analysis_disables_dynamic_introspection_in_the_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Disable dynamic introspection in memory before retrying with static analysis
    """
    docs = _source_linked_project(tmp_path / "static_retry", "static_retry", "main")
    monkeypatch.chdir(docs.layout.build_dir)
    quarto_config = quarto_yml.read(docs.layout.build_dir)
    block = quarto_config["api-reference"]
    block["dynamic"] = True
    run = make_run(docs, quarto_config=quarto_config, api_block=block)
    dynamic: list[bool] = []

    def build(ref: APIReference) -> None:
        dynamic.append(ref.settings.dynamic)
        if len(dynamic) == 1:
            raise ImportError("dynamic")

    with patch.object(APIReference, "build", autospec=True, side_effect=build):
        outcome, _ = reference.api(run, docs._config, docs.layout, BuildLog(stream=io.StringIO()))

    assert outcome == "API reference generated (static analysis)"
    assert dynamic == [True, False]
    assert run.quarto_config["api-reference"]["dynamic"] is False


def test_cli_reports_a_command_tree_without_pages(tmp_path: Path):
    """
    Report an empty CLI result without changing the Quarto configuration
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
    write_config(tmp_path, "cli:\n  enabled: true\n")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.layout.build_dir.mkdir()
    (docs.layout.build_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER, encoding="utf-8")

    with (
        patch("great_docs._cliref.click.discover", return_value={"name": "mycli"}),
        patch("great_docs._cliref.render.write_pages", return_value=[]),
    ):
        outcome = reference.cli(make_run(docs), docs._config, docs.layout)

    assert outcome == "No CLI pages generated"
    assert (docs.layout.build_dir / "_quarto.yml").read_text(encoding="utf-8") == QUARTO_YML_HEADER
