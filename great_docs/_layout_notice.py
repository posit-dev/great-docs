"""
Format migration guidance for documentation using the root layout
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import click

from ._layout import Layout
from ._layout_migration import analyse, select_destination


def _migration_command(layout: Layout, destination: Path) -> list[str]:
    """
    Build a migration command with an explicit configuration and destination
    """
    return [
        "great-docs",
        "migrate-layout",
        "--project-path",
        ".",
        "--config",
        str(layout.config_path.relative_to(layout.package_root)),
        "--to",
        str(destination.relative_to(layout.package_root)),
    ]


def _diagnostic_notice(
    layout: Layout, destination: Path, error: OSError | ValueError | subprocess.SubprocessError
) -> str:
    """
    Give a diagnostic command when migration analysis cannot finish
    """
    command = _migration_command(layout, destination)
    return (
        "\n"
        + click.style(
            "This project has documentation at the root level, which is deprecated.",
            fg="yellow",
            bold=True,
        )
        + "\n\n"
        + click.style("Migration check could not complete", fg="yellow", bold=True)
        + f": {error}\n"
        "Run this command to inspect the migration problem "
        "(the destination may need changing):\n"
        f"{shlex.join([*command, '--dry-run'])}"
    )


def _ready_notice(command: list[str]) -> str:
    """
    Give the migration command when the read-only preview has no blockers
    """
    return (
        "\n"
        + click.style(
            "This project has documentation at the root level, which is deprecated.",
            fg="yellow",
            bold=True,
        )
        + "\n\n"
        "The migration preview found no blocking problems.\n\n"
        + click.style("Run this command to migrate:", fg="cyan", bold=True)
        + "\n\n"
        f"{shlex.join(command)}"
    )


def _blocked_notice(command: list[str]) -> str:
    """
    Give an agent the commands and evidence requirements for a blocked migration
    """
    dry_run = shlex.join([*command, "--dry-run"])
    apply = shlex.join(command)
    return (
        "\n"
        + click.style(
            "This project has documentation at the root level, which is deprecated.",
            fg="yellow",
            bold=True,
        )
        + "\n\n"
        "See the new structure at "
        "https://posit-dev.github.io/great-docs/user-guide/configuration.html#example\n"
        "A scripted migration cannot safely resolve repository-specific changes, "
        "but a coding agent can help.\n\n"
        + click.style("Ask a coding agent with the following prompt:", fg="cyan", bold=True)
        + "\n\n"
        "Migrate this repository to the documentation-directory layout.\n\n"
        "Run the complete dry run from the repository root:\n"
        f"{dry_run}\n\n"
        "Read its complete report. For every blocker and related follow-up, "
        "identify the current source, proposed destination, content owner, "
        "and how affected references resolve before and after the move. "
        "Inspect configuration, pages, Quarto resources, CSS, scripts, "
        "includes, frontmatter, assets, and Git rules where the report points "
        "to them. Treat each item as an investigation; a reference may need "
        "no edit, and an asset may have a consumer the analyser could not find.\n\n"
        "Make only repairs supported by repository evidence. Ask the repository "
        "owner to decide when ownership, authoritative configuration, published "
        "structure, or reconciliation of authored content is unclear. Preserve "
        "content; do not overwrite destinations or bypass blockers.\n\n"
        "Rerun the entire dry run after repairs and resolve every remaining "
        "blocker. After a clean preview, apply with the command's normal confirmation:\n"
        f"{apply}\n"
        "Build the migrated documentation. Compare published pages, navigation, "
        "links, assets, and output paths with the legacy build. Report changes, "
        "verification, follow-up items, and any decisions still needed."
    )


def layout_notice(layout: Layout) -> str | None:
    """
    Return read-only migration guidance for a root-layout project

    Return `None` when the selected configuration already lives in a
    documentation directory. An inspection failure produces a diagnostic
    command without changing the documentation build result.
    """
    if layout.source_dir != layout.package_root:
        return None
    destination = layout.package_root / "docs"
    try:
        destination = select_destination(layout)
        migration = analyse(layout, destination)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return _diagnostic_notice(layout, destination, error)
    command = _migration_command(layout, destination)
    return _blocked_notice(command) if migration.blockers else _ready_notice(command)
