"""
Project metadata, import names, package locations and GitHub repositories for documentation
builds
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import _manifest
from ._github import GithubRepo
from ._layout import PACKAGE_DIRS
from ._manifest import Manifest, ManifestError

if TYPE_CHECKING:
    from pathlib import Path

    from ._layout import Layout
    from .config import Config

__all__ = ["Project", "locate_package_init", "package_name", "read_manifest"]

# Recognised repository URL labels, casefolded without separators, in preference order.
_REPOSITORY_URL_LABELS = ("repository", "source", "sourcecode", "github", "homepage")

# Exclude common non-package directories from fallback package discovery.
_NON_PACKAGE_DIRS = (
    "tests",
    "test",
    "docs",
    "doc",
    "examples",
    "scripts",
    "build",
    "dist",
    "venv",
    "node_modules",
    "site-packages",
)


@dataclass(frozen=True)
class Project:
    """
    The documented project's metadata, import names, package locations and GitHub repository
    """

    name: str | None
    """
    The distribution name, such as `py-yaml12`, or `None` when the project declares none and
    its root holds no single package directory
    """

    manifest: Manifest
    """The metadata the packaging files declare, empty when they cannot be read"""

    github: GithubRepo | None
    """The project's repository on GitHub, or `None` when no GitHub URL identifies it"""

    module: str | None
    """
    The module to document, such as `yaml12` or `firebird.base`, or `None` when no detection
    rule identifies one
    """

    package_init: Path | None
    """The importable package's `__init__.py`, or `None` when no package directory is found"""

    source_roots: tuple[Path, ...]
    """The package root followed by its existing `src`, `python` and `lib` directories"""

    compiled_extension: bool
    """
    Whether the package root contains `Cargo.toml` or a `.pyi` stub other than `__init__.pyi`
    with no matching `.py` file
    """

    @property
    def importable_name(self) -> str | None:
        """
        The name to import the package by: `module`, else the distribution name with hyphens
        replaced by underscores, else `None`
        """
        return _importable_name(self.module, self.name)

    def search_paths(self) -> list[str | Path]:
        """
        List the directories to search for the package, in order

        Returns
        -------
        :
            The package root and its existing source directories, followed by the current
            entries of `sys.path`.
        """
        return [*self.source_roots, *sys.path]

    @classmethod
    def make(cls, config: Config, layout: Layout) -> Project:
        """
        Read project metadata and locate the package from configuration and project files

        Use the declared distribution name, falling back to the sole non-hidden package
        directory at the package root. A package directory contains `__init__.py`.

        The module can differ from the distribution name: `py-yaml12` may install `yaml12`.
        Use the first available module from these sources, in order:

        1. Use the configured `module`.
        2. Use the first package-root `.pyi` stub other than `__init__.pyi`.
        3. Use the top-level package of Maturin's compiled module.
        4. Use the first package found in setuptools discovery directories, excluding names
           beginning with `.`, `_` or `test`.
        5. Use the first setuptools `packages` entry. Preserve dotted import names such as
           `nspkg.core`; for a path, use its last component.
        6. Use the last component of the first Hatch or Poetry package path. If the path
           names a namespace directory without `__init__.py`, use the subpackage matching
           the rest of the distribution name when it has `__init__.py`. For example, select
           `firebird.base` for distribution `firebird-base`.
        7. Find a package directory for the distribution name and form its dotted name
           relative to the first containing `src`, `python`, `lib` or discovery directory,
           then the package root. Fall back to the package directory's own name.

        Use the configured `repo`, falling back to project URLs labelled `Repository`,
        `Source`, `Source Code`, `GitHub` or `Homepage`, in that order. Ignore case,
        whitespace, hyphens and underscores when matching labels. A selected URL outside
        GitHub leaves the repository unset.

        Parameters
        ----------
        config
            The project's configuration.
        layout
            The project's directories.

        Returns
        -------
        :
            The project's metadata, import names, package locations and GitHub repository
            at the time of the call.
        """
        root = layout.package_root
        manifest = read_manifest(root)
        name = package_name(root, manifest)
        module = _detect_module(config, root, manifest, name)
        importable_name = _importable_name(module, name)
        return cls(
            name=name,
            manifest=manifest,
            github=GithubRepo.parse(config.repo or _repository_url(manifest["urls"])),
            module=module,
            package_init=(
                locate_package_init(root, manifest, importable_name) if importable_name else None
            ),
            source_roots=(
                root,
                *(root / directory for directory in PACKAGE_DIRS if (root / directory).is_dir()),
            ),
            compiled_extension=_holds_compiled_extension(root),
        )


