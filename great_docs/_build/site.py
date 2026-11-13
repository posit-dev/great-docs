"""
Site identity and Quarto configuration

Resolve the site's identity, default search description and structured data from the
project's configuration and metadata. Merge site settings into the build's Quarto
configuration and write it to `_quarto.yml`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._content import metadata
from .._website import assembly, quarto_yml
from .._website.identity import Identity
from .._website.seo.structured_data import StructuredData
from .facts import Facts
from .steps import print_warning

if TYPE_CHECKING:
    from .._project import Project
    from .._project.layout import Layout
    from .._project.remote import Remote
    from ..config import Config
    from .pipeline import Run

__all__ = [
    "default_description",
    "identity",
    "structured_data",
    "update_quarto_config",
    "write_quarto_config",
]


def identity(config: Config, layout: Layout, project: Project) -> Identity:
    """
    Resolve the site's name and addresses

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories, searched for a Go or Rust program whose name supplies
        the fallback site name.
    project
        The package name and repository used when the site's name or address is not
        configured.

    Returns
    -------
    :
        The site's identity.
    """
    return Identity.make(config, layout.package_root, project.repository, project.name)


def default_description(config: Config, project: Project) -> str | None:
    """
    Resolve the site's default search description

    Parameters
    ----------
    config
        The project's configuration.
    project
        The project whose package description supplies the fallback.

    Returns
    -------
    :
        The plain text of `seo.default_description`, or the package description when no
        default is configured. Return `None` when the selected description has no text.
    """
    return metadata.default_description(config, project.manifest["description"])


def structured_data(run: Run, config: Config) -> StructuredData | None:
    """
    Build the package's JSON-LD description for homepage and reference pages

    Parameters
    ----------
    run
        The current build's site identity and package metadata to describe.
    config
        The project's configuration.

    Returns
    -------
    :
        The package description with the site's name and canonical address, or `None` when
        structured data is disabled.
    """
    return StructuredData.make(
        config,
        run.project.manifest,
        run.identity.name,
        run.identity.base_url,
        repo_url=run.project.repository.url if run.project.repository else None,
    )


def update_quarto_config(run: Run, config: Config, layout: Layout, *, remote: Remote) -> None:
    """
    Merge Great Docs settings into the build's Quarto configuration

    Combine `great-docs.yml`, package metadata and GitHub data with recorded build
    contributions to configure render scripts, theme, resources and navigation.
    Apply contributions in build step order.
    Preserve unrelated settings.

    Require `project` and `format.html` mappings in the Quarto configuration.

    Parameters
    ----------
    run
        The build's Quarto configuration to update in place, recorded contributions and
        API reference availability for the reference switcher.
    config
        The project's configuration.
    layout
        The project's directories.
    remote
        The source of GitHub star and fork counts and the latest release.

    Returns
    -------
    :

    Raises
    ------
    FileNotFoundError
        If a header include file does not exist.
    KeyError
        If the Quarto configuration lacks a `project` or `format.html` mapping.
    """
    repo = run.project.repository

    assembly.assemble(
        run.quarto_config,
        config,
        layout,
        repo=repo,
        facts=Facts.make(config, repo, remote),
        identity=run.identity,
        package_name=run.project.name,
        metadata=run.project.manifest,
        has_api_reference=run.has_api_reference,
        has_cli_reference=run.has_cli_reference,
        has_changelog=run.has_changelog,
        has_skills=run.has_skills,
        contributions=run.contributions,
        report=print,
        warn=print_warning,
    )


def write_quarto_config(run: Run, layout: Layout) -> None:
    """
    Write the build's Quarto configuration to `_quarto.yml`

    Parameters
    ----------
    run
        The build state holding the configuration.
    layout
        The project's directories.

    Returns
    -------
    :
    """
    quarto_yml.write(layout.build_dir, run.quarto_config)
