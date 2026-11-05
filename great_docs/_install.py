"""
Project set-up for Great Docs

Create `great-docs.yml` with detected package settings and add build-output exclusions
to the project's `.gitignore`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from yaml12 import format_yaml

from ._build.steps import USER_CODE_ERRORS
from ._reference import block as reference_block
from ._reference import probe
from .config import create_default_config

if TYPE_CHECKING:
    from collections.abc import Callable

    import griffe as gf

    from ._layout import Layout
    from ._manifest import Manifest
    from ._project import Project
    from ._reference.exports import Exports
    from .config import Config

__all__ = ["format_authors_yaml", "update_gitignore", "write_initial_config"]

_YES = {"", "y", "yes"}

# The default build directory's entry, as a block with its comment
_BUILD_DIR_BLOCK = "# Great Docs build directory (ephemeral, do not commit)\n/great-docs/\n"

# Historical version builds and caches beside the default build directory
_VERSIONING_ENTRIES = (
    "/great-docs-*/",
    ".great-docs-build/",
    ".great-docs-cache/",
    ".great-docs/",
)
_VERSIONING_COMMENT = "\n# Great Docs versioned-build artifacts\n"


def write_initial_config(
    config: Config,
    layout: Layout,
    project: Project,
    exports: Exports,
    *,
    force: bool,
    report: Callable[[str], None],
) -> None:
    """
    Write a new `great-docs.yml` with detected package settings

    Activate `parser` and `dynamic` in the shipped default configuration, plus `module`,
    `authors` and `reference` when detected. Leave other keys commented. Use `parser: numpy`
    and `dynamic: true` when no package is detected.

    Parameters
    ----------
    config
        The project's current configuration, which shapes the reference sections.
    layout
        The project's layout, which locates `great-docs.yml`.
    project
        The project's metadata and package names.
    exports
        The project's package and export discovery.
    force
        Whether to replace an existing `great-docs.yml`. If `False`, an existing file is
        kept and the user is told how to replace it.
    report
        A callback for progress and warning messages.

    Returns
    -------
    :
    """
    config_path = layout.config_path

    if config_path.exists() and not force:
        report(
            f"great-docs.yml already exists at {config_path}\n"
            "Use --force to overwrite it (this will reset to defaults)."
        )
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)

    if not project.name or not (importable_name := project.importable_name):
        report("Warning: Could not detect package name, creating minimal config")
        # Keep active defaults even when no package can be inspected.
        minimal_overrides = {"parser": "parser: numpy", "dynamic": "dynamic: true"}
        _ = config_path.write_text(create_default_config(minimal_overrides), encoding="utf-8")
        report(f"Created {config_path}")
        return

    overrides: dict[str, str] = {}

    # Preserve module names that differ even after hyphens are replaced with underscores.
    if project.module and project.module != project.name.replace("-", "_"):
        overrides["module"] = f"module: {project.module}"

    report("Detecting docstring style...")
    package: gf.Module | None = None
    try:
        package = exports.package(importable_name)
    except USER_CODE_ERRORS as error:
        report(f"Warning: Could not load package for docstring detection ({type(error).__name__})")
        parser_style = "numpy"
    else:
        parser_style = probe.detect_docstring_style(package, report=report)
    overrides["parser"] = f"parser: {parser_style}"

    if authors_yaml := format_authors_yaml(_initial_authors(project.manifest)):
        overrides["authors"] = authors_yaml

    names = exports.names(importable_name)
    if not names:
        report(
            "Warning: Could not discover exports; edit the commented "
            "'reference:' section in great-docs.yml to list your API."
        )
        report("Testing dynamic introspection mode...")
        dynamic_mode = package is None or probe.detect_dynamic_mode(
            package, package.members, report=report
        )
        overrides["dynamic"] = f"dynamic: {'true' if dynamic_mode else 'false'}"
        _ = config_path.write_text(create_default_config(overrides), encoding="utf-8")
        report(f"Created {config_path}")
        return

    report("Categorizing API objects...")
    categories = exports.categorise(importable_name, names)

    # Dynamic mode cannot resolve a cyclic alias.
    cyclic_alias_count = categories.get("cyclic_alias_count", 0)
    if cyclic_alias_count > 0:
        report(f"Detected {cyclic_alias_count} cyclic alias(es), using dynamic: false")
        dynamic_mode = False
    else:
        report("Testing dynamic introspection mode...")
        dynamic_mode = package is None or probe.detect_dynamic_mode(package, names, report=report)
    overrides["dynamic"] = f"dynamic: {'true' if dynamic_mode else 'false'}"

    reference_yaml = reference_block.reference_yaml(config, categories)
    if "  - title:" in reference_yaml:
        overrides["reference"] = reference_yaml

    _ = config_path.write_text(create_default_config(overrides), encoding="utf-8")
    report(f"Created {config_path}")


def update_gitignore(
    layout: Layout,
    *,
    report: Callable[[str], None],
    ask: Callable[[str], str] | None = None,
) -> None:
    """
    Add Great Docs' build output to the project's `.gitignore`

    Add each missing entry for the build, site and cache directories, creating the file if
    needed. A configuration in a subdirectory such as `docs/` gets entries under that
    directory. For a configuration at the package root, add `/great-docs/` and the entries
    for versioned builds, and replace an unanchored `great-docs/` line from earlier releases
    with `/great-docs/`. Leave the file untouched when every entry is present.

    Parameters
    ----------
    layout
        The project's layout, which locates the package root and the documentation.
    report
        A callback that receives each line for the user: what changed, or, before a
        question, why the change is needed.
    ask
        A callback that asks the user a yes-or-no question and returns the answer, as
        `input` does. An empty answer, `y` or `yes` approves the change. If `None`, the
        file is updated without asking.
    """
    gitignore_path = layout.package_root / ".gitignore"

    if layout.source_dir != layout.package_root:
        source = layout.source_dir.relative_to(layout.package_root).as_posix()
        entries = [
            f"/{source}/_quarto/",
            f"/{source}/_site/",
            f"/{source}/.cache/",
            "/.great-docs-build/",
            "/.great-docs/",
        ]
        content = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        missing = [entry for entry in entries if not _gitignore_has_entry(content, entry)]
        if missing and (ask is None or _agrees(ask("Ignore Great Docs build output? [Y/n]: "))):
            _ = gitignore_path.write_text(
                content.rstrip() + "\n\n# Great Docs build output\n" + "\n".join(missing) + "\n",
                encoding="utf-8",
            )
        return

    if not gitignore_path.exists():
        if ask is not None:
            report("\nThe great-docs/ build directory is temporary and should not be committed.")
            if not _agrees(ask("Add '/great-docs/' to .gitignore? [Y/n]: ")):
                report("⚠️  Skipped .gitignore update. Remember to ignore /great-docs/.")
                return
        _ = gitignore_path.write_text(
            _BUILD_DIR_BLOCK + _VERSIONING_COMMENT + "".join(f"{e}\n" for e in _VERSIONING_ENTRIES),
            encoding="utf-8",
        )
        report("✅ Created .gitignore to ignore Great Docs build output")
        return

    content = gitignore_path.read_text(encoding="utf-8")
    migrated = _migrate_legacy_gitignore_entry(content)
    has_build_dir = _gitignore_has_entry(migrated, "/great-docs/")
    missing = [e for e in _VERSIONING_ENTRIES if not _gitignore_has_entry(migrated, e)]
    if has_build_dir and not missing and migrated == content:
        return

    migration_only = has_build_dir and not missing
    if ask is not None:
        if migration_only:
            report("\nThe great-docs/ entry in .gitignore matches directories at any depth.")
            question = "Anchor it to the project root as /great-docs/? [Y/n]: "
        else:
            report("\nThe great-docs/ build directory is temporary and should not be committed.")
            question = "Add '/great-docs/' to .gitignore? [Y/n]: "
        if not _agrees(ask(question)):
            report("⚠️  Skipped .gitignore update. Remember to ignore /great-docs/.")
            return

    addition = "" if has_build_dir else "\n" + _BUILD_DIR_BLOCK
    if missing:
        addition += _VERSIONING_COMMENT + "".join(f"{e}\n" for e in missing)
    if migrated != content:
        _ = gitignore_path.write_text(migrated, encoding="utf-8")
    # Appending preserves existing line endings when no migration is needed.
    with gitignore_path.open("a", encoding="utf-8") as file:
        _ = file.write(addition)
    if migration_only:
        report("✅ Anchored the great-docs/ entry to the project root as /great-docs/")
    else:
        report("✅ Updated .gitignore to ignore Great Docs build output")


def format_authors_yaml(authors: list[dict[str, str]]) -> str:
    """
    Format the `authors:` block for a new `great-docs.yml`

    Each author has a `name` and any supplied `role` and `email` fields.
    Commented placeholders mark optional details for the user to fill in.

    Values are quoted only when YAML would otherwise change their meaning. For
    example, `Doe, Jane: PhD` remains a single string.

    Parameters
    ----------
    authors
        Author mappings with a `name` and optional `role` and `email` fields.

    Returns
    -------
    :
        The YAML block without a trailing newline, or an empty string if there are no authors.
    """
    if not authors:
        return ""

    lines = ["authors:"]

    for author in authors:
        entry = _yaml_field("name", author["name"])
        if "role" in author:
            entry += _yaml_field("role", author["role"])
        entry.append("# affiliation: ")
        if "email" in author:
            entry += _yaml_field("email", author["email"])
        else:
            entry.append("# email: ")
        entry += ["# github: ", "# orcid: ", "# homepage: "]
        lines.append(f"  - {entry[0]}")
        lines.extend(f"    {line}" for line in entry[1:])

    return "\n".join(lines)


def _initial_authors(manifest: Manifest) -> list[dict[str, str]]:
    """
    List maintainers and authors for a new `great-docs.yml`

    Parameters
    ----------
    manifest
        The project's declared metadata.

    Returns
    -------
    :
        Entries with a `name`, a `role` and an `email` when declared. List named
        maintainers first with role `Maintainer`, then named authors with role `Author`.
        Keep only the first entry for each name.
    """
    authors: dict[str, dict[str, str]] = {}
    for people, role in ((manifest["maintainers"], "Maintainer"), (manifest["authors"], "Author")):
        for person in people:
            name = person.get("name")
            if name and name not in authors:
                authors[name] = {"name": name, "role": role}
                if email := person.get("email"):
                    authors[name]["email"] = email
    return list(authors.values())


def _yaml_field(key: str, value: str) -> list[str]:
    """
    Format a key and its value as YAML lines

    Parameters
    ----------
    key
        The YAML field name.
    value
        The field value. Quotes or a block scalar preserve its text when YAML
        would otherwise interpret it differently.

    Returns
    -------
    :
        YAML lines with indentation only for block scalar continuation lines.
    """
    return format_yaml({key: value}).splitlines()


def _agrees(answer: str) -> bool:
    """
    Check whether an answer to a `[Y/n]` question approves the change

    Parameters
    ----------
    answer
        The user's answer, in any case and with surrounding whitespace.

    Returns
    -------
    :
        Whether the answer is empty, `y` or `yes`.
    """
    return answer.strip().lower() in _YES


def _migrate_legacy_gitignore_entry(content: str) -> str:
    """
    Anchor a standalone legacy `great-docs/` ignore entry

    Earlier releases omitted the leading `/`, so Git matched a directory of
    that name anywhere in the project. Replace only a complete `great-docs/`
    line, without changing related patterns or negations.

    Parameters
    ----------
    content
        Contents of a project `.gitignore` file.

    Returns
    -------
    :
        Updated contents, or the original contents when no legacy entry exists.
    """
    lines = content.splitlines(keepends=True)
    migrated = False
    new_lines: list[str] = []
    for line in lines:
        body = line.rstrip("\r\n")
        line_ending = line[len(body) :]
        if body.rstrip() == "great-docs/":
            new_lines.append("/great-docs/" + line_ending)
            migrated = True
        else:
            new_lines.append(line)
    return "".join(new_lines) if migrated else content


def _gitignore_has_entry(content: str, entry: str) -> bool:
    """
    Check whether `entry` appears as a complete line in `content`

    Whole-line matching prevents an entry such as `/great-docs/` from also
    matching a negated path such as `!skills/great-docs/`.

    Parameters
    ----------
    content
        Contents of a project `.gitignore` file.
    entry
        Gitignore pattern to look for as a standalone line.

    Returns
    -------
    :
        Whether any line equals `entry` after stripping surrounding whitespace.
    """
    return entry in (line.strip() for line in content.splitlines())