def read_manifest(root: Path) -> Manifest:
    """
    Read project metadata with an empty fallback for packaging errors

    Parameters
    ----------
    root
        The directory holding the packaging files.

    Returns
    -------
    :
        The declared metadata, ignoring an unreadable or invalid `setup.cfg` when
        `pyproject.toml` can be read and parsed. Any other packaging read or parse error
        produces an empty manifest.
    """
    try:
        return _manifest.read(root, ignore_unparsable_setup_cfg=True)
    except ManifestError:
        return _manifest.empty()


def package_name(root: Path, manifest: Manifest) -> str | None:
    """
    Find the package name from declared metadata or the sole package directory

    Parameters
    ----------
    root
        The project's root directory.
    manifest
        The metadata the project's packaging files declare.

    Returns
    -------
    :
        The declared distribution name, falling back to the name of the sole non-hidden
        directory at `root` containing `__init__.py`. Return `None` if neither identifies
        a name.
    """
    if manifest["name"]:
        return manifest["name"]
    packages = [
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "__init__.py").exists() and not path.name.startswith(".")
    ]
    return packages[0] if len(packages) == 1 else None


def _repository_url(urls: dict[str, str]) -> str | None:
    """
    Choose the project URL that names its source repository

    Parameters
    ----------
    urls
        The project URLs, by declared label.

    Returns
    -------
    :
        The URL with the highest-priority recognised label, or `None` when no label is
        recognised. The first declared label wins when labels normalise to the same value.
    """
    # Reverse insertion order so the first declared label wins after normalisation.
    by_label = {_url_label(label): url for label, url in reversed(urls.items())}
    return next((by_label[label] for label in _REPOSITORY_URL_LABELS if label in by_label), None)


def _url_label(label: str) -> str:
    """
    Normalise a project URL label for matching

    Parameters
    ----------
    label
        The label as declared, such as `Source Code`.

    Returns
    -------
    :
        The label casefolded, without spaces, hyphens or underscores, such as `sourcecode`.
    """
    return re.sub(r"[\s_-]", "", label).casefold()


def locate_package_init(root: Path, manifest: Manifest, name: str) -> Path | None:
    """
    Find a package's `__init__.py` in declared and common package locations

    Search declared package paths and setuptools discovery directories before the package
    root and its `python/`, `src/` and `lib/` directories. Accept hyphens or underscores in
    `name`, and dots for a namespace subpackage. Prefer a matching file containing
    `__version__` or `__all__`, then the first matching file. If no matching file exists,
    take the first package in the package root or its `src/`, `python/` or `lib/` directory,
    skipping hidden, private, test, documentation, example, script, build and environment
    directories.

    Parameters
    ----------
    root
        The package root.
    manifest
        The project's declared metadata.
    name
        The distribution or import name of the package to find.

    Returns
    -------
    :
        The path to `__init__.py`, or `None` if no package is found.
    """
    # Package directories may use underscores where distribution names use hyphens.
    normalised = name.replace("-", "_")

    # Declared packages take precedence over candidates in discovery directories.
    candidates: list[Path] = []
    for package in manifest["declared_packages"]:
        candidates.append(root / package)
        if "/" not in package:
            candidates.append(root / "src" / package)
    for directory in manifest["discovery_dirs"]:
        candidates += [root / directory / candidate for candidate in (name, normalised)]

    if "." in name:
        dotted_path = name.replace(".", os.sep)
        candidates += [
            root / dotted_path,
            root / "src" / dotted_path,
            root / "python" / dotted_path,
            root / "lib" / dotted_path,
        ]

    candidates += [
        root / name,
        root / normalised,
        root / "python" / name,
        root / "python" / normalised,
        root / "src" / name,
        root / "src" / normalised,
        root / "lib" / name,
        root / "lib" / normalised,
    ]
    init_files = [
        directory / "__init__.py"
        for directory in candidates
        if directory.is_dir() and (directory / "__init__.py").exists()
    ]

    for init_file in init_files:
        try:
            content = init_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "__version__" in content or "__all__" in content:
            return init_file

    if init_files:
        return init_files[0]

    # The package directory can differ from both the distribution and import names.
    for base in (root, root / "src", root / "python", root / "lib"):
        if not base.is_dir():
            continue
        for item in base.iterdir():
            if (
                item.is_dir()
                and not item.name.startswith((".", "_"))
                and item.name not in _NON_PACKAGE_DIRS
                and (item / "__init__.py").exists()
            ):
                return item / "__init__.py"

    return None


