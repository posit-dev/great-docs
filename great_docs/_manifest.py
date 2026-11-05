"""
Project metadata declared in Python packaging files

Every command reads the same name, description and other project metadata from
`pyproject.toml`, `setup.cfg` and `setup.py`, regardless of which file declares them.
"""

from __future__ import annotations

import configparser
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import NotRequired, TypedDict, TypeVar

from packaging.requirements import InvalidRequirement
from packaging.requirements import Requirement as _Requirement

from great_docs._yaml import YamlMapping, YamlValue

__all__ = ["Dependency", "Manifest", "ManifestError", "Person", "empty", "read"]

_T = TypeVar("_T")

# The word boundary excludes longer names such as `username` from `name = "..."` matches.
_SETUP_PY_NAME = re.compile(r"\bname\s*=\s*[\"']([^\"']+)[\"']")

# Poetry 1.x authors may combine a name and email as `Name <email>`.
_POETRY_PERSON = re.compile(r"(.*?)\s*<([^>]*)>\s*")

# SPDX identifiers for recognised OSI-approved licence classifiers.
_LICENCE_CLASSIFIERS = {
    "MIT License": "MIT",
    "Apache Software License": "Apache-2.0",
    "GNU General Public License v3 (GPLv3)": "GPL-3.0",
    "GNU General Public License v2 (GPLv2)": "GPL-2.0",
    "BSD License": "BSD-3-Clause",
    "ISC License (ISCL)": "ISC",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}


class ManifestError(Exception):
    """An error reading or parsing a packaging file"""


class Person(TypedDict, total=False):
    """An author or maintainer of the project"""

    name: str
    email: str


class Dependency(TypedDict):
    """A requirement the project declares on another distribution"""

    name: str
    """The distribution name, or the whole requirement when it is not valid PEP 508"""

    specifier: str
    """The version specifier, such as `>=1.0,<2`; empty when there is none"""

    marker: NotRequired[str]
    """The environment marker, such as `python_version < "3.12"`"""

    extras: NotRequired[list[str]]
    """The requested extras, sorted"""


class Manifest(TypedDict):
    """
    The metadata a project declares about itself

    Every key is present. Missing values and values of the wrong type are `None` for `name`
    and empty for every other key.
    """

    name: str | None
    """The distribution name, as written"""

    description: str
    """The one-line summary"""

    license: str
    """
    The SPDX identifier of the first OSI-approved licence classifier, falling back to the
    `license` expression or text
    """

    authors: list[Person]
    """The authors, in the declared order"""

    maintainers: list[Person]
    """The maintainers, in the declared order"""

    urls: dict[str, str]
    """The project URLs, keyed by label as written"""

    requires_python: str
    """The supported Python versions, such as `>=3.11`"""

    keywords: list[str]
    """The keywords for package indexes"""

    dependencies: list[Dependency]
    """The runtime requirements"""

    optional_dependencies: dict[str, list[Dependency]]
    """The requirements of each extra, keyed by the extra's name"""

    scripts: dict[str, str]
    """
    The entry point of each command the package installs, keyed by command name: console
    scripts, then GUI scripts
    """

    declared_packages: list[str]
    """
    Package paths declared for inclusion by the build backend, relative to the project root
    with `/` separators, such as `mypkg/sub` or `src/mypkg`. The order is setuptools
    `packages`, hatch wheel `packages`, then Poetry `packages`
    """

    package_dirs: list[str]
    """
    Directories the build backend searches for packages, relative to the project root: the
    setuptools `package-dir` values and `discovery_dirs`
    """

    discovery_dirs: list[str]
    """
    Directories that setuptools package discovery (`[tool.setuptools.packages.find]`)
    searches, relative to the project root: its `where` value, or `.` when it has none
    """

    extension_module: str
    """The dotted name of the compiled module that Maturin builds, such as `pkg._native`"""

    declared_import_names: list[str]
    """
    The setuptools `packages` entries as written: import names such as `mypkg.sub`, which
    `declared_packages` also lists as paths
    """


