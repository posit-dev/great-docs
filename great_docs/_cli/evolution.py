"""API evolution commands"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .._build.steps import PROJECT_ERRORS, USER_CODE_ERRORS, BuildError
from .._project.layout import Layout
from .._reference.exports import Exports
from . import options as _options


@click.command("api-diff")
@click.argument("old_version")
@click.argument("new_version")
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--package",
    help="Python package name (auto-detected from pyproject.toml if omitted)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--graph",
    is_flag=True,
    help="Show dependency graph as Mermaid diagram for the NEW version",
)
@click.option(
    "--timeline",
    is_flag=True,
    help="Show API surface growth timeline across all version tags",
)
@click.option(
    "--symbol",
    help="Track a single symbol across versions (shows signature history)",
)
@click.option(
    "--changes-only",
    is_flag=True,
    help="With --symbol, show only versions where the symbol changed",
)
@click.option(
    "--table",
    is_flag=True,
    help="With --symbol, show parameter evolution as a table",
)
@click.option(
    "--html",
    is_flag=True,
    help="With --symbol --table, output HTML (with disclosure wrapper)",
)
@_options.config_option
def api_diff_cmd(
    old_version: str,
    new_version: str,
    project_path: str | None,
    package: str | None,
    json_output: bool,
    graph: bool,
    timeline: bool,
    symbol: str | None,
    changes_only: bool,
    table: bool,
    html: bool,
    config_path: str | None = None,
) -> None:
    """Compare the public API between two versions.

    Analyzes how the API surface changed between 'OLD_VERSION' and
    'NEW_VERSION' (git tags). Detects added, removed, and changed symbols,
    tracks parameter changes, and flags breaking changes with migration
    hints.

    \b
    Use 'HEAD' as 'NEW_VERSION' to compare against the working tree.

    \b
    Examples:
      great-docs api-diff v0.1.0 v0.2.0
      great-docs api-diff v1.0.0 HEAD
      great-docs api-diff v0.9.0 v1.0.0 --json
      great-docs api-diff v0.1.0 v0.2.0 --graph
      great-docs api-diff v0.1.0 HEAD --timeline
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs --changes-only
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs --table
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs --table --html
    """
    import json
    import shutil

    from .._api_evolution.compare import api_diff
    from .._api_evolution.history import build_dependency_graph, build_timeline, symbol_history
    from .._api_evolution.render import (
        evolution_table_html,
        evolution_table_text,
        timeline_to_mermaid,
    )
    from .._api_evolution.snapshot import (
        _detect_package_name,
        snapshot_at_tag,
        snapshot_from_griffe,
    )

    project_root = Path(project_path) if project_path else Path.cwd()
    importable_name = package or _detect_package_name(
        project_root, Path(config_path) if config_path else None
    )

    try:
        # --- Symbol history mode ---
        if symbol:
            from .._api_evolution.snapshot import list_version_tags

            all_tags = list_version_tags(project_root)
            # Filter to tags between old_version and new_version (inclusive)
            try:
                start_idx = all_tags.index(old_version)
            except ValueError:
                start_idx = 0
            try:
                end_idx = all_tags.index(new_version) + 1
            except ValueError:
                end_idx = len(all_tags)
            selected_tags = all_tags[start_idx:end_idx]

            if not selected_tags:
                click.echo(
                    f"No version tags found between {old_version} and {new_version}.",
                    err=True,
                )
                sys.exit(1)

            hist = symbol_history(
                project_root, symbol, package_name=importable_name, tags=selected_tags
            )
            if hist is None:
                click.echo("Could not determine package name.", err=True)
                sys.exit(1)

            if json_output:
                click.echo(json.dumps(hist.to_dict(changes_only=changes_only), indent=2))
            elif table:
                if html:
                    click.echo(
                        evolution_table_html(hist, changes_only=changes_only, disclosure=True)
                    )
                else:
                    click.echo(evolution_table_text(hist, changes_only=changes_only))
            else:
                entries = hist.changed_entries if changes_only else hist.entries
                term_width = shutil.get_terminal_size((80, 24)).columns
                sep = "═" * min(term_width, 60)
                thin = "─" * min(term_width, 60)

                click.echo(f"\n{sep}")
                click.echo(f"Symbol History: {hist.symbol_name}")
                click.echo(f"Package: {hist.package_name}")
                if changes_only:
                    click.echo("Showing only versions with changes")
                click.echo(sep)

                if not entries:
                    click.echo("\n  (no entries)")
                else:
                    for entry in entries:
                        click.echo(f"\n{thin}")
                        if entry.present:
                            tag = ""
                            if entry.change:
                                if entry.change.is_breaking:
                                    tag = "  ⚠ BREAKING"
                                elif entry.change.change_type == "added":
                                    tag = "  ✚ NEW"
                                else:
                                    tag = "  ∆ CHANGED"
                            click.echo(f"  {entry.version}{tag}")
                            click.echo(f"    {entry.signature}")
                            if entry.change and entry.change.details:
                                for detail in entry.change.details:
                                    click.echo(f"      {detail}")
                        else:
                            click.echo(f"  {entry.version}  ✖ NOT PRESENT")
                            if entry.change and entry.change.details:
                                for detail in entry.change.details:
                                    click.echo(f"      {detail}")

                click.echo(f"\n{sep}\n")
            return

        # --- Timeline mode ---
        if timeline:
            tl = build_timeline(project_root, importable_name)
            if not tl:
                click.echo("No version tags found or could not build snapshots.", err=True)
                sys.exit(1)
            if json_output:
                click.echo(json.dumps(tl, indent=2))
            else:
                click.echo(timeline_to_mermaid(tl))
            return

        # --- Diff ---
        result = api_diff(project_root, old_version, new_version, package_name=importable_name)

        if result is None:
            click.echo(
                "Could not build API snapshots. Check that the tags exist and the "
                "package source is present at those versions.",
                err=True,
            )
            sys.exit(1)

        # --- Graph mode ---
        if graph:
            from great_docs._reference import documented as documented_reference

            package_exports = Exports.make(
                Layout.make(project_root, Path(config_path) if config_path else None)
            )
            project = package_exports.project
            documented = (
                documented_reference.symbol_names(
                    package_exports.config,
                    importable_name=project.module or result.package_name.replace("-", "_"),
                    search_paths=project.search_paths(),
                    create_sections=package_exports.sections,
                )
                or None
            )
            # Build graph for the new version
            if new_version.upper() == "HEAD":
                snap = snapshot_from_griffe(
                    result.package_name, version="HEAD", documented_names=documented
                )
            else:
                snap = snapshot_at_tag(
                    project_root, new_version, result.package_name, documented_names=documented
                )
            if snap is None:
                click.echo("Could not build snapshot for graph.", err=True)
                sys.exit(1)
            dep_graph = build_dependency_graph(snap)
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "nodes": dep_graph.nodes,
                            "inheritance": [
                                {"child": e.child, "parent": e.parent}
                                for e in dep_graph.inheritance
                            ],
                        },
                        indent=2,
                    )
                )
            else:
                click.echo(dep_graph.to_mermaid())
            return

        # --- JSON output ---
        if json_output:
            click.echo(json.dumps(result.to_dict(), indent=2))
            return

        # --- Text output ---
        term_width = shutil.get_terminal_size((80, 24)).columns
        sep = "═" * min(term_width, 60)
        thin = "─" * min(term_width, 60)

        click.echo(f"\n{sep}")
        click.echo(f"API Diff: {result.old_version} → {result.new_version}")
        click.echo(f"Package: {result.package_name}")
        click.echo(sep)

        # Summary
        click.echo(
            f"\n  Added: {len(result.added)}  │  "
            f"Removed: {len(result.removed)}  │  "
            f"Changed: {len(result.changed)}  │  "
            f"Breaking: {len(result.breaking_changes)}"
        )

        if not result.added and not result.removed and not result.changed:
            click.echo("\n✅ No API changes detected.")
            return

        # Added
        if result.added:
            click.echo(f"\n{thin}")
            click.echo(f"  ✚ Added ({len(result.added)})")
            click.echo(thin)
            for c in result.added:
                click.echo(f"    + {c.symbol}")

        # Removed
        if result.removed:
            click.echo(f"\n{thin}")
            click.echo(f"  ✖ Removed ({len(result.removed)})  [BREAKING]")
            click.echo(thin)
            for c in result.removed:
                click.echo(f"    - {c.symbol}")
                if c.migration_hint:
                    click.echo(f"      hint: {c.migration_hint}")

        # Changed
        if result.changed:
            click.echo(f"\n{thin}")
            click.echo(f"  ∆ Changed ({len(result.changed)})")
            click.echo(thin)
            for c in result.changed:
                label = "  ⚠ BREAKING" if c.is_breaking else ""
                click.echo(f"    ~ {c.symbol}{label}")
                for detail in c.details:
                    click.echo(f"        {detail}")
                if c.migration_hint:
                    click.echo(f"        hint: {c.migration_hint}")

        # Breaking summary
        if result.has_breaking_changes:
            click.echo(f"\n{sep}")
            click.echo(f"⚠  {len(result.breaking_changes)} breaking change(s) detected")
            click.echo(sep)

        click.echo()

    except (*PROJECT_ERRORS, *USER_CODE_ERRORS) as e:
        if json_output:
            click.echo(json.dumps({"status": "error", "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--check",
    is_flag=True,
    help="Validate version configuration and exit with non-zero on errors",
)
@_options.config_option
def versions(project_path: str | None, check: bool, config_path: str | None = None) -> None:
    """List configured documentation versions.

    Shows the multi-version documentation configuration from 'great-docs.yml',
    including version tags, labels, and status indicators.

    \b
    Examples:
      great-docs versions              # List all configured versions
      great-docs versions --check      # Validate configuration
    """
    from great_docs._versions.model import get_latest_version, parse_versions_config

    try:
        project_root = Path(project_path or ".").resolve()
        layout = Layout.make(project_root, Path(config_path) if config_path else None)
        project_root = layout.package_root
        cfg = layout.load_config()

        if not cfg.has_versions:
            click.echo("No versions configured in great-docs.yml.")
            click.echo("Add a 'versions:' list to enable multi-version docs.")
            return

        try:
            entries = parse_versions_config(cfg.versions)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

        if check:
            click.echo(f"✓ {len(entries)} version(s) configured")
            latest = get_latest_version(entries)
            if latest:
                click.echo(f"  Latest: {latest.tag} ({latest.label})")
            else:
                click.echo("  Warning: no version marked as latest", err=True)
                sys.exit(1)
            return

        # Table header
        click.echo(f"  {'TAG':<12} {'LABEL':<20} {'STATUS':<16} {'API SOURCE'}")
        click.echo(f"  {'─' * 12} {'─' * 20} {'─' * 16} {'─' * 24}")

        for v in entries:
            status = "—"
            if v.latest:
                status = "latest ✓"
            elif v.prerelease:
                status = "prerelease"
            elif v.eol:
                status = "eol"

            api_source = "live introspection"
            if v.api_snapshot:
                api_source = v.api_snapshot
            elif v.git_ref:
                api_source = f"git tag: {v.git_ref}"

            click.echo(f"  {v.tag:<12} {v.label:<20} {status:<16} {api_source}")

        click.echo()

    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command("api-snapshot")
@click.argument("version_tag", required=False)
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--package",
    help="Python package name (auto-detected from 'pyproject.toml' if omitted)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    help="Output file path (default: '.great-docs/snapshots/<version>.json')",
)
@click.option(
    "--all-tags",
    is_flag=True,
    help="Snapshot all version tags in the repository",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing snapshot files",
)
@_options.config_option
def api_snapshot_cmd(
    version_tag: str | None,
    project_path: str | None,
    package: str | None,
    output: str | None,
    all_tags: bool,
    force: bool,
    config_path: str | None = None,
) -> None:
    """Capture a JSON snapshot of a package's public API.

    Snapshots record every public symbol, its parameters, type annotations,
    and other metadata. They are used to build versioned API reference pages
    and compute diff annotations without needing access to old source code.

    \b
    With no arguments, snapshot the *current* working-tree API:
      'great-docs api-snapshot'

    \b
    Snapshot a specific git tag:
      'great-docs api-snapshot v1.0.0'

    \b
    Snapshot all version tags at once:
      'great-docs api-snapshot --all-tags'

    \b
    Snapshots are saved to '.great-docs/snapshots/<version>.json' by default.
    """
    from .._api_evolution.snapshot import (
        _detect_package_name,
        list_version_tags,
        snapshot_at_tag,
        snapshot_from_griffe,
    )

    project_root = Path(project_path) if project_path else Path.cwd()

    # Resolve package name
    pkg_name = package or _detect_package_name(
        project_root, Path(config_path) if config_path else None
    )
    if not pkg_name:
        click.echo(
            "Could not detect package name. Pass --package or add [project] "
            "name to pyproject.toml.",
            err=True,
        )
        sys.exit(1)

    from great_docs._reference import documented as documented_reference

    try:
        package_exports = Exports.make(
            Layout.make(project_root, Path(config_path) if config_path else None)
        )
        project = package_exports.project
        documented = (
            documented_reference.symbol_names(
                package_exports.config,
                importable_name=project.module or pkg_name.replace("-", "_"),
                search_paths=project.search_paths(),
                create_sections=package_exports.sections,
            )
            or None
        )
    except BuildError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Default snapshot directory
    snap_dir = project_root / ".great-docs" / "snapshots"

    # Determine which versions to snapshot
    if all_tags:
        tags = list_version_tags(project_root)
        if not tags:
            click.echo("No version tags found in repository.", err=True)
            sys.exit(1)
    elif version_tag:
        tags = [version_tag]
    else:
        # Current working tree
        tags = ["HEAD"]

    saved = 0
    failed = 0

    for tag in tags:
        # Determine output path
        if output and len(tags) == 1:
            out_path = Path(output)
        else:
            label = tag if tag != "HEAD" else "dev"
            out_path = snap_dir / f"{label}.json"

        if out_path.exists() and not force:
            click.echo(f"  ⏭  {tag}: {out_path} already exists (use --force to overwrite)")
            continue

        try:
            if tag == "HEAD":
                snap = snapshot_from_griffe(pkg_name, version="dev", documented_names=documented)
            else:
                snap = snapshot_at_tag(project_root, tag, pkg_name, documented_names=documented)

            if snap is None:
                click.echo(f"  ✗  {tag}: could not build snapshot", err=True)
                failed += 1
                continue

            snap.save(out_path)
            click.echo(f"  ✓  {tag}: {snap.symbol_count} symbols → {out_path}")
            saved += 1

        except USER_CODE_ERRORS as e:
            click.echo(f"  ✗  {tag}: {e}", err=True)
            failed += 1

    click.echo()
    if saved:
        click.echo(f"Saved {saved} snapshot(s).")
    if failed:
        click.echo(f"Failed: {failed}")
        sys.exit(1)
