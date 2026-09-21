"""Inspect migration inputs and produce operations without writing files"""

from __future__ import annotations

import configparser
import os
import re
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from great_docs._content_naming import section_slug
from great_docs._layout import Layout
from great_docs._utils import is_great_docs_build_dir, recognised_build_dirs

from .content import (
    ConfigPath,
    ContentDirectory,
    config_paths,
    local_path,
    read_config,
    rewrite_config,
    rewrite_document,
    set_config_values,
)
from .model import (
    Edit,
    Migration,
    MigrationError,
    Move,
    Note,
    absolute_path,
    check_symlinks,
    fingerprint,
    moved_path,
    tree_files,
)

_DOCUMENT_SUFFIXES = {".md", ".qmd", ".html", ".htm"}
_MANIFESTS = ("pyproject.toml", "setup.py", "setup.cfg", "go.mod", "Cargo.toml")
_RESERVED = {
    ".git",
    ".venv",
    ".great-docs-cache",
    "great-docs",
    "_quarto",
    "_site",
    "_freeze",
    "tests",
    "test-packages",
    "scripts",
}


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise MigrationError(
            f"Cannot run git {args[0]}: local Git check exited {result.returncode}"
        )
    return result.stdout


def _ignored_paths(root: Path) -> frozenset[Path] | None:
    """
    Return every path Git ignores under `root`, or `None` outside a worktree

    `None` means "no ignore information available" rather than "nothing is
    ignored" — callers must treat it as "skip this check", matching how
    `_check_freeze_ignore_policy` already falls back outside a Git worktree.
    """
    if not any((parent / ".git").exists() for parent in (root, *root.parents)):
        return None
    output = _git(
        root, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"
    )
    return frozenset(root / os.fsdecode(path).rstrip("/") for path in output.split(b"\0") if path)


def _check_freeze_ignore_policy(
    root: Path,
    destination: Path,
    paths: set[Path],
    retain: Callable[[Path], bool],
    retain_policy: Callable[[Path], bool],
) -> None:
    """
    Refuse cache relocation when effective ignore rules would change

    Compare rules independently of the index so tracked cache files and
    untracked exceptions keep their existing policy. Retain the local and
    external rule inputs for application-time revalidation.
    """
    source = root / "_freeze"
    if any(path.name == ".gitignore" for path in paths):
        raise MigrationError(
            "Cannot preserve freeze ignore policy with nested cache .gitignore files; "
            "move those rules to the package .gitignore and preview again"
        )
    pairs = [(source / path, destination / "_freeze" / path) for path in paths | {Path(".")}]
    rules = {
        parent / ".gitignore"
        for pair in pairs
        for path in pair
        for parent in path.parents
        if parent.is_relative_to(root)
    }
    for path in sorted(rules):
        retain(path)
    if not any((parent / ".git").exists() for parent in (root, *root.parents)):
        harmless = {"great-docs/", "/great-docs/"}
        if any(
            line.strip() and not line.lstrip().startswith("#") and line.strip() not in harmless
            for path in rules
            if path.is_file()
            for line in path.read_text(encoding="utf-8").splitlines()
        ):
            raise MigrationError(
                "Cannot verify freeze ignore policy outside a Git worktree; "
                "initialise Git, check destination cache rules, and preview again"
            )
        return

    repository = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip())
    for path in (root, *root.parents):
        if path.is_relative_to(repository):
            retain_policy(path / ".gitignore")
    for name in ("info/exclude", "config", "config.worktree", "HEAD", "index"):
        retain_policy(
            absolute_path(root / os.fsdecode(_git(root, "rev-parse", "--git-path", name)).strip())
        )
    shared_index = os.fsdecode(_git(root, "rev-parse", "--shared-index-path")).strip()
    if shared_index:
        retain_policy(absolute_path(root / shared_index))
    tracked = {
        root / os.fsdecode(path)
        for path in _git(root, "ls-files", "--cached", "-z", "--", "_freeze").split(b"\0")
        if path
    }
    config = _git(root, "config", "--show-origin", "--list").decode("utf-8")
    for line in config.splitlines():
        origin, separator, entry = line.partition("\t")
        if not separator or not origin.startswith("file:"):
            raise MigrationError(
                "Cannot verify freeze ignore policy from non-file Git configuration"
            )
        config_file = absolute_path(root / Path(origin[5:]).expanduser())
        retain_policy(config_file)
        key, _, value = entry.partition("=")
        if key.lower().startswith("includeif."):
            raise MigrationError(
                "Cannot verify freeze ignore policy with conditional Git includes; "
                "use unconditional policy configuration and preview again"
            )
        if key.lower() == "include.path":
            retain_policy(absolute_path(config_file.parent / Path(value).expanduser()))
    user_root = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(user_root / ".config")))
    global_config = os.environ.get("GIT_CONFIG_GLOBAL")
    defaults = [xdg / "git/ignore"]
    defaults.extend(
        [Path(global_config)] if global_config else [user_root / ".gitconfig", xdg / "git/config"]
    )
    for path in defaults:
        retain_policy(path)
    excludes = os.fsdecode(_git(root, "config", "--path", "--get", "core.excludesFile")).strip()
    if excludes:
        retain_policy(absolute_path(root / Path(excludes).expanduser()))
    queries = [
        str(path.relative_to(root)) + ("/" if before.is_dir() or before == source else "")
        for before, after in pairs
        for path in (before, after)
    ]
    ignored = set(
        _git(
            root,
            "check-ignore",
            "--no-index",
            "-z",
            "--stdin",
            input_bytes=b"\0".join(os.fsencode(path) for path in queries) + b"\0",
        ).split(b"\0")
    )
    for index in range(0, len(queries), 2):
        before, after = queries[index : index + 2]
        original = root / before
        if original in tracked and os.fsencode(after) in ignored:
            raise MigrationError(
                f"Migration would lose tracked cache status: {before} -> {after}. "
                "Make the destination cache file addable in .gitignore and preview again"
            )
        if original.is_dir() and any(path.is_relative_to(original) for path in tracked):
            continue
        if original in tracked:
            continue
        if (os.fsencode(before) in ignored) != (os.fsencode(after) in ignored):
            raise MigrationError(
                f"Migration would change freeze ignore policy: {before} -> {after}. "
                "Adjust destination .gitignore rules to preserve ignored files and "
                "tracked exceptions, then preview again"
            )