def read(root: Path, *, ignore_unparsable_setup_cfg: bool = False) -> Manifest:
    """
    Read the metadata declared in a project's packaging files

    Use the first declaration of each value: `[project]` in `pyproject.toml`, then
    `[tool.poetry]` for a Poetry 1.x project, then `setup.cfg`, then `setup.py`. Poetry supplies
    only the name, description, authors and URLs; `setup.py` supplies only the name.

    Parameters
    ----------
    root
        The directory holding the packaging files.
    ignore_unparsable_setup_cfg
        Whether to ignore an unreadable or invalid `setup.cfg` when `pyproject.toml` can be
        read and parsed. Some projects use `setup.cfg` only for tool settings that
        `configparser` rejects.

    Returns
    -------
    :
        The metadata, with `None` for an undeclared name and empty values for other undeclared
        fields.

    Raises
    ------
    ManifestError
        A packaging file exists but cannot be read or parsed.
    """
    manifest = empty()
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = YamlMapping(_load(pyproject, _parse_toml))
        poetry = _from_poetry(data.mapping("tool").mapping("poetry"))
        manifest = _first(_from_pyproject(data), poetry)
    setup_cfg = root / "setup.cfg"
    if setup_cfg.is_file():
        try:
            manifest = _first(manifest, _from_setup_cfg(_load(setup_cfg, _parse_cfg)))
        except ManifestError:
            if not (ignore_unparsable_setup_cfg and pyproject.is_file()):
                raise
    setup_py = root / "setup.py"
    if not manifest["name"] and setup_py.is_file():
        match = _SETUP_PY_NAME.search(_load(setup_py, str))
        manifest["name"] = match[1] if match else None
    return manifest


def empty() -> Manifest:
    """
    Make an empty project manifest

    Returns
    -------
    :
        A manifest whose name is `None` and whose other values are empty.
    """
    return Manifest(
        name=None,
        description="",
        license="",
        authors=[],
        maintainers=[],
        urls={},
        requires_python="",
        keywords=[],
        dependencies=[],
        optional_dependencies={},
        scripts={},
        declared_packages=[],
        package_dirs=[],
        discovery_dirs=[],
        extension_module="",
        declared_import_names=[],
    )


def _load(path: Path, parse: Callable[[str], _T]) -> _T:
    """
    Read a packaging file as UTF-8 text and parse it

    Parameters
    ----------
    path
        The file to read.
    parse
        The parser for the file's text.

    Returns
    -------
    :
        The result of parsing the file's text.

    Raises
    ------
    ManifestError
        The file cannot be read or decoded, or `parse` rejects its text.
    """
    try:
        return parse(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, configparser.Error) as error:
        # `ValueError` covers `UnicodeDecodeError` and `tomllib.TOMLDecodeError`.
        raise ManifestError(f"Cannot read {path}: {error}") from error


def _parse_toml(text: str) -> dict[str, YamlValue]:
    """
    Parse `pyproject.toml`

    Parameters
    ----------
    text
        The file's text.

    Returns
    -------
    :
        The parsed tables.
    """
    return tomllib.loads(text)


def _parse_cfg(text: str) -> configparser.ConfigParser:
    """
    Parse `setup.cfg`

    Parameters
    ----------
    text
        The file's text.

    Returns
    -------
    :
        The parsed sections.
    """
    # setuptools reads `setup.cfg` without interpolation, so `%` is literal.
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    return parser


def _first(manifest: Manifest, fallback: Manifest) -> Manifest:
    """
    Fill missing metadata values from a fallback source

    Parameters
    ----------
    manifest
        The values that take precedence.
    fallback
        The values used where `manifest` has `None` or an empty value.

    Returns
    -------
    :
        A new manifest that uses each non-empty value from `manifest` and fills the remaining
        values from `fallback`.
    """
    return Manifest(
        name=manifest["name"] or fallback["name"],
        description=manifest["description"] or fallback["description"],
        license=manifest["license"] or fallback["license"],
        authors=manifest["authors"] or fallback["authors"],
        maintainers=manifest["maintainers"] or fallback["maintainers"],
        urls=manifest["urls"] or fallback["urls"],
        requires_python=manifest["requires_python"] or fallback["requires_python"],
        keywords=manifest["keywords"] or fallback["keywords"],
        dependencies=manifest["dependencies"] or fallback["dependencies"],
        optional_dependencies=manifest["optional_dependencies"]
        or fallback["optional_dependencies"],
        scripts=manifest["scripts"] or fallback["scripts"],
        declared_packages=manifest["declared_packages"] or fallback["declared_packages"],
        package_dirs=manifest["package_dirs"] or fallback["package_dirs"],
        discovery_dirs=manifest["discovery_dirs"] or fallback["discovery_dirs"],
        extension_module=manifest["extension_module"] or fallback["extension_module"],
        declared_import_names=manifest["declared_import_names"]
        or fallback["declared_import_names"],
    )