def _detect_module(config: Config, root: Path, manifest: Manifest, name: str | None) -> str | None:
    """
    Detect the importable module to document

    Parameters
    ----------
    config
        The project's configuration.
    root
        The package root.
    manifest
        The project's declared metadata.
    name
        The distribution name, or `None` when the project has none.

    Returns
    -------
    :
        The module selected by the detection rules in `Project.make`, or `None` if none
        identifies a module.
    """
    if config.module:
        return config.module

    for stub in root.glob("*.pyi"):
        if stub.stem != "__init__":
            return stub.stem

    if manifest["extension_module"]:
        # Document the top-level package rather than its compiled extension submodule.
        return manifest["extension_module"].split(".", 1)[0]

    for directory in manifest["discovery_dirs"]:
        base = root / directory
        if not base.is_dir():
            continue
        for item in base.iterdir():
            if (
                item.is_dir()
                and (item / "__init__.py").exists()
                and not item.name.startswith((".", "_", "test"))
            ):
                return item.name

    if manifest["declared_import_names"]:
        # Preserve dotted import names; path entries identify their last directory.
        return manifest["declared_import_names"][0].split("/")[-1]

    if manifest["declared_packages"]:
        declared = manifest["declared_packages"][0]
        package = declared.split("/")[-1]
        path = root / declared
        if path.is_dir() and not (path / "__init__.py").exists():
            distribution = (name or "").replace("-", "_")
            subpackage = distribution.removeprefix(f"{package}_")
            if (
                distribution.startswith(f"{package}_")
                and (path / subpackage / "__init__.py").exists()
            ):
                return f"{package}.{subpackage}"
        return package

    init_file = locate_package_init(root, manifest, name) if name else None
    if init_file is None:
        return None
    package_dir = init_file.parent
    for layout_dir in (
        *(root / directory for directory in PACKAGE_DIRS),
        *(root / directory for directory in manifest["discovery_dirs"]),
        root,
    ):
        if package_dir != layout_dir and package_dir.is_relative_to(layout_dir):
            return ".".join(package_dir.relative_to(layout_dir).parts)
    return package_dir.name


def _importable_name(module: str | None, name: str | None) -> str | None:
    """
    Choose the package's import name

    Parameters
    ----------
    module
        The detected module, or `None`.
    name
        The distribution name, or `None`.

    Returns
    -------
    :
        The detected module, falling back to the distribution name with hyphens replaced
        by underscores, or `None` when neither is known.
    """
    return module or (name.replace("-", "_") if name else None)


def _holds_compiled_extension(root: Path) -> bool:
    """
    Check for packaging files that indicate a compiled extension

    Parameters
    ----------
    root
        The package root.

    Returns
    -------
    :
        `True` if the root contains `Cargo.toml` or a `.pyi` stub other than `__init__.pyi`
        with no matching `.py` file; otherwise `False`.
    """
    return (root / "Cargo.toml").exists() or any(
        stub.stem != "__init__" and not stub.with_suffix(".py").exists()
        for stub in root.glob("*.pyi")
    )
