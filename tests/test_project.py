"""
Tests for project names, metadata, package locations and repository selection from project files
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from great_docs._project.github import GithubRepo
from great_docs._project.layout import Layout
from great_docs._project.model import Project, locate_package_init, read_manifest
from great_docs.config import Config
from tests.support import write_pyproject


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


def test_configured_module_comes_before_detection(tmp_path: Path):
    write(tmp_path, "great-docs.yml", "module: chosen\n")
    write(tmp_path, "native.pyi", "")
    assert make(tmp_path).module == "chosen"


def test_module_is_a_root_stub_other_than_init_pyi(tmp_path: Path):
    write(tmp_path, "__init__.pyi", "")
    write(tmp_path, "native.pyi", "")
    assert make(tmp_path).module == "native"


def test_module_is_the_top_level_package_of_a_maturin_extension(tmp_path: Path):
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "pkg"\n[tool.maturin]\nmodule-name = "pkg._native"\n',
    )
    assert make(tmp_path).module == "pkg"


def test_module_is_a_discovered_package_that_is_not_hidden_private_or_a_test(tmp_path: Path):
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "dist"\n[tool.setuptools.packages.find]\nwhere = ["src"]\n',
    )
    for package in (".hidden", "_private", "tests", "real"):
        write(tmp_path, f"src/{package}/__init__.py", "")
    assert make(tmp_path).module == "real"


@pytest.mark.parametrize(
    ("packages", "module"),
    [('["nspkg.core", "nspkg"]', "nspkg.core"), ('["src/pkg"]', "pkg")],
)
def test_module_is_the_first_setuptools_package_as_an_import_name(
    tmp_path: Path, packages: str, module: str
):
    write(
        tmp_path,
        "pyproject.toml",
        f'[project]\nname = "dist"\n[tool.setuptools]\npackages = {packages}\n',
    )
    assert make(tmp_path).module == module


@pytest.mark.parametrize(
    "backend",
    [
        '[tool.hatch.build.targets.wheel]\npackages = ["src/mypkg"]\n',
        '[tool.poetry]\npackages = [{include = "mypkg", from = "src"}]\n',
    ],
)
def test_module_is_the_last_component_of_a_hatch_or_poetry_package_path(
    tmp_path: Path, backend: str
):
    write(tmp_path, "pyproject.toml", f'[project]\nname = "dist"\n{backend}')
    write(tmp_path, "src/mypkg/__init__.py", "")
    assert make(tmp_path).module == "mypkg"


@pytest.mark.parametrize(
    ("init_file", "module"),
    [
        # Match the rest of the distribution name to a namespace subpackage.
        ("src/firebird/base/__init__.py", "firebird.base"),
        # Document a regular package as a whole.
        ("src/firebird/__init__.py", "firebird"),
    ],
)
def test_declared_namespace_directory_selects_the_distribution_subpackage(
    tmp_path: Path, init_file: str, module: str
):
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "firebird-base"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/firebird"]\n',
    )
    write(tmp_path, init_file, "")
    assert make(tmp_path).module == module


@pytest.mark.parametrize(
    ("name", "init_file", "module"),
    [
        ("my-pkg", "src/my_pkg/__init__.py", "my_pkg"),
        # The dotted name is relative to the layout directory, not the package root.
        ("ns.pkg", "src/ns/pkg/__init__.py", "ns.pkg"),
        ("ns.pkg", "ns/pkg/__init__.py", "ns.pkg"),
    ],
)
def test_module_is_the_dotted_path_of_the_distribution_package(
    tmp_path: Path, name: str, init_file: str, module: str
):
    write_pyproject(tmp_path, name)
    write(tmp_path, init_file, "")
    assert make(tmp_path).module == module


def test_no_module_without_a_name_or_declared_package(tmp_path: Path):
    write(tmp_path, "first/__init__.py", "")
    write(tmp_path, "second/__init__.py", "")
    assert make(tmp_path).module is None


@pytest.mark.parametrize(
    ("files", "importable_name"),
    [
        ({"great-docs.yml": "module: chosen\n"}, "chosen"),
        ({"pyproject.toml": '[project]\nname = "my-pkg"\n'}, "my_pkg"),
        ({}, None),
    ],
)
def test_importable_name_is_the_module_else_the_distribution_name_with_underscores(
    tmp_path: Path, files: dict[str, str], importable_name: str | None
):
    for name, text in files.items():
        write(tmp_path, name, text)
    assert make(tmp_path).importable_name == importable_name


def test_package_init_belongs_to_the_importable_package(tmp_path: Path):
    write_pyproject(tmp_path, "pkg")
    write(tmp_path, "great-docs.yml", "module: other\n")
    write(tmp_path, "pkg/__init__.py", "__version__ = '1'\n")
    write(tmp_path, "other/__init__.py", "")
    assert make(tmp_path).package_init == tmp_path.resolve() / "other/__init__.py"


def locate(root: Path, name: str) -> Path | None:
    """
    Locate a package's `__init__.py` relative to the project directory

    Parameters
    ----------
    root
        The project directory.
    name
        The distribution or import name of the package.

    Returns
    -------
    :
        The file's path relative to `root`, or `None` if no package is found.
    """
    init_file = locate_package_init(root, read_manifest(root), name)
    return init_file.relative_to(root) if init_file else None


def test_package_init_with_version_or_all_is_preferred(tmp_path: Path):
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "python/pkg/__init__.py", "__all__ = []\n")
    write(tmp_path, "src/pkg/__init__.py", "__version__ = '1'\n")
    assert locate(tmp_path, "pkg") == Path("python/pkg/__init__.py")


def test_package_init_without_version_or_all_is_the_first_found(tmp_path: Path):
    write(tmp_path, "src/pkg/__init__.py", "")
    write(tmp_path, "lib/pkg/__init__.py", "")
    assert locate(tmp_path, "pkg") == Path("src/pkg/__init__.py")


@pytest.mark.parametrize(
    ("name", "init_file"),
    [("my-pkg", "my_pkg/__init__.py"), ("ns.pkg", "lib/ns/pkg/__init__.py")],
)
def test_package_init_accepts_hyphens_and_dots_in_the_name(
    tmp_path: Path, name: str, init_file: str
):
    write(tmp_path, init_file, "")
    assert locate(tmp_path, name) == Path(init_file)


@pytest.mark.parametrize(
    "backend",
    [
        '[tool.hatch.build.targets.wheel]\npackages = ["code/pkg"]\n',
        '[tool.setuptools.packages.find]\nwhere = ["code"]\n',
    ],
)
def test_package_init_in_declared_locations_comes_first(tmp_path: Path, backend: str):
    write(tmp_path, "pyproject.toml", f'[project]\nname = "pkg"\n{backend}')
    write(tmp_path, "pkg/__init__.py", "__version__ = '1'\n")
    write(tmp_path, "code/pkg/__init__.py", "__version__ = '1'\n")
    assert locate(tmp_path, "pkg") == Path("code/pkg/__init__.py")


def test_package_init_falls_back_to_any_package_in_a_layout_directory(tmp_path: Path):
    for directory in ("tests", "docs", "examples", "build", "venv", "_private", ".hidden"):
        write(tmp_path, f"{directory}/__init__.py", "")
    write(tmp_path, "src/real/__init__.py", "")
    assert locate(tmp_path, "missing") == Path("src/real/__init__.py")


def test_package_init_is_none_without_a_package(tmp_path: Path):
    write(tmp_path, "tests/__init__.py", "")
    assert locate(tmp_path, "missing") is None


@pytest.mark.parametrize(
    ("files", "compiled"),
    [
        (["Cargo.toml"], True),
        (["native.pyi"], True),
        (["native.pyi", "native.py"], False),
        (["__init__.pyi"], False),
        ([], False),
    ],
)
def test_compiled_extension_has_cargo_toml_or_a_stub_without_python_source(
    tmp_path: Path, files: list[str], compiled: bool
):
    for name in files:
        write(tmp_path, name, "")
    assert make(tmp_path).compiled_extension is compiled


def test_source_roots_are_the_package_root_and_its_existing_layout_directories(tmp_path: Path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "src").mkdir()
    root = tmp_path.resolve()
    assert make(tmp_path).source_roots == (root, root / "src", root / "lib")


def test_search_paths_read_the_import_path_when_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project = make(tmp_path)
    monkeypatch.setattr(sys, "path", ["/added/after/make"])
    assert project.search_paths() == [tmp_path.resolve(), "/added/after/make"]