def _from_pyproject(data: YamlMapping) -> Manifest:
    """
    Read the `[project]` table and the build backends' package declarations

    Parameters
    ----------
    data
        The parsed `pyproject.toml`.

    Returns
    -------
    :
        The `[project]` values, with the packages and package directories that build
        backends declare under `[tool]`.
    """
    project = data.mapping("project")
    manifest = empty()
    manifest["name"] = project.string("name")
    manifest["description"] = project.string("description") or ""
    manifest["license"] = _licence(project)
    manifest["authors"] = _people(project.sequence("authors"))
    manifest["maintainers"] = _people(project.sequence("maintainers"))
    manifest["urls"] = _string_values(project.mapping("urls"))
    manifest["requires_python"] = project.string("requires-python") or ""
    manifest["keywords"] = _strings(project.sequence("keywords"))
    manifest["dependencies"] = [
        _dependency(text) for text in _strings(project.sequence("dependencies"))
    ]
    manifest["optional_dependencies"] = {
        str(extra): [_dependency(text) for text in _strings(specs)]
        for extra, specs in project.mapping("optional-dependencies").data.items()
    }
    console = _string_values(project.mapping("scripts"))
    gui = _string_values(project.mapping("gui-scripts"))
    # A command in both tables keeps its console entry.
    manifest["scripts"] = console | {
        name: reference for name, reference in gui.items() if name not in console
    }

    tool = data.mapping("tool")
    setuptools = tool.mapping("setuptools")
    manifest["package_dirs"] = list(_string_values(setuptools.mapping("package-dir")).values())
    packages = setuptools.get("packages")
    manifest["declared_import_names"] = _strings(packages)
    manifest["declared_packages"] += [
        package.replace(".", "/") for package in manifest["declared_import_names"]
    ]
    find = setuptools.mapping("packages").mapping("find")
    if "find" in setuptools.mapping("packages"):
        # setuptools searches the project root when `where` is absent.
        manifest["discovery_dirs"] = find.strings("where") if "where" in find else ["."]
        manifest["package_dirs"] += manifest["discovery_dirs"]
    manifest["extension_module"] = tool.mapping("maturin").string("module-name") or ""
    wheel = tool.mapping("hatch").mapping("build").mapping("targets").mapping("wheel")
    manifest["declared_packages"] += _strings(wheel.sequence("packages"))
    for entry in tool.mapping("poetry").sequence("packages"):
        package = YamlMapping(entry) if isinstance(entry, dict) else YamlMapping()
        include = package.string("include")
        if include is not None:
            source = package.string("from")
            manifest["declared_packages"].append(f"{source}/{include}" if source else include)
    return manifest


def _from_poetry(poetry: YamlMapping) -> Manifest:
    """
    Read the metadata of a Poetry 1.x `[tool.poetry]` table

    Parameters
    ----------
    poetry
        The `[tool.poetry]` table.

    Returns
    -------
    :
        The name, description, authors and the `Repository`, `Homepage` and `Documentation`
        URLs. An author written as `Name <email>` supplies both parts; any other string
        supplies only the name.
    """
    manifest = empty()
    manifest["name"] = poetry.string("name")
    manifest["description"] = poetry.string("description") or ""
    for author in _strings(poetry.sequence("authors")):
        match = _POETRY_PERSON.fullmatch(author)
        name, email = (match[1], match[2]) if match else (author.strip(), "")
        person = Person()
        if name:
            person["name"] = name
        if email:
            person["email"] = email
        manifest["authors"].append(person)
    for key in ("repository", "homepage", "documentation"):
        url = poetry.string(key)
        if url:
            manifest["urls"][key.capitalize()] = url
    return manifest


