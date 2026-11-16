"""Project setup, migration and discovery commands"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from .._build.steps import PROJECT_ERRORS, USER_CODE_ERRORS
from .._project import Project
from .._project.layout import CONVENTIONAL_DOC_DIRS, Layout, _find_package_root
from .._project.remote import HttpRemote
from .._project.scaffold import update_gitignore
from .._reference.exports import Exports
from .._website import changelog as changelog_page
from .._website import quarto_yml
from ..core import GreatDocs
from . import options as _options

if TYPE_CHECKING:
    from .._layout_migration import Migration, Move, Note


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Delete existing great-docs.yml and generate a fresh default config",
)
@_options.config_option
def init(project_path: str | None, force: bool, config_path: str | None = None) -> None:
    """
    Initialise documentation in your project

    Creates a fresh 'docs/great-docs.yml' configuration file with discovered
    package exports and sensible defaults. Refuses to run if
    the selected configuration already exists (use '--force' to reset).

    \b
    • Creates 'docs/great-docs.yml' with discovered API exports
    • Auto-detects your package name and public API
    • Updates .gitignore to exclude the build directory
    • Detects docstring style (numpy, google, sphinx)

    After init, customise 'docs/great-docs.yml' then use 'great-docs build'
    for all subsequent builds. You should never need to run
    'great-docs init' again unless you want to completely reset your
    configuration.

    \b
    Examples:
      great-docs init                       # Initialize in current directory
      great-docs init --force               # Reset config to defaults
      great-docs init --project-path ../pkg # Initialize in another project
    """
    try:
        docs = GreatDocs(project_path=project_path, config_path=config_path, create=True)
        docs.install(force=force)
    except (*PROJECT_ERRORS, *USER_CODE_ERRORS, EOFError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@_options.config_option
def uninstall(project_path: str | None, config_path: str | None = None) -> None:
    """
    Remove documentation configuration and generated output

    This command removes the great-docs configuration and build directory:

    \b
    • Deletes the selected configuration, normally 'docs/great-docs.yml'
    • Removes its generated Quarto projects and deployment output

    Your source files ('docs/user_guide/', 'README.md', etc.) are preserved.

    \b
    Examples:
      great-docs uninstall                  # Remove from current project
    """
    try:
        docs = GreatDocs(project_path=project_path, config_path=config_path)
        docs.uninstall()
    except (*PROJECT_ERRORS, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing great-docs.yml without prompting",
)
@_options.config_option
def config(project_path: str | None, force: bool, config_path: str | None = None) -> None:
    """
    Generate a documentation configuration file

    Creates 'docs/great-docs.yml' with all available options documented.
    The generated file contains commented examples for each setting.

    \b
    Examples:
      great-docs config                     # Generate docs/great-docs.yml
      great-docs config --force             # Overwrite existing file
      great-docs config --project-path ../pkg
    """
    from pathlib import Path

    from ..config import create_default_config

    try:
        project_root = Path(project_path) if project_path else Path.cwd()
        layout = Layout.make(project_root, Path(config_path) if config_path else None, create=True)
        config_path = layout.config_path

        if config_path.exists() and not force:
            if not click.confirm(
                f"⚠️  Configuration file already exists at {config_path}\n   Overwrite it?"
            ):
                click.echo("Cancelled.")
                return

        config_content = create_default_config()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_content, encoding="utf-8")
        update_gitignore(layout, report=click.echo)
        click.echo(f"✓ Created {config_path}")
        click.echo("\nEdit this file to customize your documentation settings.")
        click.echo("See https://posit-dev.github.io/great-docs/user-guide/configuration.html")

    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _count_phrase(count: int, singular: str, plural: str) -> str:
    """Render a noun phrase followed by its count in parentheses"""
    return f"{singular if count == 1 else plural} ({count})"


def _print_migration(migration: Migration) -> None:
    """Show every proposed move, file edit, needs-review item, and blocker"""
    import difflib

    root = migration.package_root
    if migration.moves:
        click.echo(
            click.style(
                _count_phrase(
                    len(migration.moves),
                    "File / Folder to Move",
                    "Files / Folders to Move",
                ),
                bold=True,
            )
        )
        for move in migration.moves:
            source = move.source.relative_to(root)
            destination = move.destination.relative_to(root)
            click.echo(f"  {source} {click.style('->', dim=True)} {destination}")
        click.echo()
    if migration.edits:
        click.echo(
            click.style(
                _count_phrase(
                    len(migration.edits),
                    "File to be Edited",
                    "Files to be Edited",
                ),
                bold=True,
            )
        )
        for edit in migration.edits:
            path = str(edit.path.relative_to(root))
            click.echo(f"  {'Create' if edit.before is None else 'Update'} {path}")
            try:
                before = (edit.before or b"").decode("utf-8")
                after = edit.after.decode("utf-8")
            except UnicodeError:
                click.echo(
                    f"    Write {len(edit.after)} bytes; preserve the original for recovery."
                )
            else:
                for line in difflib.unified_diff(
                    before.splitlines(), after.splitlines(), fromfile=path, tofile=path, lineterm=""
                ):
                    if line.startswith("+++") or line.startswith("---"):
                        click.echo(line)
                    elif line.startswith("+"):
                        click.echo(click.style(line, fg="green"))
                    elif line.startswith("-"):
                        click.echo(click.style(line, fg="red"))
                    else:
                        click.echo(line)
        click.echo()
    _print_notes(
        _count_phrase(
            len(migration.follow_up),
            "File to Review",
            "Files to Review",
        ),
        migration.follow_up,
        "yellow",
        root=root,
    )
    _print_notes(
        _count_phrase(
            len(migration.blockers),
            "Blocking Problem",
            "Blocking Problems",
        ),
        migration.blockers,
        "red",
        root=root,
        err=True,
        blocking=True,
    )


# Categories backed by exactly one message template, where nothing but the
# path (and any fixed trailing detail) varies between notes. Their category
# name already reads as the shared action sentence, so items show only the
# part that actually varies (see `_subject`) instead of repeating it.
_SUBJECT_ONLY_CATEGORIES = frozenset(
    {
        "Scripts and Notebooks to Verify",
        "reStructuredText Files to Check",
        "Terminal Recordings to Check",
        "Package Files Mixed Into Docs",
        "Already Migrated",
        "Relocation Not Supported",
        "References Outside the Move",
        "Old Output Paths to Update",
        "References to Edit Before Migrating",
    }
)

# Categories whose notes carry a line and snippet, but where the snippet is
# always some boilerplate variant (e.g. "```{python}") that adds nothing
# beyond "there's a code block here" — show the location without it.
_SNIPPET_SUPPRESSED_CATEGORIES = frozenset({"Code Blocks to Verify"})


def _subject(note: "Note", root: Path) -> str:
    """The relative path (in red) plus any fixed detail that followed it in the message"""
    assert note.path is not None
    path_text = str(note.path)
    offset = note.rfind(path_text)
    suffix = note[offset + len(path_text) :] if offset != -1 else ""
    return click.style(os.path.relpath(note.path, root), fg="red") + suffix


def _highlight_path(note: "Note", root: Path) -> str:
    """The note's message with its path swapped for a red, relative version"""
    assert note.path is not None
    if note.path == root or not note.path.is_relative_to(root):
        message = str(note)
        path_text = str(note.path)
    else:
        message = str(note).replace(str(root) + os.sep, "")
        path_text = os.path.relpath(note.path, root)
    display_path = click.style(os.path.relpath(note.path, root), fg="red")
    return message.replace(path_text, display_path, 1)


