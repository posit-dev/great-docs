"""
Build steps for reference pages and cross-reference links

Write API, Click, Go CLI, Rust CLI and MCP reference pages with their sidebars and navbar
links. Index documented names to resolve cross-reference links.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, cast

from .._cliref import click as cli_click
from .._cliref import render as cli_render
from .._reference import block as reference_block
from .._website import quarto_yml
from . import quarto
from .facts import source_links
from .steps import USER_CODE_ERRORS, Outcome, Skipped, StepError, print_warning

if TYPE_CHECKING:
    from .._apiref.api_reference import APIReference
    from .._cliref.model import CliCommand
    from .._layout import Layout
    from ..config import Config
    from .log import BuildLog
    from .pipeline import Run

__all__ = ["add_api_block", "api", "api_config", "cli", "go_cli", "interlinks", "mcp", "rust_cli"]


def add_api_block(run: Run, config: Config, layout: Layout) -> None:
    """
    Write the API reference configuration to `_quarto.yml`

    Skip the reference when disabled, when the project is not Python, or when no package name
    is detected. Warn for a missing package name. Use an explicit `reference` configuration
    when supplied; otherwise discover sections from the package's exports. Skip when neither
    supplies sections. Record skips and completed export discovery in the build state.

    Parameters
    ----------
    run
        The current build, including API reference availability and export discovery status.
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
    """
    # An explicit `reference: false` disables API reference generation.
    if not config.reference_enabled:
        print("API reference disabled (reference: false), skipping")
        run.has_api_reference = False
        return

    # Non-Python projects have no importable Python package to introspect.
    if not config.is_python_project:
        print("API reference skipped (non-Python project)")
        run.has_api_reference = False
        return

    project = run.project
    if not project.name or not (importable_name := project.importable_name):
        print_warning("Could not detect the package name; skipping the API reference")
        run.has_api_reference = False
        return

    print(f"Adding API reference configuration for package: {project.name}")

    # Report module names that differ even after hyphens are replaced with underscores.
    if importable_name not in (project.name, project.name.replace("-", "_")):
        print(f"Detected module name: {importable_name}")

    if project.compiled_extension:
        print("Detected compiled extension package (PyO3/Rust/Cython)")
        print("Note: The package must be installed (`pip install -e .` or `maturin develop`)")
        print("      for API reference generation.")

    # An explicit `reference` configuration takes precedence over discovered exports.
    sections = run.exports.sections(importable_name)

    # The API reference configuration step skips rediscovery in this build.
    run.api_discovery_done = True

    if not sections:
        print("No documentable exports found — skipping API reference")
        run.has_api_reference = False
        return

    build_dir = layout.build_dir
    quarto_config = quarto_yml.read(build_dir)
    reference_block.configure(config, quarto_config, importable_name, sections)
    quarto_yml.write(build_dir, quarto_config)

    print(f"Added API reference configuration to {quarto_yml.path(build_dir)}")


def api_config(run: Run, config: Config, layout: Layout, *, refresh: bool) -> Outcome:
    """
    Update the API reference configuration from the package's exports

    Reuse the configuration if this build already discovered the exports during preparation.

    Parameters
    ----------
    run
        Build state recording whether the site has an API reference and whether its exports
        have already been discovered.
    config
        The project's configuration.
    layout
        The project's directories.
    refresh
        Whether to rediscover package exports.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not run.has_api_reference:
        return Skipped("no API reference")
    if not refresh:
        return "Using existing config"
    if run.api_discovery_done:
        print("API reference already configured in this build, skipping re-discovery")
    else:
        reference_block.refresh(config, layout.build_dir, run.exports.sections)
    return "API reference refreshed"


def api(
    run: Run, config: Config, layout: Layout, log: BuildLog
) -> tuple[Outcome, APIReference | None]:
    """
    Write the API reference pages and the inventory of documented objects

    When dynamic introspection fails, retry once with static analysis.

    Parameters
    ----------
    run
        Build state recording whether the site has an API reference, with repository details
        for source links.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log.

    Returns
    -------
    :
        The result line or skip reason, and the API reference if one was generated.

    Raises
    ------
    StepError
        If the API reference cannot be generated.
    """
    if not run.has_api_reference:
        return Skipped("API reference disabled"), None

    from .._apiref.api_reference import APIReference

    # Use the same package import paths as Quarto to document the same code.
    for path in quarto.environment(config).get("PYTHONPATH", "").split(os.pathsep):
        if path and path not in sys.path:
            sys.path.insert(0, path)

    from .._apiref.resolve import ObjectNotFoundError

    failures = (*USER_CODE_ERRORS, ObjectNotFoundError)
    build_dir = layout.build_dir
    quarto_yml_path = str(quarto_yml.path(build_dir))
    repo_url = run.project.github.url if run.project.github else None
    links = source_links(config, layout.package_root, repo_url, warn=print_warning)
    try:
        ref = APIReference(quarto_yml_path, links)
        ref.build()
        return "API reference generated", ref
    except failures as e:
        if not config.dynamic:
            message = f"API reference build failed: {e}"
            raise StepError(message, detail=str(e)) from e
        log.warn(
            "Dynamic introspection failed for a resolved item, retrying with static analysis..."
        )
        log.detail(str(e))
        with quarto_yml.edit(build_dir) as quarto_config:
            if "api-reference" in quarto_config:
                quarto_config["api-reference"]["dynamic"] = False
    try:
        ref = APIReference(quarto_yml_path, links)
        ref.build()
    except failures as e:
        raise StepError(f"API reference build failed: {e}") from e
    return "API reference generated (static analysis)", ref


