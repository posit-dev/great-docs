"""
The build steps that run after the site is rendered

These steps write the WebMCP manifest, SEO files and build timings, save the freeze cache, save an API snapshot
for versioned sites and record ownership of files in a separate site directory.

`print_layout_notice` shows migration guidance for documentation at the project root after
a build and before a preview.
"""

from __future__ import annotations

import subprocess
from importlib import metadata
from typing import TYPE_CHECKING

from .._cliref import click as cli_click
from .._utils import record_site_ownership as record_ownership
from .._website.ai_agents import webmcp_manifest as manifest_file
from .._website.seo import site_files
from . import freeze, timings
from .facts import exact_tag
from .site import default_description
from .steps import USER_CODE_ERRORS, Outcome, Skipped

if TYPE_CHECKING:
    from .._layout import Layout
    from .._project import Project
    from ..config import Config
    from .log import BuildLog
    from .pipeline import Run

__all__ = [
    "print_layout_notice",
    "record_site_ownership",
    "save_api_snapshot",
    "save_freeze_cache",
    "seo_files",
    "webmcp_manifest",
    "write_timings",
]


def webmcp_manifest(run: Run, config: Config, layout: Layout, log: BuildLog) -> Outcome:
    """
    Write `gd-webmcp.json` to the root of each rendered version

    Parameters
    ----------
    run
        The current build, which supplies the package's names, metadata and site address.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log, which shows missing or unreadable inputs as warnings.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.webmcp_enabled:
        return Skipped("WebMCP not enabled")
    project = run.project
    name = project.name
    version: str | None = None
    if name:
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    site = manifest_file.SiteInfo(
        name=name,
        title=run.identity.name or name or "",
        description=default_description(config, project),
        version=version,
        repo=project.github.url if project.github else None,
        license=project.manifest["license"] or None,
        install=(f"pip install {name}", f"uv add {name}") if name and project.module else (),
    )
    roots = manifest_file.roots(config, layout, run.identity.base_url)
    written = manifest_file.write(roots, site, warn=log.warn)
    if len(written) > 1:
        return f"{manifest_file.MANIFEST_FILE} written for {len(written)} versions"
    return f"{manifest_file.MANIFEST_FILE} written"


def seo_files(config: Config, layout: Layout, base_url: str | None) -> Outcome:
    """
    Write `sitemap.xml` and `robots.txt` for the rendered site

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    base_url
        The site's canonical address, or `None` when it is unknown.

    Returns
    -------
    :
        The step's result line.
    """
    site_files.write(layout.site_dir, config, base_url, report=print)
    return "sitemap.xml + robots.txt"


def write_timings(
    layout: Layout,
    log: BuildLog,
    page_timings: list[dict[str, object]] | None = None,
    timings_by_version: dict[str, list[dict[str, object]]] | None = None,
    render: dict[str, object] | None = None,
) -> Outcome:
    """
    Write `build-timings.json` to the site

    Parameters
    ----------
    layout
        The project's directories.
    log
        The build log.
    page_timings
        The render time of each page of a single-version site.
    timings_by_version
        The render time of each page, by version.
    render
        How a parallel render of a single-version site went, which the next parallel
        build plans with.

    Returns
    -------
    :
        `None`; the result is a detail line of the previous step.
    """
    path = timings.write(
        layout,
        page_timings=page_timings,
        timings_by_version=timings_by_version,
        render=render,
    )
    if path:
        log.detail(f"Wrote {path.name}")
    return None


def save_freeze_cache(layout: Layout, log: BuildLog) -> Outcome:
    """
    Save the rendered pages' freeze cache for later builds

    Parameters
    ----------
    layout
        The project's directories.
    log
        The build log.

    Returns
    -------
    :
        `None`; the result is a detail line of the previous step.
    """
    n_frozen = freeze.save(layout)
    if n_frozen is not None:
        log.detail(f"Saved freeze cache ({n_frozen} files)")
    return None


def save_api_snapshot(run: Run, config: Config, layout: Layout, log: BuildLog) -> Outcome:
    """
    Save the package's API to `.great-docs/snapshots/<version>.json` for version comparisons

    `<version>` is the exact tag at `HEAD`, or `dev` when there is none or `git` fails or
    takes longer than 5 seconds. The snapshot includes the Click CLI when the CLI reference
    is enabled and the CLI is found. Nothing is saved without a detected package name.

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log, which shows a failure to load the package or write the snapshot as a
        warning.

    Returns
    -------
    :
        `None`; warnings are attributed to the previous listed step.
    """
    try:
        _save_snapshot(config, layout, run.project)
    except USER_CODE_ERRORS as e:
        log.warn(f"Snapshot auto-save failed: {e}")
    return None


def _save_snapshot(config: Config, layout: Layout, project: Project) -> None:
    """
    Save the package's API snapshot, named after the exact tag at `HEAD`

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    project
        The project to snapshot.

    Returns
    -------
    :

    Raises
    ------
    ImportError, SyntaxError, AttributeError, RuntimeError, OSError, griffe.GriffeError
        If the package cannot be loaded or the snapshot cannot be written.
    """
    from .._api_diff import snapshot_from_griffe

    # griffe loads by importable module name, which can differ from the PyPI project name.
    importable_name = project.importable_name
    if not project.name or not importable_name:
        return

    try:
        version = exact_tag(layout.package_root) or "dev"
    except (OSError, subprocess.TimeoutExpired):
        version = "dev"

    snap = snapshot_from_griffe(importable_name, version=version)
    if config.cli_enabled:
        try:
            found = cli_click.find_command(
                importable_name,
                layout.package_root,
                cli_module=config.cli_module,
                cli_name=config.cli_name,
            )
            if found is not None:
                snap.cli_commands = cli_click.extract_snapshot(found.command)
        except USER_CODE_ERRORS:
            pass  # The API snapshot is still useful without the CLI
    snap.save(layout.package_root / ".great-docs" / "snapshots" / f"{version}.json")


def record_site_ownership(layout: Layout) -> Outcome:
    """
    Record the files of a site directory outside the build directory

    Parameters
    ----------
    layout
        The project's directories. Nothing is recorded when the site directory is the build
        directory's `_site`.

    Returns
    -------
    :
        `None`; the step has no result line.
    """
    if layout.site_dir != layout.build_dir / "_site":
        record_ownership(layout.site_dir)
    return None


def print_layout_notice(layout: Layout) -> None:
    """
    Print migration guidance for documentation at the project root

    Parameters
    ----------
    layout
        The project's directories. Nothing is printed for documentation in its own
        directory.

    Returns
    -------
    :
    """
    from .._layout_migration.notice import layout_notice

    notice = layout_notice(layout)
    if notice is not None:
        import click

        click.echo(notice)