def _overlaps(left: Path, right: Path) -> bool:
    return left.is_relative_to(right) or right.is_relative_to(left)


def _package_metadata(root: Path) -> tuple[str, list[Path]]:
    name = ""
    sources: list[Path] = [root / "src"]
    manifest = root / "pyproject.toml"
    if manifest.is_file():
        data = tomllib.loads(manifest.read_bytes().decode("utf-8"))
        name = data.get("project", {}).get("name", "")
        setuptools = data.get("tool", {}).get("setuptools", {})
        for directory in setuptools.get("package-dir", {}).values():
            if isinstance(directory, str) and directory not in {"", "."}:
                sources.append(absolute_path(root / directory))
        packages = setuptools.get("packages", {})
        if isinstance(packages, dict):
            for directory in packages.get("find", {}).get("where", []):
                if isinstance(directory, str) and directory not in {"", "."}:
                    sources.append(absolute_path(root / directory))
        elif isinstance(packages, list):
            sources.extend(
                root / package.split(".")[0] for package in packages if isinstance(package, str)
            )
        for package in data.get("tool", {}).get("poetry", {}).get("packages", []):
            if isinstance(package, dict) and isinstance(package.get("include"), str):
                sources.append(root / package.get("from", "") / package["include"])
    if not name and (root / "setup.cfg").is_file():
        config = configparser.ConfigParser()
        config.read_string((root / "setup.cfg").read_bytes().decode("utf-8"))
        name = config.get("metadata", "name", fallback="")
    if not name and (root / "setup.py").is_file():
        match = re.search(
            r"name\s*=\s*[\"']([^\"']+)[\"']", (root / "setup.py").read_bytes().decode("utf-8")
        )
        if match:
            name = match[1]
    packages = [
        child
        for child in sorted(root.iterdir())
        if not child.name.startswith(".") and (child / "__init__.py").is_file()
    ]
    sources.extend(packages)
    if not name and len(packages) == 1:
        name = packages[0].name
    if name:
        sources.append(root / name.replace("-", "_"))
    return name, sources


def _logo_candidates(package: str, *, hero: bool) -> list[str]:
    if hero:
        return [
            "logo-hero.svg",
            "logo-hero.png",
            "assets/logo-hero.svg",
            "assets/logo-hero.png",
            "logo-hero-light.svg",
            "logo-hero-light.png",
            "assets/logo-hero-light.svg",
            "assets/logo-hero-light.png",
        ]
    candidates = [
        "logo.svg",
        "logo.png",
        "assets/logo.svg",
        "assets/logo.png",
        "docs/assets/logo.svg",
        "docs/assets/logo.png",
    ]
    for name in dict.fromkeys((package, package.replace("-", "_"))):
        if name:
            candidates.extend(
                [
                    f"{name}_logo.svg",
                    f"{name}_logo.png",
                    f"assets/{name}_logo.svg",
                    f"assets/{name}_logo.png",
                ]
            )
    candidates.extend(["assets/logo-light.svg", "assets/logo-light.png"])
    return candidates