def interlinks(
    run: Run,
    config: Config,
    layout: Layout,
    log: BuildLog,
    *,
    api_reference: APIReference | None,
) -> Outcome:
    """
    Write the index that resolves cross-reference links to documented names

    Parameters
    ----------
    run
        The current build, which supplies the package name.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log.
    api_reference
        The project's API reference, if it has one.

    Returns
    -------
    :
        The step's result line.
    """
    from .._interlinks import AliasClaims, build_project_index

    index, notes = build_project_index(
        layout.build_dir,
        config,
        run.project.name or "",
        AliasClaims.make(api_reference.items) if api_reference is not None else AliasClaims(),
    )
    for note in notes:
        log.detail(note)
    for alias, targets in sorted(index.dropped.items()):
        log.detail(f"'{alias}' is ambiguous ({', '.join(targets)}); references to it stay unlinked")
    return f"Indexed {len(index.names)} name(s)"


def cli(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages for the package's Click command-line interface

    Parameters
    ----------
    run
        The current build, which supplies the package and module names.
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.cli_enabled:
        return Skipped("CLI not enabled")
    package_name = run.project.name
    module = run.project.importable_name
    if not package_name or not module:
        return Skipped("no package detected")
    cli_info = cli_click.discover(
        module,
        layout.package_root,
        cli_module=config.cli_module,
        cli_name=config.cli_name,
        display_name=package_name,
        report=print,
    )
    if not cli_info:
        return Skipped("no Click CLI found")
    return _write_cli_pages(config, layout, cli_info, "CLI")


def go_cli(config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages for the project's Go command-line interface

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.go_cli_enabled:
        return Skipped("Go CLI not enabled")
    from .._cliref.go import (
        detect_go_cli_project,
        introspect_cobra_cli,  # pyright: ignore[reportUnknownVariableType]
    )

    project = detect_go_cli_project(layout.package_root)
    if not project:
        return Skipped("no Go CLI project detected")
    # The introspection module types the command tree as a plain `dict`.
    cli_info = cast("CliCommand | None", introspect_cobra_cli(project))
    if not cli_info:
        return Skipped("Go CLI introspection failed (is 'go' on PATH?)")
    return _write_cli_pages(config, layout, cli_info, "Go CLI", f" ({project.binary_name})")


def rust_cli(config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages for the project's Rust command-line interface

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.rust_cli_enabled:
        return Skipped("Rust CLI not enabled")
    from .._cliref.rust import (
        detect_rust_cli_project,
        introspect_rust_cli,  # pyright: ignore[reportUnknownVariableType]
    )

    project = detect_rust_cli_project(layout.package_root)
    if not project:
        return Skipped("no Rust CLI project detected")
    # The introspection module types the command tree as a plain `dict`.
    cli_info = cast("CliCommand | None", introspect_rust_cli(project))
    if not cli_info:
        return Skipped("Rust CLI introspection failed (is 'cargo' on PATH?)")
    return _write_cli_pages(config, layout, cli_info, "Rust CLI", f" ({project.binary_names[0]})")


def _write_cli_pages(
    config: Config, layout: Layout, cli_info: CliCommand, kind: str, suffix: str = ""
) -> Outcome:
    """
    Write CLI reference pages and add their sidebar and the Reference navbar link

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    cli_info
        The command tree to document.
    kind
        The interface label in the result line, such as `"Go CLI"`.
    suffix
        Text appended to the result line, such as the binary's name.

    Returns
    -------
    :
        The step's result line.
    """
    build_dir = layout.build_dir
    cli_files = cli_render.write_pages(config, build_dir, cli_info, report=print)
    if not cli_files:
        return f"No {kind} pages generated"
    with quarto_yml.edit(build_dir) as quarto_config:
        quarto_yml.apply(quarto_config, cli_render.contribution(config, cli_files), config)
    n_pages = cli_render.count_pages(cli_files)
    print(f"Updated sidebar with {n_pages} CLI reference page(s)")
    return f"{n_pages} {kind} reference page(s){suffix}"


def mcp(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages and a discovery manifest for the project's MCP server

    Parameters
    ----------
    run
        The current build, which supplies the package name and repository.
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.mcp_enabled:
        return Skipped("MCP not enabled")
    from .._mcpref import build as mcp_build

    mcp_info = mcp_build.discover_server(config, run.project.importable_name)
    if not mcp_info:
        return Skipped("no MCP server found")
    repo_url = run.project.github.url if run.project.github else None
    build_dir = layout.build_dir
    mcp_files = mcp_build.build_mcp_reference(
        config, mcp_info, build_dir, run.project.name, repo_url
    )
    if not mcp_files:
        return "No MCP pages generated"
    with quarto_yml.edit(build_dir) as quarto_config:
        quarto_yml.apply(quarto_config, mcp_build.contribution(config, mcp_files), config)
    print(f"Updated sidebar with {cli_render.count_pages(mcp_files)} MCP reference page(s)")
    return f"{len(mcp_info.get('tools', []))} MCP tool page(s) + manifest"
