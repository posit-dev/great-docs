from pathlib import Path

import pytest

from great_docs import _manifest
from great_docs._manifest import ManifestError


def write(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text, encoding="utf-8")


def test_reads_nothing_without_packaging_files(tmp_path: Path):
    manifest = _manifest.read(tmp_path)
    assert manifest["name"] is None
    assert manifest["description"] == ""
    assert manifest["scripts"] == {}


def test_reads_the_project_table(tmp_path: Path):
    write(
        tmp_path,
        "pyproject.toml",
        """
[project]
name = "my-pkg"
description = "A package"
license = "Apache-2.0 OR MIT"
authors = [{name = "Ada", email = "ada@example.com"}, "not a table"]
maintainers = [{email = "team@example.com"}]
requires-python = ">=3.11"
keywords = ["docs", 3]
dependencies = ["requests>=2; python_version < '3.12'", "rich[jupyter]", "not valid !"]

[project.optional-dependencies]
docs = ["sphinx"]
odd = "not a list"

[project.urls]
Homepage = "https://example.com"
Bad = 1
""",
    )
    manifest = _manifest.read(tmp_path)
    assert manifest["name"] == "my-pkg"
    assert manifest["description"] == "A package"
    assert manifest["license"] == "Apache-2.0 OR MIT"
    assert manifest["authors"] == [{"name": "Ada", "email": "ada@example.com"}]
    assert manifest["maintainers"] == [{"email": "team@example.com"}]
    assert manifest["requires_python"] == ">=3.11"
    assert manifest["keywords"] == ["docs"]
    assert manifest["dependencies"] == [
        {"name": "requests", "specifier": ">=2", "marker": 'python_version < "3.12"'},
        {"name": "rich", "specifier": "", "extras": ["jupyter"]},
        {"name": "not valid !", "specifier": ""},
    ]
    assert manifest["optional_dependencies"] == {
        "docs": [{"name": "sphinx", "specifier": ""}],
        "odd": [],
    }
    assert manifest["urls"] == {"Homepage": "https://example.com"}


@pytest.mark.parametrize(
    ("declaration", "licence"),
    [
        (
            'license = "Apache-2.0"\nclassifiers = ["License :: OSI Approved :: MIT License"]',
            "MIT",
        ),
        ('classifiers = ["License :: OSI Approved :: Zope Public License"]', "Zope Public License"),
        ('license = {text = "BSD"}', "BSD"),
        ('license = {file = "LICENSE"}', ""),
    ],
)
def test_licence_prefers_an_osi_classifier(tmp_path: Path, declaration: str, licence: str):
    write(tmp_path, "pyproject.toml", f'[project]\nname = "pkg"\n{declaration}\n')
    assert _manifest.read(tmp_path)["license"] == licence


def test_scripts_list_console_scripts_before_gui_scripts(tmp_path: Path):
    write(
        tmp_path,
        "pyproject.toml",
        """
[project.gui-scripts]
viewer = "pkg.gui:main"
both = "pkg.gui:both"

[project.scripts]
tool = "pkg.cli:main"
both = "pkg.cli:both"
""",
    )
    scripts = _manifest.read(tmp_path)["scripts"]
    assert list(scripts.items()) == [
        ("tool", "pkg.cli:main"),
        ("both", "pkg.cli:both"),
        ("viewer", "pkg.gui:main"),
    ]


def test_reads_package_declarations(tmp_path: Path):
    write(
        tmp_path,
        "pyproject.toml",
        """
[tool.setuptools]
packages = ["pkg", "pkg.sub"]
package-dir = {"" = "lib"}

[tool.hatch.build.targets.wheel]
packages = ["src/wheel_pkg"]

[[tool.poetry.packages]]
include = "other"
from = "src"

[[tool.poetry.packages]]
include = "plain"
""",
    )
    manifest = _manifest.read(tmp_path)
    assert manifest["declared_packages"] == [
        "pkg",
        "pkg/sub",
        "src/wheel_pkg",
        "src/other",
        "plain",
    ]
    assert manifest["package_dirs"] == ["lib"]


def test_reads_setuptools_find_directories(tmp_path: Path):
    write(tmp_path, "pyproject.toml", '[tool.setuptools.packages.find]\nwhere = ["code"]\n')
    manifest = _manifest.read(tmp_path)
    assert manifest["package_dirs"] == ["code"]
    assert manifest["discovery_dirs"] == ["code"]
    assert manifest["declared_packages"] == []


@pytest.mark.parametrize(
    ("find", "directories"),
    [('where = "code"\n', ["code"]), ("include = ['pkg*']\n", ["."])],
    ids=["string", "absent"],
)
def test_setuptools_find_where_may_be_a_string_or_absent(
    tmp_path: Path, find: str, directories: list[str]
):
    write(tmp_path, "pyproject.toml", f"[tool.setuptools.packages.find]\n{find}")
    assert _manifest.read(tmp_path)["discovery_dirs"] == directories