def _dedicated_directories(config: dict[str, Any], root: Path) -> list[Path]:
    selected: list[Path] = []
    guide = config.get("user_guide")
    if isinstance(guide, str) and not Path(guide).is_absolute():
        selected.append(root / guide)
    elif not isinstance(guide, str):
        for name in ("user_guide", "user-guide"):
            if (root / name).exists() or (root / name).is_symlink():
                selected.append(root / name)
                break
    sections = config.get("sections") or []
    if not isinstance(sections, list):
        raise MigrationError("Narrative sections must be a list of directory mappings")
    for section in sections:
        if (
            isinstance(section, dict)
            and isinstance(section.get("dir"), str)
            and not Path(section["dir"]).is_absolute()
        ):
            selected.append(root / section["dir"])
    custom = config.get("custom_pages")
    if custom is None:
        if (root / "custom").exists() or (root / "custom").is_symlink():
            selected.append(root / "custom")
    else:
        for entry in custom if isinstance(custom, list) else [custom]:
            directory = entry.get("dir") if isinstance(entry, dict) else entry
            if isinstance(directory, str) and not Path(directory).is_absolute():
                selected.append(root / directory)
    marimo = config.get("marimo", False)
    if marimo is True or isinstance(marimo, dict) and marimo.get("enabled"):
        if (root / "notebooks").exists() or (root / "notebooks").is_symlink():
            selected.append(root / "notebooks")
    for path in selected:
        check_symlinks(path)
    return [absolute_path(path) for path in selected]


def _content_directories(config: dict[str, Any], root: Path) -> tuple[ContentDirectory, ...]:
    """
    Map each recognised content root to its build-time rename and prefix rule

    Mirrors `_dedicated_directories`'s reading of the same `user_guide` and
    `sections` config fields; keep the two in sync when either changes.
    """
    directories: list[ContentDirectory] = []
    guide = config.get("user_guide")
    strip = not isinstance(guide, list)
    if isinstance(guide, str) and not Path(guide).is_absolute():
        directories.append(ContentDirectory(root / guide, "user-guide", strip))
    elif not isinstance(guide, str):
        for name in ("user_guide", "user-guide"):
            if (root / name).exists() or (root / name).is_symlink():
                directories.append(ContentDirectory(root / name, "user-guide", strip))
                break
    for section in config.get("sections") or []:
        if (
            isinstance(section, dict)
            and isinstance(section.get("dir"), str)
            and not Path(section["dir"]).is_absolute()
        ):
            directories.append(
                ContentDirectory(
                    root / section["dir"],
                    section_slug(section["dir"]),
                    section.get("type") != "blog",
                )
            )
    return tuple(directories)


def _exclusive_to_moving_content(
    candidates: list[Path],
    root: Path,
    moves: list[Move],
    content_directories: tuple[ContentDirectory, ...],
    generated: list[Path],
    blockers: list[Note],
) -> set[Path]:
    """Return which candidates are referenced only from content already moving"""
    try:
        ignored = _ignored_paths(root)
    except (OSError, MigrationError) as error:
        blockers.append(
            Note(
                f"Cannot inspect git ignore rules: {error}", category="Files That Could Not Be Read"
            )
        )
        ignored = None
    non_moving: set[Path] = set()
    for directory, children, names in os.walk(root, followlinks=False):
        parent = Path(directory)
        children[:] = [name for name in children if _walk_into(parent / name, generated, ignored)]
        for name in names:
            path = parent / name
            # A `documents` membership check is not enough here: `documents` also
            # holds README-style files that are *edited in place* rather than moved
            # (see `analyse`'s README loop), so it cannot distinguish moving content
            # from content that merely stays put and gets its links patched. Whether
            # a move would relocate the file is the only reliable test. Every
            # candidate's own subtree is included here too, so a file inside one
            # not-yet-decided candidate can still prove another candidate is
            # externally referenced.
            if (
                path.suffix.lower() in _DOCUMENT_SUFFIXES
                and moved_path(path, tuple(moves)) == path
                and not path.is_symlink()
            ):
                non_moving.add(path)
    referenced_externally: set[Path] = set()
    for doc in non_moving:
        try:
            text = doc.read_bytes().decode("utf-8")
        except (OSError, UnicodeError):
            continue
        _, inputs, _, _ = rewrite_document(text, doc, (), content_directories=content_directories)
        for target in inputs:
            for candidate in candidates:
                # A reference from inside the candidate's own subtree to itself
                # isn't external: once the candidate folds in, both files move
                # together as one unit.
                if target.is_relative_to(candidate) and not doc.is_relative_to(candidate):
                    referenced_externally.add(candidate)
    return {candidate for candidate in candidates if candidate not in referenced_externally}


def _categorize_move_contents(
    move: Move,
    config_path: Path,
    documents: set[Path],
    blockers: list[Note],
    follow_up: list[Note],
) -> None:
    """Classify every file a move brings in, the same way for every move"""
    try:
        for path in tree_files(move.source):
            if path == config_path:
                continue
            if path.name == "__init__.py" or path.name in _MANIFESTS:
                blockers.append(
                    Note(
                        f"Documentation directory contains package sources or metadata: {path}",
                        category="Package Files Mixed Into Docs",
                        path=path,
                    )
                )
            if path.suffix.lower() in _DOCUMENT_SUFFIXES:
                documents.add(path)
            elif path.suffix.lower() in {".ipynb", ".py", ".r", ".jl"}:
                follow_up.append(
                    Note(
                        f"Review dynamic code, notebook references, and working-directory assumptions in {path}",
                        category="Scripts and Notebooks to Verify",
                        path=path,
                    )
                )
            elif path.suffix.lower() == ".rst":
                follow_up.append(
                    Note(
                        f"Review reStructuredText references in {path}",
                        category="reStructuredText Files to Check",
                        path=path,
                    )
                )
    except (OSError, MigrationError) as error:
        blockers.append(
            Note(
                f"Cannot inspect {move.source}: {error}",
                category="Files That Could Not Be Read",
                path=move.source,
            )
        )