def _from_setup_cfg(parser: configparser.ConfigParser) -> Manifest:
    """
    Read the `[metadata]` and `[options]` sections of `setup.cfg`

    Parameters
    ----------
    parser
        The parsed `setup.cfg`.

    Returns
    -------
    :
        The name, description, licence, Python requirement, first author, first maintainer
        and URLs. The `url` field becomes the `Repository` URL.
    """

    def metadata(option: str) -> str:
        """
        Read an option from the `[metadata]` section

        Parameters
        ----------
        option
            The option's name.

        Returns
        -------
        :
            The option's value, or an empty string when it is absent.
        """
        return parser.get("metadata", option, fallback="")

    manifest = empty()
    manifest["name"] = metadata("name") or None
    manifest["description"] = metadata("description")
    manifest["license"] = metadata("license")
    manifest["requires_python"] = parser.get("options", "python_requires", fallback="")
    for role in ("author", "maintainer"):
        name = metadata(role)
        if name:
            person = Person(name=name)
            email = metadata(f"{role}_email")
            if email:
                person["email"] = email
            manifest["authors" if role == "author" else "maintainers"] = [person]
    url = metadata("url")
    if url:
        manifest["urls"]["Repository"] = url
    for line in metadata("project_urls").splitlines():
        label, separator, address = line.partition("=")
        if separator:
            manifest["urls"][label.strip()] = address.strip()
    return manifest


def _licence(project: YamlMapping) -> str:
    """
    Read the licence declared in a `[project]` table

    Parameters
    ----------
    project
        The `[project]` table.

    Returns
    -------
    :
        The SPDX identifier of the first OSI-approved licence classifier, or the classifier's
        name if its identifier is unknown. With no such classifier, the `license` expression
        or the text of a `license` table; with neither, an empty string.
    """
    for classifier in _strings(project.sequence("classifiers")):
        if classifier.startswith("License :: OSI Approved ::"):
            name = classifier.split("::")[-1].strip()
            return _LICENCE_CLASSIFIERS.get(name, name)
    # A `license = {file = ...}` table names no licence.
    return project.string("license") or project.mapping("license").string("text") or ""


def _people(entries: list[YamlValue]) -> list[Person]:
    """
    Read the `authors` or `maintainers` of a `[project]` table

    Parameters
    ----------
    entries
        The parsed list.

    Returns
    -------
    :
        A person for each table in the list, retaining its string-valued name and email.
    """
    people: list[Person] = []
    for entry in entries:
        if isinstance(entry, dict):
            fields = YamlMapping(entry)
            person = Person()
            name = fields.string("name")
            email = fields.string("email")
            if name is not None:
                person["name"] = name
            if email is not None:
                person["email"] = email
            people.append(person)
    return people


def _dependency(text: str) -> Dependency:
    """
    Read a PEP 508 requirement

    Parameters
    ----------
    text
        The requirement as declared, such as `rich[jupyter]>=13`.

    Returns
    -------
    :
        The requirement's parts, or `text` as the name with an empty specifier when it is not
        valid PEP 508.
    """
    try:
        requirement = _Requirement(text)
    except InvalidRequirement:
        return Dependency(name=text, specifier="")
    dependency = Dependency(name=requirement.name, specifier=str(requirement.specifier))
    if requirement.marker:
        dependency["marker"] = str(requirement.marker)
    if requirement.extras:
        dependency["extras"] = sorted(requirement.extras)
    return dependency


def _strings(value: YamlValue) -> list[str]:
    """
    Keep the string items in a list

    Parameters
    ----------
    value
        A parsed value of any type.

    Returns
    -------
    :
        The string items in order, or an empty list when `value` is not a list.
    """
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _string_values(table: YamlMapping) -> dict[str, str]:
    """
    Keep the entries with string keys and values

    Parameters
    ----------
    table
        A parsed table.

    Returns
    -------
    :
        The entries whose key and value are both strings, in order.
    """
    return {
        key: value
        for key, value in table.data.items()
        if isinstance(key, str) and isinstance(value, str)
    }
