"""
Tests for project names, metadata and repository selection from project files
"""

from __future__ import annotations

from pathlib import Path

import pytest

from great_docs._github import GithubRepo
from great_docs._layout import Layout
from great_docs._project import Project
from great_docs.config import Config


def make(root: Path) -> Project:
    """
    Read a project's name, metadata and GitHub repository from its files

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
        The project's name, declared metadata and GitHub repository.
    """
    layout = Layout.make(root)
    return Project.make(Config(root, config_path=layout.config_path), layout)


def write(root: Path, name: str, text: str) -> None:
    """
    Write a file into a project, creating its directories

    Parameters
    ----------
    root
        The project directory.
    name
        The file's path relative to `root`.
    text
        The file's contents.
    """
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pyproject_urls(root: Path, *entries: tuple[str, str]) -> None:
    """
    Write a `pyproject.toml` that declares project URLs

    Parameters
    ----------
    root
        The project directory.
    *entries
        The URLs as labels and addresses, in declaration order.
    """
    urls = "".join(f'"{label}" = "{url}"\n' for label, url in entries)
    write(root, "pyproject.toml", f'[project]\nname = "pkg"\n\n[project.urls]\n{urls}')


def test_name_is_the_declared_name(tmp_path: Path):
    write(tmp_path, "pyproject.toml", '[project]\nname = "my-pkg"\n')
    write(tmp_path, "other/__init__.py", "")
    assert make(tmp_path).name == "my-pkg"


@pytest.mark.parametrize(
    ("packages", "name"),
    [
        (["only"], "only"),
        (["only", ".hidden"], "only"),
        (["first", "second"], None),
        ([], None),
    ],
)
def test_without_a_declared_name_the_sole_package_directory_names_the_project(
    tmp_path: Path, packages: list[str], name: str | None
):
    for package in packages:
        write(tmp_path, f"{package}/__init__.py", "")
    # A directory without `__init__.py` is not a package.
    (tmp_path / "data").mkdir()
    assert make(tmp_path).name == name


def test_manifest_survives_an_unparsable_setup_cfg(tmp_path: Path):
    write(tmp_path, "pyproject.toml", '[project]\nname = "pkg"\ndescription = "Summary"\n')
    write(tmp_path, "setup.cfg", "[flake8]\nignore = E1\nignore = E2\n")
    project = make(tmp_path)
    assert project.name == "pkg"
    assert project.manifest["description"] == "Summary"


def test_unreadable_packaging_files_leave_the_manifest_empty(tmp_path: Path):
    write(tmp_path, "pyproject.toml", "[project\n")
    project = make(tmp_path)
    assert project.name is None
    assert project.manifest["description"] == ""


def test_configured_repo_wins_over_the_project_urls(tmp_path: Path):
    pyproject_urls(tmp_path, ("Repository", "https://github.com/url/repo"))
    write(tmp_path, "great-docs.yml", "repo: https://github.com/config/repo\n")
    assert make(tmp_path).github == GithubRepo("config", "repo")


def test_configured_repo_outside_github_names_no_repository(tmp_path: Path):
    pyproject_urls(tmp_path, ("Repository", "https://github.com/url/repo"))
    write(tmp_path, "great-docs.yml", "repo: https://gitlab.com/config/repo\n")
    assert make(tmp_path).github is None


@pytest.mark.parametrize(
    "label", ["Source Code", "source-code", "source_code", "REPOSITORY", "Git Hub", "HomePage"]
)
def test_url_labels_match_whatever_their_case_and_separators(tmp_path: Path, label: str):
    pyproject_urls(tmp_path, (label, "https://github.com/owner/repo"))
    assert make(tmp_path).github == GithubRepo("owner", "repo")


def test_url_labels_rank_repository_source_source_code_github_homepage(tmp_path: Path):
    ranked = ["Repository", "Source", "Source Code", "GitHub", "Homepage"]
    for best in range(len(ranked)):
        entries = [
            (label, f"https://github.com/owner/{index}") for index, label in enumerate(ranked)
        ]
        # Declare the labels in reverse, so declaration order cannot explain the choice.
        pyproject_urls(tmp_path, *reversed(entries[best:]))
        assert make(tmp_path).github == GithubRepo("owner", str(best))


def test_first_declared_of_two_labels_that_normalise_alike_wins(tmp_path: Path):
    pyproject_urls(
        tmp_path,
        ("source-code", "https://github.com/owner/first"),
        ("Source Code", "https://github.com/owner/second"),
    )
    assert make(tmp_path).github == GithubRepo("owner", "first")


@pytest.mark.parametrize(
    ("label", "url"),
    [
        ("Changelog", "https://github.com/owner/repo"),
        ("Repository", "https://gitlab.com/owner/repo"),
    ],
)
def test_other_labels_and_hosts_name_no_repository(tmp_path: Path, label: str, url: str):
    pyproject_urls(tmp_path, (label, url))
    assert make(tmp_path).github is None


def test_each_make_reads_the_files_afresh(tmp_path: Path):
    write(tmp_path, "pyproject.toml", '[project]\nname = "before"\n')
    layout = Layout.make(tmp_path)
    config = Config(tmp_path, config_path=layout.config_path)
    assert Project.make(config, layout).name == "before"

    write(tmp_path, "pyproject.toml", '[project]\nname = "after"\ndescription = "Edited"\n')

    project = Project.make(config, layout)
    assert project.name == "after"
    assert project.manifest["description"] == "Edited"
