"""Skill installation and inspection commands"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .._project import manifest as _manifest
from .._project.manifest import ManifestError
from .app import OrderedGroup


@click.group(cls=OrderedGroup)
def skill():
    """Manage AI coding agent skills.

    Install, check, and list SKILL.md files so AI coding agents can
    learn to use your Python package.

    \b
    Quick start:
      great-docs skill install great-docs      # install Great Docs' own skill
      great-docs skill install great-tables    # install from PyPI package
      great-docs skill install pointblank      # works with any GD-powered package
      great-docs skill check                   # verify freshness
      great-docs skill check --update          # auto-update outdated skills
      great-docs skill list great-tables       # see what's bundled
    """


@click.command(name="install")
@click.argument("source", required=False)
@click.option(
    "-g",
    "--global",
    "global_",
    is_flag=True,
    help="Install the skill globally (~/) instead of in the current repository.",
)
@click.option(
    "-p",
    "--path",
    type=str,
    help="Custom path where to install the skill.",
)
@click.option(
    "-d",
    "--detect",
    is_flag=True,
    help="Automatically detect and update existing installations.",
)
@click.option(
    "--agent",
    type=click.Choice(["claude", "copilot", "cursor", "windsurf", "opencode", "codex"]),
    help="Target agent format (auto-detected if not specified).",
)
@click.option(
    "--name",
    "skill_name",
    type=str,
    help="Override the skill name.",
)
def skill_install(
    source: str | None,
    global_: bool,
    path: str | None,
    detect: bool,
    agent: str | None,
    skill_name: str | None,
) -> None:
    """Install skills for AI coding agents.

    SOURCE can be a Python package name or a documentation site URL.
    If omitted, looks for skills in the current package.

    \b
    Examples:
      great-docs skill install                    # current package (pyproject.toml)
      great-docs skill install great-tables       # any installed package
      great-docs skill install polars pointblank  # multiple packages at once
      great-docs skill install https://posit-dev.github.io/great-tables/
      great-docs skill install great-tables --agent claude           # Claude Code
      great-docs skill install great-tables --agent copilot          # GitHub Copilot
      great-docs skill install great-tables --global                 # install to ~/
      great-docs skill install great-tables --path .claude/skills/gt # custom path
      great-docs skill install --detect           # find and refresh all skills
    """
    from .._skills.install import install_skill as _install_skill

    kwargs: dict = {
        "global_": global_,
        "path": path,
        "detect": detect,
        "skill_name": skill_name,
    }

    if agent:
        kwargs["agent"] = agent

    if source:
        if source.startswith(("http://", "https://")):
            kwargs["url"] = source
        else:
            kwargs["package"] = source
    else:
        # Use the current project's declared package name when no source is supplied.
        project_root = Path.cwd()
        pkg_name = _detect_current_package(project_root)
        if pkg_name:
            kwargs["package"] = pkg_name
        else:
            click.echo(
                "Error: No source specified and no package found in current directory.", err=True
            )
            click.echo("Usage: great-docs skill install <package-or-url>", err=True)
            sys.exit(1)

    results = _install_skill(**kwargs)
    if not results:
        sys.exit(1)


@click.command(name="check")
@click.argument("package", required=False)
@click.option(
    "-g",
    "--global",
    "global_",
    is_flag=True,
    help="Only check global installations (in home directory).",
)
@click.option(
    "-l",
    "--local",
    is_flag=True,
    default=True,
    help="Only check local installations (in current repository).",
)
@click.option(
    "-u",
    "--update",
    is_flag=True,
    help="Automatically update any outdated skills found.",
)
def skill_check(
    package: str | None,
    global_: bool,
    local: bool,
    update: bool,
) -> None:
    """Check if installed skills are up to date.

    Scans for installed SKILL.md files and compares their content hash
    with the currently installed package to detect changes.

    \b
    Examples:
      great-docs skill check                # check all installed skills
      great-docs skill check great-tables   # check a specific package
      great-docs skill check --global       # check global installations only
      great-docs skill check --update       # reinstall any that have changed
    """
    from .._skills.install import check_skill as _check_skill

    click.echo("Checking installed skills...")
    results = _check_skill(
        package=package,
        global_=global_,
        local=local,
        update=update,
    )

    if not results:
        click.echo("No installed skills found.")
    else:
        current = sum(1 for r in results if r["status"] == "current")
        outdated = sum(1 for r in results if r["status"] == "outdated")
        updated = sum(1 for r in results if r["status"] == "updated")
        local = sum(1 for r in results if r["status"] == "local")

        click.echo()
        parts = []
        if current:
            parts.append(f"{current} current")
        if outdated:
            parts.append(f"{outdated} outdated")
        if updated:
            parts.append(f"{updated} updated")
        if local:
            parts.append(f"{local} local")
        click.echo(f"Summary: {', '.join(parts)}")


@click.command(name="list")
@click.argument("source", required=False)
@click.option(
    "--url",
    type=str,
    help="Documentation site URL to query for available skills.",
)
def skill_list(source: str | None, url: str | None) -> None:
    """List available skills from a package or URL.

    Shows all SKILL.md files bundled in a package or discoverable at a URL,
    including their names and file paths.

    \b
    Examples:
      great-docs skill list                   # current package (pyproject.toml)
      great-docs skill list great-tables      # any installed package
      great-docs skill list https://posit-dev.github.io/great-tables/
    """
    from .._skills.install import list_skills as _list_skills

    if source:
        if source.startswith(("http://", "https://")):
            url = source
            source = None

    if url:
        click.echo(f"Skills available at {url}:")
        results = _list_skills(url=url)
    elif source:
        click.echo(f"Skills bundled in '{source}':")
        results = _list_skills(package=source)
    else:
        project_root = Path.cwd()
        pkg_name = _detect_current_package(project_root)
        if pkg_name:
            click.echo(f"Skills bundled in '{pkg_name}':")
            results = _list_skills(package=pkg_name)
        else:
            click.echo("Error: No source specified and no package found.", err=True)
            sys.exit(1)

    if not results:
        click.echo("No skills found.")
        sys.exit(1)


def _detect_current_package(project_root: Path) -> str | None:
    """
    Read the package name declared by a project

    Parameters
    ----------
    project_root
        The directory holding the packaging files.

    Returns
    -------
    :
        The distribution name as written, or `None` when the project declares no name or its
        metadata cannot be read.
    """
    try:
        return _manifest.read(project_root)["name"]
    except ManifestError:
        return None


skill.add_command(skill_install)
skill.add_command(skill_check)
skill.add_command(skill_list)