def test_setup_cfg_fills_what_pyproject_leaves_out(tmp_path: Path):
    write(tmp_path, "pyproject.toml", '[project]\ndescription = "From pyproject"\n')
    write(
        tmp_path,
        "setup.cfg",
        """
[metadata]
name = cfg-pkg
description = From setup.cfg
license = MIT
author = Ada
author_email = ada@example.com
maintainer = Bob
url = https://example.com/repo
project_urls =
    Docs = https://example.com/docs?q=100%

[options]
python_requires = >=3.10
""",
    )
    manifest = _manifest.read(tmp_path)
    assert manifest["name"] == "cfg-pkg"
    assert manifest["description"] == "From pyproject"
    assert manifest["license"] == "MIT"
    assert manifest["authors"] == [{"name": "Ada", "email": "ada@example.com"}]
    assert manifest["maintainers"] == [{"name": "Bob"}]
    assert manifest["urls"] == {
        "Repository": "https://example.com/repo",
        "Docs": "https://example.com/docs?q=100%",
    }
    assert manifest["requires_python"] == ">=3.10"


def test_setup_py_supplies_the_name_from_its_name_keyword(tmp_path: Path):
    write(tmp_path, "setup.py", 'username = "bob"\nsetup(name="realpkg")\n')
    assert _manifest.read(tmp_path)["name"] == "realpkg"


def test_setup_py_is_not_read_when_another_file_names_the_project(tmp_path: Path):
    write(tmp_path, "setup.cfg", "[metadata]\nname = cfg-pkg\n")
    write(tmp_path, "setup.py", 'setup(name="py-pkg")\n')
    assert _manifest.read(tmp_path)["name"] == "cfg-pkg"


@pytest.mark.parametrize(
    ("file", "text"),
    [
        ("pyproject.toml", "[project\n"),
        ("setup.cfg", "name = no section\n"),
        ("setup.py", b"name = '\xff'"),
    ],
)
def test_unreadable_files_raise_naming_the_file(tmp_path: Path, file: str, text: str | bytes):
    path = tmp_path / file
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    with pytest.raises(ManifestError, match=file):
        _manifest.read(tmp_path)


def test_reads_poetry_1_metadata(tmp_path: Path):
    write(
        tmp_path,
        "pyproject.toml",
        """
[tool.poetry]
name = "poetry-pkg"
description = "From Poetry"
authors = ["Ada Lovelace <ada@example.com>", "Bob"]
maintainers = ["Carol <carol@example.com>"]
repository = "https://github.com/owner/repo"
homepage = "https://example.com"
documentation = "https://example.com/docs"
license = "MIT"

[tool.poetry.dependencies]
python = "^3.11"
""",
    )
    manifest = _manifest.read(tmp_path)
    assert manifest["name"] == "poetry-pkg"
    assert manifest["description"] == "From Poetry"
    assert manifest["authors"] == [
        {"name": "Ada Lovelace", "email": "ada@example.com"},
        {"name": "Bob"},
    ]
    assert manifest["urls"] == {
        "Repository": "https://github.com/owner/repo",
        "Homepage": "https://example.com",
        "Documentation": "https://example.com/docs",
    }
    # Poetry 1.x support covers the name, description, authors and URLs only.
    assert manifest["maintainers"] == []
    assert manifest["license"] == ""
    assert manifest["requires_python"] == ""
    assert manifest["dependencies"] == []


def test_project_table_wins_over_poetry(tmp_path: Path):
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "pep621"\n\n[tool.poetry]\nname = "poetry"\ndescription = "Poetry"\n',
    )
    manifest = _manifest.read(tmp_path)
    assert manifest["name"] == "pep621"
    assert manifest["description"] == "Poetry"


def test_unparsable_setup_cfg_may_be_ignored_beside_pyproject(tmp_path: Path):
    write(tmp_path, "pyproject.toml", '[project]\nname = "pkg"\ndescription = "Summary"\n')
    write(tmp_path, "setup.cfg", "[flake8]\nignore = E1\nignore = E2\n")

    with pytest.raises(ManifestError, match="setup.cfg"):
        _manifest.read(tmp_path)
    manifest = _manifest.read(tmp_path, ignore_unparsable_setup_cfg=True)
    assert (manifest["name"], manifest["description"]) == ("pkg", "Summary")


def test_unparsable_setup_cfg_alone_raises_even_when_ignorable(tmp_path: Path):
    write(tmp_path, "setup.cfg", "[metadata]\nname = a\nname = b\n")

    with pytest.raises(ManifestError, match="setup.cfg"):
        _manifest.read(tmp_path, ignore_unparsable_setup_cfg=True)
