"""
Project set-up for Great Docs

Entries in the project's `.gitignore` keep build output out of version control.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._layout import Layout

__all__ = ["update_gitignore"]

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