def _relocate_note(note: "Note", moves: "tuple[Move, ...]") -> "Note":
    """Point a note at its file's post-move location, once a migration has applied"""
    from .._layout_migration.model import Note, moved_path

    if note.path is None:
        return note
    moved = moved_path(note.path, moves)
    if moved == note.path:
        return note
    old_text = str(note.path)
    message = note.replace(old_text, str(moved)) if old_text in note else str(note)
    return Note(message, category=note.category, path=moved, line=note.line, snippet=note.snippet)


def _print_notes(
    label: str,
    notes: "tuple[Note, ...]",
    color: str,
    *,
    root: Path,
    err: bool = False,
    blocking: bool = False,
) -> None:
    """Print a category-grouped section of migration notes under a pre-formatted count header"""
    if not notes:
        return
    click.echo(click.style(label, bold=True, fg=color), err=err)
    if blocking:
        click.echo(
            "Resolve every blocking problem, then run great-docs migrate-layout --dry-run "
            "again. The migration will not apply while any blocker remains.",
            err=err,
        )
    categories: dict[str, list[Note]] = {}
    for note in notes:
        categories.setdefault(note.category, []).append(note)
    for category, items in categories.items():
        click.echo(click.style(f"  {category} ({len(items)})", bold=True), err=err)
        for note in items:
            if note.path is not None and note.line is not None and note.snippet is not None:
                display_path = click.style(os.path.relpath(note.path, root), fg="red")
                if category in _SNIPPET_SUPPRESSED_CATEGORIES:
                    click.echo(f"    {display_path}:{note.line}", err=err)
                else:
                    click.echo(f"    {display_path}:{note.line}: {note.snippet}", err=err)
                    if blocking:
                        reason = str(note).replace(str(note.path), "", 1).strip(" :")
                        reason = reason.replace(str(root) + os.sep, "")
                        click.echo(f"      {reason}", err=err)
            elif note.path is not None and not blocking and category in _SUBJECT_ONLY_CATEGORIES:
                click.echo(f"    {_subject(note, root)}", err=err)
            elif note.path is not None:
                click.echo(f"    {_highlight_path(note, root)}", err=err)
            else:
                click.echo(f"    {note}", err=err)
        click.echo(err=err)