def _fold_in_static_directories(
    root: Path,
    destination: Path,
    config_path: Path,
    documents: set[Path],
    moves: list[Move],
    protected: list[Path],
    content_directories: tuple[ContentDirectory, ...],
    config_referenced: set[Path],
    never_fold_in: set[Path],
    retain: Callable[[Path], bool],
    generated: list[Path],
    blockers: list[Note],
) -> list[Note]:
    """
    Move a top-level directory into the destination when only moving content needs it

    Repeat until no further directory qualifies, since folding one directory
    in can pull its own files into `documents` and reveal new references. Fingerprint
    and classify every folded-in directory the same way the original move-set loop
    already does, since that loop only runs over the *original* move-set, before this
    pass adds to it. Return the follow-up notes for directories deliberately left in
    place, alongside the per-file notes the folded-in directories raise.
    """
    follow_up: list[Note] = []
    folded: set[Path] = {move.source for move in moves}
    while True:
        referenced: set[Path] = set(config_referenced)
        for doc in sorted(documents):
            try:
                text = doc.read_bytes().decode("utf-8")
            except (OSError, UnicodeError):
                continue
            _, inputs, _, _ = rewrite_document(
                text, doc, tuple(moves), content_directories=content_directories
            )
            referenced.update(inputs)
        candidates: dict[Path, Path] = {}
        for target in sorted(referenced):
            if not target.is_relative_to(root) or moved_path(target, tuple(moves)) != target:
                continue
            top = root / target.relative_to(root).parts[0]
            if top not in folded and top.name not in _RESERVED and top.is_dir():
                candidates[top] = top
        to_fold = [
            candidate
            for candidate in candidates
            if not any(_overlaps(candidate, path) for path in protected)
            and not any(_overlaps(candidate, path) for path in never_fold_in)
            and not _overlaps(candidate, destination)
        ]
        if not to_fold:
            break
        exclusive = _exclusive_to_moving_content(
            to_fold, root, moves, content_directories, generated, blockers
        )
        for candidate in to_fold:
            if candidate not in exclusive:
                follow_up.append(
                    Note(
                        f"Retain {candidate} in place; something outside the moving documentation still references it",
                        category="Files Retained As-Is",
                        path=candidate,
                    )
                )
                folded.add(candidate)
                continue
            move = Move(candidate, destination / candidate.relative_to(root))
            moves.append(move)
            folded.add(candidate)
            if retain(candidate):
                _categorize_move_contents(move, config_path, documents, blockers, follow_up)
    return follow_up


def _walk_into(path: Path, generated: list[Path], ignored: frozenset[Path] | None) -> bool:
    """Whether a directory the implicit-input walk finds should be descended into"""
    return (
        not path.name.startswith(".")
        and path.name not in {"_quarto", "_site", "_freeze"}
        and path not in generated
        and not path.is_symlink()
        and (ignored is None or path not in ignored)
    )


