from pathlib import Path
from typing import Any

from great_docs._layout import Layout
from great_docs._website import quarto_yml, resources
from tests.support import write_config

NO_SKILL: dict[str, object] = {"skill": {"enabled": False}}


def _register(root: Path, settings: dict[str, object]) -> dict[str, Any]:
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    config = write_config(root, settings)
    layout = Layout.make(root)
    quarto_config: dict[str, Any] = {"project": {"resources": ["logo.png"]}}
    resources.register(quarto_config, config, layout)
    return quarto_config["project"]


def _mkdir(path: Path, *files: str) -> None:
    path.mkdir(parents=True)
    for name in files:
        (path / name).write_text("", encoding="utf-8")


def test_lists_only_the_shared_files_for_a_bare_project(tmp_path: Path):
    project = _register(tmp_path, NO_SKILL)

    assert project == {"resources": ["logo.png", "_shared/**"]}


def test_lists_the_asset_directories_that_the_build_holds(tmp_path: Path):
    build_dir = tmp_path / "great-docs"
    _mkdir(build_dir / "assets", "style.css")
    _mkdir(build_dir / "user-guide" / "images", "dark.png")
    _mkdir(build_dir / "user-guide" / "chapter", "page.qmd")
    _mkdir(build_dir / "recipes" / "_includes", "snippet.qmd")
    _mkdir(tmp_path / "recipes", "intro.qmd")

    project = _register(tmp_path, {**NO_SKILL, "sections": [{"title": "R", "dir": "recipes"}]})

    assert project["resources"] == [
        "logo.png",
        "user-guide/images/**",
        "assets/**",
        "_shared/**",
        "recipes/_includes/**",
    ]


def test_lists_the_marimo_notebooks_and_islands(tmp_path: Path):
    _mkdir(tmp_path / "great-docs" / "notebooks", "demo.py")

    project = _register(tmp_path, {**NO_SKILL, "marimo": {"enabled": True}})

    assert project["resources"] == [
        "logo.png",
        "notebooks/**",
        "_marimo_islands/**",
        "_shared/**",
    ]


def test_lists_the_skill_files_and_keeps_quarto_from_rendering_them(tmp_path: Path):
    project = _register(tmp_path, {})

    assert project["resources"] == ["logo.png", "_shared/**", "skill.md", ".well-known/**"]
    assert project["render"] == [*quarto_yml.RENDER_GLOBS, "!skill.md", "!.well-known/**"]


def test_lists_only_skill_md_without_well_known(tmp_path: Path):
    project = _register(tmp_path, {"skill": {"well_known": False}})

    assert project["resources"] == ["logo.png", "_shared/**", "skill.md"]
    assert project["render"] == [*quarto_yml.RENDER_GLOBS, "!skill.md"]


def test_lists_the_mcp_manifest_without_the_skill_files(tmp_path: Path):
    _mkdir(tmp_path / "great-docs" / ".well-known", "mcp.json")

    project = _register(tmp_path, NO_SKILL)

    assert project["resources"] == ["logo.png", "_shared/**", ".well-known/mcp.json"]


def test_lists_the_mcp_manifest_only_through_the_skill_glob(tmp_path: Path):
    _mkdir(tmp_path / "great-docs" / ".well-known", "mcp.json")

    project = _register(tmp_path, {})

    assert project["resources"] == ["logo.png", "_shared/**", "skill.md", ".well-known/**"]
