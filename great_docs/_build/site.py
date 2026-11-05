"""
Site identity and Quarto configuration

Resolve the site's identity, default search description and structured data on each call.
The identity and structured data use the current title in `_quarto.yml`, which can change
during a build.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._website import assembly, quarto_yml
from .._website.identity import Identity
from .._website.seo import description as seo_description
from .._website.seo.structured_data import StructuredData
from .facts import Facts
from .steps import print_warning

if TYPE_CHECKING:
    from .._layout import Layout
    from .._project import Project
    from .._remote import Remote
    from ..config import Config
    from .pipeline import Run

__all__ = ["default_description", "identity", "structured_data", "update_quarto_config"]


def identity(config: Config, layout: Layout, project: Project) -> Identity:
    """
    Resolve the site's name and addresses

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories. Read the site title from the build directory's
        `_quarto.yml` when available.
    project
        The package name and GitHub repository used when the site's name or address is not
        configured.

    Returns
    -------
    :
        The site's identity.
    """
    github = project.github
    return Identity.make(
        config,
        layout.build_dir,
        github.owner if github else None,
        github.name if github else None,
        project.name,
    )


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
    return seo_description.default_description(config, project.manifest["description"])


def structured_data(config: Config, layout: Layout, project: Project) -> StructuredData | None:
    """
    Build the package's JSON-LD description for homepage and reference pages

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    project
        The package metadata to describe.

    Returns
    -------
    :
        The package description with the current site name and canonical address, or `None`
        when structured data is disabled.
    """
    site_identity = identity(config, layout, project)
    return StructuredData.make(config, project.manifest, site_identity.name, site_identity.base_url)


def update_quarto_config(run: Run, config: Config, layout: Layout, *, remote: Remote) -> None:
    """
    Merge Great Docs settings into the build directory's `_quarto.yml`

    Require an existing `_quarto.yml` with `project` and `format.html` mappings. Add render
    scripts, theme settings, resources and navigation from `great-docs.yml`, package metadata
    and GitHub data while preserving unrelated settings. Call again after publishing content
    to register its resources and refresh navigation.

    Parameters
    ----------
    run
        The build state, including API reference availability for the reference switcher.
        Fetch and store repository data if absent; reuse it on later calls.
    config
        The project's configuration.
    layout
        The project's directories.
    remote
        The source of GitHub star and fork counts and the latest release when not already
        stored in the build state.

    Returns
    -------
    :

    Raises
    ------
    FileNotFoundError
        If the build directory has no `_quarto.yml`, or a header include file does not exist.
    KeyError
        If `_quarto.yml` lacks a `project` or `format.html` mapping, including when it is empty.
    """
    build_dir = layout.build_dir
    quarto_config = quarto_yml.read(build_dir)

    repo = run.project.github
    if run.facts is None:
        run.facts = Facts.make(config, repo, remote)

    assembly.assemble(
        quarto_config,
        config,
        layout,
        build_dir,
        repo=repo,
        facts=run.facts,
        identity=identity(config, layout, run.project),
        package_name=run.project.name,
        metadata=run.project.manifest,
        has_api_reference=run.has_api_reference,
        report=print,
        warn=print_warning,
    )

    quarto_yml.write(build_dir, quarto_config)

    print(f"Updated {quarto_yml.path(build_dir)} with great-docs configuration")