def analyse(layout: Layout, destination: Path) -> Migration:
    """
    Preview a root-layout migration without modifying the filesystem

    Resolve a relative destination against the package root. Record moves,
    edits at original paths, retained input fingerprints, blocking conflicts,
    and file-specific manual follow-up. Preserve generated trees and cache
    bytes. Report an already migrated matching layout without operations.
    """
    root = layout.package_root
    supplied_destination = root / destination
    destination = absolute_path(root / destination)
    config_path = layout.config_path
    moves: list[Move] = []
    edits: list[Edit] = []
    fingerprints: dict[Path, str] = {}
    blockers: list[Note] = []
    follow_up: list[Note] = []

    def result() -> Migration:
        return Migration(
            root,
            config_path,
            tuple(moves),
            tuple(edits),
            tuple(sorted(fingerprints.items())),
            tuple(dict.fromkeys(blockers)),
            tuple(dict.fromkeys(follow_up)),
        )

    def retain(path: Path) -> bool:
        try:
            check_symlinks(path)
            if path.is_dir():
                tree_files(path)
            fingerprints[path] = fingerprint(path)
            return True
        except (OSError, MigrationError) as error:
            blockers.append(
                Note(
                    f"Cannot inspect {path}: {error}",
                    category="Files That Could Not Be Read",
                    path=path,
                )
            )
            return False

    def retain_policy(path: Path) -> bool:
        if path.is_relative_to(root):
            return retain(path)
        seen: set[Path] = set()
        try:
            while True:
                link = next(
                    (part for part in reversed((path, *path.parents)) if part.is_symlink()), None
                )
                if link is None:
                    return retain(path)
                if link in seen:
                    raise MigrationError(f"Ignore policy contains a symlink cycle: {link}")
                seen.add(link)
                fingerprints[link] = fingerprint(link)
                target = absolute_path(link.parent / os.readlink(link))
                path = target / path.relative_to(link)
        except (OSError, MigrationError) as error:
            blockers.append(
                Note(
                    f"Cannot inspect ignore policy {path}: {error}",
                    category="Files That Could Not Be Read",
                    path=path,
                )
            )
            return False

    if layout.source_dir != root:
        if destination == layout.source_dir:
            follow_up.append(
                Note(
                    f"Documentation already uses {layout.source_dir}; no migration is needed",
                    category="Already Migrated",
                    path=layout.source_dir,
                )
            )
        else:
            blockers.append(
                Note(
                    f"Relocating an already migrated project is unsupported: {layout.source_dir}",
                    category="Relocation Not Supported",
                    path=layout.source_dir,
                )
            )
        return result()
    if destination == root or not destination.is_relative_to(root):
        blockers.append(
            Note(
                f"The destination must be a descendant of the package root: {destination}",
                category="Conflicts at the Destination",
                path=destination,
            )
        )
        return result()
    try:
        check_symlinks(supplied_destination)
        check_symlinks(destination)
        for component in (destination, *destination.parents):
            if component.exists() and not component.is_dir():
                blockers.append(
                    Note(
                        f"Destination component is not a directory: {component}",
                        category="Conflicts at the Destination",
                        path=component,
                    )
                )
    except MigrationError as error:
        blockers.append(Note(str(error), category="Conflicts at the Destination", path=destination))
    if not retain(config_path):
        return result()
    try:
        before = config_path.read_bytes()
        text = before.decode("utf-8")
        config = read_config(text)
        rewrite_config(text, (), root, root)
    except (OSError, UnicodeError, MigrationError) as error:
        blockers.append(
            Note(
                f"Cannot inspect configuration {config_path}: {error}",
                category="Files That Could Not Be Read",
                path=config_path,
            )
        )
        return result()

    for name in _MANIFESTS:
        retain(root / name)
    try:
        package, package_sources = _package_metadata(root)
    except (OSError, UnicodeError, ValueError, configparser.Error) as error:
        blockers.append(
            Note(
                f"Cannot inspect package metadata: {error}", category="Files That Could Not Be Read"
            )
        )
        package, package_sources = "", [root / "src"]
    module = config.get("module")
    if isinstance(module, str):
        package_sources.append(root / module.split(".")[0])
    try:
        generated = recognised_build_dirs(layout)
        if is_great_docs_build_dir(layout.build_dir):
            generated.append(layout.build_dir)
    except OSError as error:
        blockers.append(
            Note(
                f"Cannot inspect generated projects: {error}",
                category="Files That Could Not Be Read",
            )
        )
        generated = []
    protected = [*package_sources, *(root / name for name in _RESERVED), *generated]
    for path in protected:
        if _overlaps(destination, path):
            blockers.append(
                Note(
                    f"Destination overlaps package sources, shared assets, or generated output: {path}",
                    category="Conflicts at the Destination",
                    path=destination,
                )
            )

    try:
        selected = _dedicated_directories(config, root)
    except (OSError, MigrationError) as error:
        blockers.append(Note(str(error), category="Files That Could Not Be Read"))
        selected = []
    content_directories = _content_directories(config, root)
    for name in ("index.qmd", "index.md"):
        if (root / name).exists() or (root / name).is_symlink():
            selected.append(root / name)
            break
    selected.append(config_path)
    for index, source in enumerate(selected):
        if source == root or not source.is_relative_to(root):
            blockers.append(
                Note(
                    f"Documentation source must be a package descendant: {source}",
                    category="Conflicts With the Source",
                    path=source,
                )
            )
            continue
        if _overlaps(source, destination):
            blockers.append(
                Note(
                    f"Documentation source overlaps the destination: {source}",
                    category="Conflicts With the Source",
                    path=source,
                )
            )
        for other in selected[:index]:
            if _overlaps(source, other):
                blockers.append(
                    Note(
                        f"Selected documentation sources overlap: {other} and {source}",
                        category="Conflicts With the Source",
                        path=source,
                    )
                )
        for path in protected:
            if _overlaps(source, path):
                blockers.append(
                    Note(
                        f"Documentation source overlaps package sources, shared assets, or generated output: {source} and {path}",
                        category="Conflicts With the Source",
                        path=source,
                    )
                )
        target = destination / source.relative_to(root)
        if source == config_path:
            target = destination / config_path.name
        if source.exists() or source.is_symlink():
            moves.append(Move(source, target))
        else:
            blockers.append(
                Note(
                    f"Documentation source does not exist: {source}",
                    category="Conflicts With the Source",
                    path=source,
                )
            )

    for name in (
        "user_guide",
        "user-guide",
        "custom",
        "notebooks",
        "index.qmd",
        "index.md",
        "README.md",
        "README.rst",
    ):
        if (root / name).is_file() or not (root / name).exists():
            retain(root / name)
        target = destination / name
        if target.exists() and not any(move.destination == target for move in moves):
            blockers.append(
                Note(
                    f"Existing destination input would change source discovery: {target}",
                    category="Conflicts at the Destination",
                    path=target,
                )
            )

    implicit: dict[ConfigPath, Any] = {}
    for path, hero in ((("logo",), False), (("hero", "logo"), True)):
        parent = config.get("hero") if hero else config
        existing = parent.get("logo") if isinstance(parent, dict) else None
        if hero and parent is False or existing is False:
            continue
        explicit = (
            isinstance(existing, str)
            or isinstance(existing, dict)
            and any(existing.get(key) for key in ("light", "dark"))
        )
        if explicit:
            continue
        for candidate in _logo_candidates(package, hero=hero):
            candidate_path = root / candidate
            if not retain(candidate_path):
                break
            if candidate_path.is_file():
                light = Path(candidate)
                dark = light.with_name(light.stem.replace("-light", "") + "-dark" + light.suffix)
                retain(root / dark)
                variants = {
                    "light": candidate,
                    "dark": dark.as_posix() if (root / dark).is_file() else candidate,
                }
                if isinstance(existing, dict):
                    implicit.update({(*path, key): value for key, value in variants.items()})
                else:
                    implicit[path] = variants
                break
    try:
        materialised = set_config_values(text, implicit)
        amended = read_config(materialised)
    except MigrationError as error:
        blockers.append(Note(str(error), category="Configuration to Review", path=config_path))
        materialised, amended = text, config
    documents: set[Path] = set()
    config_referenced: set[Path] = set()
    # Directories that must never fold in, either because a config value pins them in
    # place absolutely, or because an executable script path (`pre_render`) references
    # them and a directory-level move wouldn't safely update that reference.
    never_fold_in: set[Path] = set()
    for option, value in config_paths(amended):
        try:
            source = local_path(value, root)
            if source is None:
                continue
            if Path(value).is_absolute():
                # An absolute config value is a deliberate opt-out of relocation
                # (`_dedicated_directories` already excludes it from `selected`/`moves`
                # on the same basis); folding it in would silently move something the
                # author pinned in place, however it's discovered as a candidate.
                never_fold_in.add(source)
            else:
                config_referenced.add(source)
            check_symlinks(root / value)
            readable = retain(source)
            if (
                readable
                and source.is_dir()
                and option[0] in {"sections", "user_guide", "custom_pages"}
            ):
                documents.update(
                    path for path in tree_files(source) if path.suffix.lower() in _DOCUMENT_SUFFIXES
                )
            if not source.exists():
                blockers.append(
                    Note(
                        f"Configured input does not exist for {'.'.join(map(str, option))}: {source}",
                        category="Configuration to Review",
                        path=source,
                    )
                )
            if not source.is_relative_to(root):
                follow_up.append(
                    Note(
                        f"Retain external input for {'.'.join(map(str, option))}: {source}",
                        category="Files Retained As-Is",
                        path=source,
                    )
                )
            if Path(value).is_absolute() and moved_path(source, tuple(moves)) != source:
                blockers.append(
                    Note(
                        f"An unchanged absolute reference would point into a moved source: {source}",
                        category="Configuration to Review",
                        path=source,
                    )
                )
            if "pre_render" in option:
                never_fold_in.add(source)
                follow_up.append(
                    Note(
                        f"Review working-directory assumptions in render script {source}",
                        category="Scripts and Notebooks to Verify",
                        path=source,
                    )
                )
        except (OSError, ValueError) as error:
            blockers.append(
                Note(
                    f"Cannot inspect configured input {option}: {error}",
                    category="Files That Could Not Be Read",
                )
            )

    for move in moves:
        if not retain(move.source):
            continue
        _categorize_move_contents(move, config_path, documents, blockers, follow_up)
    for name in ("README.md", "README.rst", "index.qmd", "index.md"):
        path = root / name
        if path.is_file():
            retain(path)
            if path.suffix in _DOCUMENT_SUFFIXES:
                documents.add(path)
            elif moves:
                follow_up.append(
                    Note(
                        f"Review reStructuredText references to moved documentation in {path}",
                        category="reStructuredText Files to Check",
                        path=path,
                    )
                )
    follow_up.extend(
        _fold_in_static_directories(
            root,
            destination,
            config_path,
            documents,
            moves,
            protected,
            content_directories,
            config_referenced,
            never_fold_in,
            retain,
            generated,
            blockers,
        )
    )
    try:
        rewritten = rewrite_config(materialised, tuple(moves), root, destination).encode("utf-8")
        if rewritten != before:
            edits.append(Edit(config_path, before, rewritten))
    except MigrationError as error:
        blockers.append(Note(str(error), category="Configuration to Review", path=config_path))

    generated_homepage = None
    if not any((root / name).exists() for name in ("index.qmd", "index.md")) and any(
        (root / name).is_file() for name in ("README.md", "README.rst")
    ):
        generated_homepage = root / "index.qmd"
    for path in sorted(documents):
        try:
            content = path.read_bytes()
            rewritten_text, inputs, notes, conflicts = rewrite_document(
                content.decode("utf-8"),
                path,
                tuple(moves),
                generated_homepage=generated_homepage,
                content_directories=content_directories,
            )
            follow_up.extend(notes)
            blockers.extend(conflicts)
            for source in inputs:
                retain(source)
            after = rewritten_text.encode("utf-8")
            if content != after:
                if path.is_relative_to(root):
                    edits.append(Edit(path, content, after))
                else:
                    blockers.append(
                        Note(
                            f"A retained external document needs reference edits before migration: {path}",
                            category="References to Edit Before Migrating",
                            path=path,
                        )
                    )
        except (OSError, UnicodeError, ValueError) as error:
            blockers.append(
                Note(
                    f"Cannot inspect document {path}: {error}",
                    category="Files That Could Not Be Read",
                    path=path,
                )
            )

    for doc in sorted(documents):
        try:
            text = doc.read_bytes().decode("utf-8")
        except (OSError, UnicodeError):
            continue
        _, inputs, _, _ = rewrite_document(
            text,
            doc,
            tuple(moves),
            generated_homepage=generated_homepage,
            content_directories=content_directories,
        )
        relocated_doc = moved_path(doc, tuple(moves))
        if not relocated_doc.is_relative_to(destination):
            continue
        for target in inputs:
            if moved_path(target, tuple(moves)) == target and (
                not target.is_relative_to(destination)
            ):
                follow_up.append(
                    Note(
                        f"Review: external reference from {doc} to {target}",
                        category="References Outside the Move",
                        path=doc,
                    )
                )

    assets = root / "assets"
    referenced = set(fingerprints)
    if assets.exists() and assets not in {move.source for move in moves} and retain(assets):
        for path in tree_files(assets):
            if path not in referenced:
                blockers.append(
                    Note(
                        f"Cannot preserve unreferenced implicit asset publication automatically: {path}",
                        category="Assets With Unclear Ownership",
                        path=path,
                    )
                )

    freeze = root / "_freeze"
    target_freeze = destination / "_freeze"
    freeze_paths: set[Path] = set()
    retain(freeze)
    if target_freeze.exists() or target_freeze.is_symlink():
        blockers.append(
            Note(
                f"Destination cache already exists: {target_freeze}",
                category="Cached Build Conflicts",
                path=target_freeze,
            )
        )
    if freeze.exists() or freeze.is_symlink():
        if not freeze.is_dir():
            blockers.append(
                Note(
                    f"Persistent cache must be a directory: {freeze}",
                    category="Cached Build Conflicts",
                    path=freeze,
                )
            )
        moves.append(Move(freeze, target_freeze))
        freeze_paths.update(path.relative_to(freeze) for path in freeze.rglob("*"))
    else:
        recovered: dict[Path, bytes] = {}
        for build in generated:
            cache = build / "_freeze"
            if not retain(cache) or not cache.exists():
                continue
            try:
                for path in tree_files(cache):
                    recovered[target_freeze / path.relative_to(cache)] = path.read_bytes()
            except (OSError, MigrationError) as error:
                blockers.append(
                    Note(
                        f"Cannot recover cache from {cache}: {error}",
                        category="Cached Build Conflicts",
                        path=cache,
                    )
                )
        for path, content in sorted(recovered.items()):
            if any(parent in recovered for parent in path.parents):
                blockers.append(
                    Note(
                        f"Recovered cache files overlap a directory: {path}",
                        category="Cached Build Conflicts",
                        path=path,
                    )
                )
            edits.append(Edit(path, None, content))
            freeze_paths.add(path.relative_to(target_freeze))
    if freeze.exists() or freeze_paths:
        try:
            _check_freeze_ignore_policy(root, destination, freeze_paths, retain, retain_policy)
        except (OSError, UnicodeError, MigrationError) as error:
            blockers.append(Note(str(error), category="Cached Build Conflicts", path=freeze))
    cache_root = root / ".great-docs-cache"
    target_cache = destination / ".cache"
    # Move each cache separately. The root also contains this command's
    # recovery journal, and the apply step rejects overlapping moves.
    for name in ("d2", "interlinks", "snapshots"):
        source_cache = cache_root / name
        if not source_cache.exists() and not source_cache.is_symlink():
            continue
        retain(source_cache)
        dest_cache = target_cache / name
        if dest_cache.exists() or dest_cache.is_symlink():
            blockers.append(
                Note(
                    f"Destination cache already exists: {dest_cache}",
                    category="Cached Build Conflicts",
                    path=dest_cache,
                )
            )
        elif not source_cache.is_dir():
            blockers.append(
                Note(
                    f"Persistent cache must be a directory: {source_cache}",
                    category="Cached Build Conflicts",
                    path=source_cache,
                )
            )
        else:
            moves.append(Move(source_cache, dest_cache))
    for build in generated:
        retain(build / "_quarto.yml")
        follow_up.append(
            Note(
                f"Retain generated project {build}; the next build publishes to {destination / '_site'}",
                category="Files Retained As-Is",
                path=build,
            )
        )
    ignore = root / ".gitignore"
    if retain(ignore):
        try:
            original = ignore.read_bytes() if ignore.exists() else None
            ignore_text = (original or b"").decode("utf-8")
            newline = "\r\n" if "\r\n" in ignore_text else "\n"
            prefix = destination.relative_to(root).as_posix()
            additions = [
                f"/{prefix}/{name}/"
                for name in ("_quarto", "_site", ".cache")
                if f"/{prefix}/{name}/" not in ignore_text.splitlines()
            ]
            if additions:
                updated = (
                    ignore_text
                    + (newline if ignore_text and not ignore_text.endswith("\n") else "")
                    + newline.join(additions)
                    + newline
                )
                edits.append(Edit(ignore, original, updated.encode("utf-8")))
        except (OSError, UnicodeError) as error:
            blockers.append(
                Note(
                    f"Cannot inspect ignore rules {ignore}: {error}",
                    category="Files That Could Not Be Read",
                    path=ignore,
                )
            )

    automation = [root / "Makefile", root / "justfile", root / "tox.ini", root / "noxfile.py"]
    for directory in (root / ".github/workflows", root / "scripts"):
        if directory.exists() and retain(directory):
            automation.extend(tree_files(directory))
    for path in sorted(root.iterdir()):
        if path.suffix in {".sh", ".bash", ".zsh", ".ps1"}:
            automation.append(path)

    def report_walk_error(error: OSError) -> None:
        blockers.append(
            Note(
                f"Cannot inspect implicit documentation inputs: {error}",
                category="Files That Could Not Be Read",
            )
        )

    try:
        ignored = _ignored_paths(root)
    except (OSError, MigrationError) as error:
        blockers.append(
            Note(
                f"Cannot inspect git ignore rules: {error}", category="Files That Could Not Be Read"
            )
        )
        ignored = None
    for directory, children, names in os.walk(root, onerror=report_walk_error, followlinks=False):
        parent = Path(directory)
        children[:] = [name for name in children if _walk_into(parent / name, generated, ignored)]
        for name in names:
            path = parent / name
            if path.suffix == ".termshow":
                retain(path)
                retain(path.with_suffix(".yml"))
                retain(path.with_suffix(".yaml"))
                follow_up.append(
                    Note(
                        f"Review terminal recording and companion YAML paths in {path}",
                        category="Terminal Recordings to Check",
                        path=path,
                    )
                )
    for path in dict.fromkeys(automation):
        if not path.is_file() or not retain(path):
            continue
        try:
            automation_text = path.read_bytes().decode("utf-8")
            if re.search(
                r"great-docs(?:-[\w.-]+)?[/\\]_site|great-docs(?:-[\w.-]+)?/", automation_text
            ):
                follow_up.append(
                    Note(
                        f"Update old output paths in {path}; publish "
                        f"{os.path.relpath(destination / '_site', root)}",
                        category="Old Output Paths to Update",
                        path=path,
                    )
                )
        except (OSError, UnicodeError) as error:
            blockers.append(
                Note(
                    f"Cannot inspect automation {path}: {error}",
                    category="Files That Could Not Be Read",
                    path=path,
                )
            )
    skill = root / "skills" / package / "SKILL.md"
    if package and skill.is_file():
        retain(skill)
    sources = (
        config.get("interlinks", {}).get("sources", {})
        if isinstance(config.get("interlinks"), dict)
        else {}
    )
    if isinstance(sources, dict):
        for name, entry in sources.items():
            value = entry.get("url") if isinstance(entry, dict) else None
            if isinstance(value, str) and local_path(value, root) is not None:
                follow_up.append(
                    Note(
                        f"Review inventory location and published URL together for interlinks.sources.{name}.url: {value}",
                        category="Configuration to Review",
                    )
                )
    site = config.get("site")
    if isinstance(site, dict):
        for name, value in site.items():
            if (
                name != "css"
                and isinstance(value, str)
                and re.search(r"[/\\]|\.(?:html|qmd|css|js|png|svg)$", value)
                and local_path(value, root) is not None
            ):
                follow_up.append(
                    Note(
                        f"Review unsupported Quarto path option site.{name}: {value}",
                        category="Configuration to Review",
                    )
                )
    targets = [move.destination for move in moves]
    targets.extend(edit.path for edit in edits if edit.before is None)
    for target in targets:
        try:
            check_symlinks(target)
            if target.exists() or target.is_symlink():
                blockers.append(
                    Note(
                        f"Destination already exists: {target}",
                        category="Conflicts at the Destination",
                        path=target,
                    )
                )
            for parent in target.parents:
                if parent.exists() and not parent.is_dir():
                    blockers.append(
                        Note(
                            f"Destination component is not a directory: {parent}",
                            category="Conflicts at the Destination",
                            path=parent,
                        )
                    )
        except (OSError, MigrationError) as error:
            blockers.append(Note(str(error), category="Conflicts at the Destination", path=target))
    return result()
