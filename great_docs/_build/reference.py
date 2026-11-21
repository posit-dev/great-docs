"""
Build steps for reference pages and cross-reference links

Write API, Click, Go CLI, Rust CLI and MCP reference pages with their sidebars and navbar
links. Keep the Python API reference on the build state for the text export and
interlinks, and close a failed attempt before retrying. Index documented names to resolve
cross-reference links. An API reference extension error stops the build; only other
failures of dynamic introspection lead to the static-analysis retry.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from .._apiref.spec import ReferenceSpec
from .._cliref import click as cli_click
from .._cliref import render as cli_render
from .._reference import block as reference_block
from .._reference import discovery_cache
from .._reference import sections as reference_sections
from . import quarto
from .facts import source_links
from .steps import USER_CODE_ERRORS, Outcome, Skipped, StepError, print_warning

if TYPE_CHECKING:
    from .._apiref.api_reference import APIReference
    from .._cliref.model import CliCommand
    from .._project.layout import Layout
    from ..config import Config
    from .log import BuildLog
    from .pipeline import Run

__all__ = ["add_api_block", "api", "api_config", "cli", "go_cli", "interlinks", "mcp", "rust_cli"]


def _prepare_imports(config: Config) -> None:
    """
    Make the project's packages importable using Quarto's source paths

    Parameters
    ----------
    config
        The project's configuration.
    """
    for path in quarto.environment(config).get("PYTHONPATH", "").split(os.pathsep):
        if path and path not in sys.path:
            sys.path.insert(0, path)


def add_api_block(run: Run, config: Config, *, refresh: bool) -> None:
    """
    Discover the reference sections and record them in the Quarto project

    Skip the reference when disabled, when the project is not Python, or when no package name
    is detected. Warn for a missing package name. Use an explicit `reference` configuration
    when supplied; otherwise discover sections from the package's exports. When `refresh`
    is false, reuse valid cached sections. Skip when no sections are found. Record the
    reference specification for the remaining build steps.

    Parameters
    ----------
    run
        The build state, updated with the reference specification and the Quarto project
        metadata.
    config
        The project's configuration.
    refresh
        Whether to discover sections even when the cached sections are valid.

    Returns
    -------
    :
    """
    # An explicit `reference: false` disables API reference generation.
    if not config.reference_enabled:
        print("API reference disabled (reference: false), skipping")
        return

    # Non-Python projects have no importable Python package to introspect.
    if not config.is_python_project:
        print("API reference skipped (non-Python project)")
        return

    project = run.project
    if not project.name or not (importable_name := project.importable_name):
        print_warning("Could not detect the package name; skipping the API reference")
        return

    print(f"Adding API reference configuration for package: {project.name}")

    # Report module names that differ even after hyphens are replaced with underscores.
    if importable_name not in (project.name, project.name.replace("-", "_")):
        print(f"Detected module name: {importable_name}")

    if project.compiled_extension:
        print("Detected compiled extension package (PyO3/Rust/Cython)")
        print("Note: The package must be installed (`pip install -e .` or `maturin develop`)")
        print("      for API reference generation.")

    discovery = discovery_cache.sections(run.exports, importable_name, reuse=not refresh)
    run.api_discovery_reused = discovery.reused
    sections = discovery.sections
    if not sections:
        print("No documentable exports found — skipping API reference")
        return

    run.api_spec = ReferenceSpec(importable_name, sections)
    reference_block.configure(config, run.quarto_config, run.api_spec)
    # Navigation allocates collision suffixes before the reference pages are written.
    # Both stages need to resolve the same objects to choose the same labels.
    _prepare_imports(config)
    print("Added API reference configuration")


def api_config(run: Run) -> Outcome:
    """
    Report whether API reference discovery ran, reused the cache or was skipped

    Parameters
    ----------
    run
        The build state, including the discovered reference and cache reuse.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if run.api_spec is None:
        return Skipped("no API reference")
    if run.api_discovery_reused:
        return "Reused cached API discovery"
    return "API reference discovered"