@click.command(name="migrate-layout", hidden=True)
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False),
    help="Path to the project root directory",
)
@click.option(
    "--to",
    "destination",
    default="docs",
    show_default=True,
    help="Documentation directory relative to the package root",
)
@click.option("--dry-run", is_flag=True, help="Preview all changes without writing files")
@click.option(
    "--yes", is_flag=True, help="Apply the reviewed changes without an interactive confirmation"
)
@_options.config_option
@click.pass_context
def migrate_layout(
    ctx: click.Context,
    project_path: str | None,
    destination: str,
    dry_run: bool,
    yes: bool,
    config_path: str | None = None,
) -> None:
    """
    Move root-layout documentation into docs/ or a custom directory

    Preview source moves, configuration and ignore-file edits, cache treatment,
    and manual follow-up before applying changes. Keep generated build trees.
    Refuse conflicts and changed inputs even with --yes. Use --dry-run to inspect
    the proposal without writes; it takes precedence over --yes.

    An unrequested default destination falls through docs/, docs-website/,
    doc/, website/ in order, skipping any that already holds unrelated
    content; an explicit --to or --config is always used as given.

    Require affirmative terminal confirmation unless --yes is supplied. If a
    previous migration was interrupted, show its recovery instructions and
    refuse another migration until recovery is complete. A repeated invocation
    with a matching --to or explicit --config reports that no migration is needed.
    """
    import shlex

    from .. import _layout_migration as migration_api
    from .._layout_migration.content import read_config
    from .._layout_migration.model import absolute_path, check_symlinks, moved_path

    try:
        root = _find_package_root(absolute_path(Path(project_path or Path.cwd())))
        recovery = migration_api.recovery_instructions(root)
        if recovery:
            for instruction in recovery:
                click.echo(instruction)
            raise click.ClickException(
                "Pending migration recovery must be completed before another migration."
            )

        if config_path:
            check_symlinks(Path(config_path))
        else:
            for candidate in (
                root / "great-docs.yml",
                *(root / name / "great-docs.yml" for name in CONVENTIONAL_DOC_DIRS),
            ):
                if candidate.is_file():
                    check_symlinks(candidate)
        layout = Layout.make(root, Path(config_path) if config_path else None)
        target = root / destination
        is_default_destination = (
            ctx.get_parameter_source("destination") == click.core.ParameterSource.DEFAULT
        )
        is_default_config = (
            ctx.get_parameter_source("config_path") == click.core.ParameterSource.DEFAULT
        )
        if layout.source_dir != root and is_default_destination:
            target = layout.source_dir
        elif is_default_destination and is_default_config:
            # An explicit --config is disambiguating which file to use, not requesting
            # automatic destination selection; skip the fallback so it can't silently
            # substitute a different directory than the one --config points at.
            target = migration_api.select_destination(layout)
        check_symlinks(target)
        target = absolute_path(target)
        if target == root or not target.is_relative_to(root):
            raise ValueError(f"The destination must be a descendant of the package root: {target}")

        if not config_path and not layout.config_path.is_file():
            candidate = target / "great-docs.yml"
            check_symlinks(candidate)
            layout = Layout.make(root, candidate)
        read_config(layout.config_path.read_bytes().decode("utf-8"))

        migration = migration_api.analyse(layout, target)
        _print_migration(migration)
        if migration.blockers:
            raise click.ClickException("Migration has blocking conflicts.")
        if not migration.moves and not migration.edits:
            click.echo("No migration is needed.")
            return
        if dry_run:
            click.echo("Dry run complete; no files changed.")
            return
        if not yes:
            if not sys.stdin.isatty():
                raise click.ClickException(
                    "An interactive terminal is required for confirmation. Use --yes to apply the previewed changes unattended."
                )
            if not click.confirm("Apply these changes?", default=False):
                click.echo("Migration declined; no files changed.")
                return

        migration_api.apply(migration)
        selected = moved_path(migration.config_path, migration.moves)
        completed = Layout.make(root, selected)
        click.echo(f"Selected configuration: {selected.relative_to(root)}")
        click.echo(f"Deployment directory: {completed.site_dir.relative_to(root)}")
        at_root = Path.cwd().resolve() == root
        selection = [] if at_root else ["--project-path", str(root)]
        if selected not in (root / name / "great-docs.yml" for name in CONVENTIONAL_DOC_DIRS):
            selection += ["--config", str(selected.relative_to(root) if at_root else selected)]
        click.echo("Build or preview the migrated documentation:")
        click.echo("  " + shlex.join(["great-docs", "build", *selection]))
        click.echo("  " + shlex.join(["great-docs", "preview", *selection]))
        if migration.follow_up:
            click.echo()
            _print_notes(
                _count_phrase(
                    len(migration.follow_up),
                    "File to Review",
                    "Files to Review",
                ),
                tuple(_relocate_note(note, migration.moves) for note in migration.follow_up),
                "yellow",
                root=root,
            )
    except (OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--docs-dir",
    type=str,
    help="Path to documentation directory relative to project root",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show method names for each class",
)
@_options.config_option
def scan(
    project_path: str | None, docs_dir: str | None, verbose: bool, config_path: str | None = None
) -> None:
    """Discover package exports and preview what can be documented.

    This command analyzes your package to find public classes, functions,
    and other exports. Use this to see what's available before writing
    your reference config.

    \b
    Examples:
      great-docs scan                       # Show discovered exports
      great-docs scan --verbose             # Include method names for classes
      great-docs scan -v                    # Short form of --verbose
    """

    try:
        package_exports = Exports.make(
            Layout.make(
                Path(project_path) if project_path else Path.cwd(),
                Path(config_path) if config_path else None,
            )
        )
        project = package_exports.project
        importable_name = project.importable_name
        if not project.name or not importable_name:
            click.echo("Error: Could not detect package name.", err=True)
            sys.exit(1)

        # Section 1: Discovery
        click.echo("─" * 50)
        click.echo("📡 Discovery")
        click.echo("─" * 50)
        click.echo(f"Package: {importable_name}\n")

        # Get discovered exports
        exports = package_exports.names(importable_name)
        if not exports:
            click.echo("No exports discovered.")
            sys.exit(0)

        # Group exports for comparison with the configured reference.
        categories = package_exports.categorise(importable_name, exports)

        # Build sets of what's in the reference config
        reference_config = package_exports.config.reference
        ref_items = set()  # Items explicitly listed
        ref_classes_with_members = set()  # Classes with members: true (or default)
        ref_classes_without_members = set()  # Classes with members: false

        for section in reference_config:
            for item in section.get("contents", []):
                if isinstance(item, str):
                    ref_items.add(item)
                elif isinstance(item, dict):
                    name = item.get("name", "")
                    ref_items.add(name)
                    # Check members setting
                    members = item.get("members", True)
                    if members is False:
                        ref_classes_without_members.add(name)
                    else:
                        ref_classes_with_members.add(name)

        # Section 2: Exports
        click.echo("\n" + "─" * 50)
        click.echo(f"📦 Exports ({len(exports)} item(s))")
        click.echo("─" * 50)

        # Markers with colors
        marker_included = click.style("[x]", fg="green")
        marker_not_included = click.style("[ ]", fg="red")
        marker_class_only = click.style("[-]", fg="yellow")

        # Show class-like categories (with method details)
        _class_like_cats = [
            ("classes", "Classes"),
            ("dataclasses", "Dataclasses"),
            ("abstract_classes", "Abstract Classes"),
            ("protocols", "Protocols"),
        ]
        for cat_key, label in _class_like_cats:
            cat_items = categories.get(cat_key)
            if cat_items:
                click.echo(f"\n{label}:")
                for class_name in cat_items:
                    method_names = categories.get("class_method_names", {}).get(class_name, [])

                    # Determine class marker
                    if class_name in ref_classes_without_members:
                        class_marker = marker_class_only
                    elif class_name in ref_classes_with_members or class_name in ref_items:
                        class_marker = marker_included
                    else:
                        class_marker = marker_not_included

                    click.echo(f"• {class_marker} {class_name}")
                    for method in method_names:
                        full_method = f"{class_name}.{method}"
                        method_marker = (
                            marker_included if full_method in ref_items else marker_not_included
                        )
                        click.echo(f"    • {method_marker} {full_method}")

        # Show flat categories (simple lists)
        _flat_cats = [
            ("enums", "Enumerations"),
            ("exceptions", "Exceptions"),
            ("namedtuples", "Named Tuples"),
            ("typeddicts", "Typed Dicts"),
            ("functions", "Functions"),
            ("async_functions", "Async Functions"),
            ("constants", "Constants"),
            ("type_aliases", "Type Aliases"),
            ("other", "Other"),
        ]
        for cat_key, label in _flat_cats:
            cat_items = categories.get(cat_key)
            if cat_items:
                click.echo(f"\n{label}:")
                for name in cat_items:
                    m = marker_included if name in ref_items else marker_not_included
                    click.echo(f"• {m} {name}")

        # Section 3: Config status
        click.echo("\n" + "─" * 50)
        click.echo("📋 Reference Config")
        click.echo("─" * 50)

        if reference_config:
            click.echo(f"\n✅ Found in great-docs.yml ({len(reference_config)} section(s))")
            if verbose:
                for section in reference_config:
                    title = section.get("title") or section.get("subtitle") or "Untitled"
                    contents = section.get("contents", [])
                    click.echo(f"    • {title}: {len(contents)} item(s)")
        else:
            click.echo("\n💡 No reference config found. Add one to great-docs.yml:")
            click.echo("   reference:")
            click.echo("     - title: Core Classes")
            click.echo("       desc: Main classes for the package")
            click.echo("       contents:")
            click.echo("         - name: MyClass")
            click.echo("           members: false     # Don't document methods")
            click.echo("         - SimpleClass        # Methods inline")

    except (*PROJECT_ERRORS, *USER_CODE_ERRORS) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--max-releases",
    type=int,
    default=None,
    help="Maximum number of releases to include (default: from config or 50)",
)
@_options.config_option
def changelog(
    project_path: str | None, max_releases: int | None, config_path: str | None = None
) -> None:
    """
    Generate a Changelog page from repository releases

    Fetch published releases from the repository API and render them as a
    'changelog.qmd' page in the build directory. The page is also linked in
    the navbar automatically.

    \b
    Require a GitHub or GitLab repository URL in the project configuration or metadata.
    Set 'GITHUB_TOKEN' or 'GH_TOKEN' for GitHub, or 'GITLAB_TOKEN' for GitLab.
    """
    try:
        layout = Layout.make(
            Path(project_path) if project_path else Path.cwd(),
            Path(config_path) if config_path else None,
        )
        config = layout.load_config()

        repo = Project.make(config, layout).repository
        if repo is None:
            click.echo(
                "Error: No supported repository URL found in the project. "
                "Add a [project.urls] entry like:\n\n"
                '  Repository = "https://github.com/owner/repo"',
                err=True,
            )
            sys.exit(1)

        contribution = changelog_page.write_page(
            config,
            layout,
            repo,
            HttpRemote(report=lambda message: print(f"   ⚠️  {message}")),
            max_releases=max_releases,
            report=click.echo,
        )
        if contribution is None:
            click.echo("No published releases found.")
        else:
            # Link the page from a site that has been built
            if quarto_yml.path(layout.build_dir).exists():
                with quarto_yml.edit(layout.build_dir) as quarto_config:
                    quarto_yml.apply(quarto_config, contribution, config)
            click.echo(f"✅ Changelog generated: {layout.build_dir / changelog_page.FILENAME}")

    except (*PROJECT_ERRORS, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
