"""
Project names, packaging metadata and GitHub repositories for documentation builds
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import _manifest
from ._github import GithubRepo
from ._manifest import Manifest, ManifestError

if TYPE_CHECKING:
    from pathlib import Path

    from ._layout import Layout
    from .config import Config

__all__ = ["Project", "read_manifest"]

# Recognised repository URL labels, casefolded without separators, in preference order.
_REPOSITORY_URL_LABELS = ("repository", "source", "sourcecode", "github", "homepage")


@dataclass(frozen=True)
class Project:
    """The documented project's distribution name, declared metadata and GitHub repository"""

    name: str | None
    """
    The distribution name, such as `py-yaml12`, or `None` when the project declares none and
    its root holds no single package directory
    """

    manifest: Manifest
    """The metadata the packaging files declare, empty when they cannot be read"""

    github: GithubRepo | None
    """The project's repository on GitHub, or `None` when no GitHub URL identifies it"""

    @classmethod
    def make(cls, config: Config, layout: Layout) -> Project:
        """
        Read the project's facts from its configuration and packaging files

        Use the declared distribution name, falling back to the sole non-hidden package
        directory at the package root. A package directory contains `__init__.py`.

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
            The project's name, declared metadata and GitHub repository at the time of reading.
        """
        package_root = layout.package_root
        manifest = read_manifest(package_root)
        return cls(
            name=manifest["name"] or _sole_package(package_root),
            manifest=manifest,
            github=GithubRepo.parse(config.repo or _repository_url(manifest["urls"])),
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


def _sole_package(root: Path) -> str | None:
    """
    Find the sole non-hidden package directory at a project's root

    Parameters
    ----------
    root
        The project's root directory.

    Returns
    -------
    :
        The directory's name, or `None` unless exactly one non-hidden directory contains
        `__init__.py`.
    """
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