def api(
    run: Run, config: Config, layout: Layout, log: BuildLog
) -> tuple[Outcome, APIReference | None]:
    """
    Write the API reference pages and the inventory of documented objects

    Store each attempt's reference on `run` before generating it, and close an attempt
    that fails. When dynamic introspection fails, retry once with static analysis and
    record the change in the generated Quarto metadata. An API reference
    extension failure propagates without a retry. Leave a successful reference open for
    the text export and interlinks; the build closes it.

    The reference sidebar links only to generated pages, so it leaves out the objects
    that the extension excludes.

    Parameters
    ----------
    run
        The build's reference specification and repository details for source links.
        Receives the reference for later steps and cleanup.
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
    ExtensionError
        If the API reference extension fails during loading, setup, preparation,
        rendering or input fingerprinting.
    """
    spec = run.api_spec
    if spec is None:
        return Skipped("API reference disabled"), None

    from .._apiref._extension_loading import _ExtensionSource
    from .._apiref.api_reference import APIReference

    _prepare_imports(config)

    from .._apiref.resolve import ObjectNotFoundError

    # `ExtensionError` derives from none of these types, so a failing extension escapes
    # both attempts and is never retried with static analysis.
    failures = (*USER_CODE_ERRORS, ObjectNotFoundError)
    links = source_links(config, layout.package_root, run.project.repository, warn=print_warning)

    def build_reference(*, dynamic: bool | None = None) -> APIReference:
        """
        Generate the API reference and record it on the run

        Parameters
        ----------
        dynamic
            The introspection mode for this attempt, or `None` to use the site setting.

        Returns
        -------
        :
            The generated reference. A failed build closes its extension before the error
            propagates.
        """
        ref = APIReference(
            config,
            spec,
            dynamic=dynamic,
            source_links=links,
            extension_source=_ExtensionSource.make(config, layout.source_dir),
            output_root=layout.build_dir,
        )
        run.api_reference = ref
        try:
            ref.build()
        except BaseException:
            ref.close()
            raise
        reference_sections.prune_sidebar(run.quarto_config, ref)
        return ref

    try:
        ref = build_reference()
        return "API reference generated", ref
    except failures as e:
        if not config.dynamic:
            message = f"API reference build failed: {e}"
            raise StepError(message, detail=str(e)) from e
        log.warn(
            "Dynamic introspection failed for a resolved item, retrying with static analysis..."
        )
        log.detail(str(e))
        if "api-reference" in run.quarto_config:
            run.quarto_config["api-reference"]["dynamic"] = False
    try:
        ref = build_reference(dynamic=False)
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
        The build's prepared API reference, or `None` without one. Its inventory
        supplies the names that objects claim, without loading another extension or
        rendering docstring bodies.

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
    # A collision matters only where a page names it, which this step can't see, so name no
    # aliases here. `great-docs lint` reports each reference that hits one.
    if index.dropped:
        log.detail(
            f"{len(index.dropped)} short name(s) are claimed by more than one object; run "
            "`great-docs lint --check cross-refs` to find the references to qualify"
        )
    return f"Indexed {len(index.names)} name(s)"


def cli(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages for the package's Click command-line interface

    Parameters
    ----------
    run
        The current build, which supplies the package and module names and records the
        pages' sidebar and navbar link.
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
    return _write_cli_pages(run, config, layout, cli_info, "CLI")


def go_cli(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages for the project's Go command-line interface

    Parameters
    ----------
    run
        The current build, which records the pages' sidebar and navbar link.
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
    from .._cliref.go import detect_go_cli_project, introspect_cobra_cli

    project = detect_go_cli_project(layout.package_root)
    if not project:
        return Skipped("no Go CLI project detected")
    cli_info = introspect_cobra_cli(project)
    if not cli_info:
        return Skipped("Go CLI introspection failed (is 'go' on PATH?)")
    return _write_cli_pages(run, config, layout, cli_info, "Go CLI", f" ({project.binary_name})")


def rust_cli(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages for the project's Rust command-line interface

    Parameters
    ----------
    run
        The current build, which records the pages' sidebar and navbar link.
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
    from .._cliref.rust import detect_rust_cli_project, introspect_rust_cli

    project = detect_rust_cli_project(layout.package_root)
    if not project:
        return Skipped("no Rust CLI project detected")
    cli_info = introspect_rust_cli(project)
    if not cli_info:
        return Skipped("Rust CLI introspection failed (is 'cargo' on PATH?)")
    return _write_cli_pages(
        run, config, layout, cli_info, "Rust CLI", f" ({project.binary_names[0]})"
    )


def _write_cli_pages(
    run: Run, config: Config, layout: Layout, cli_info: CliCommand, kind: str, suffix: str = ""
) -> Outcome:
    """
    Write CLI reference pages and record their sidebar and the Reference navbar link

    Parameters
    ----------
    run
        The current build, which records the sidebar and navbar link.
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
    cli_files = cli_render.write_pages(config, layout, cli_info, report=print)
    if not cli_files:
        return f"No {kind} pages generated"
    run.contributions.append(cli_render.contribution(config, cli_files))
    run.has_cli_reference = True
    n_pages = cli_render.count_pages(cli_files)
    print(f"Updated sidebar with {n_pages} CLI reference page(s)")
    return f"{n_pages} {kind} reference page(s){suffix}"


def mcp(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write reference pages and a discovery manifest for the project's MCP server

    Parameters
    ----------
    run
        The current build, which supplies the package name and repository and records the
        pages' sidebar.
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
    repo_url = run.project.repository.url if run.project.repository else None
    mcp_files = mcp_build.build_mcp_reference(config, mcp_info, layout, run.project.name, repo_url)
    if not mcp_files:
        return "No MCP pages generated"
    run.contributions.append(mcp_build.contribution(config, mcp_files))
    print(f"Updated sidebar with {cli_render.count_pages(mcp_files)} MCP reference page(s)")
    return f"{len(mcp_info.get('tools', []))} MCP tool page(s) + manifest"
