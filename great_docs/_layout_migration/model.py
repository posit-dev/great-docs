"""Immutable migration operations and source fingerprints"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


class MigrationError(ValueError):
    """Input that cannot be migrated without changing its meaning"""


class Note(str):
    """A follow-up item or blocking conflict, grouped by category with an optional excerpt"""

    category: str
    path: Path | None
    line: int | None
    snippet: str | None

    def __new__(
        cls,
        message: str,
        *,
        category: str = "",
        path: Path | None = None,
        line: int | None = None,
        snippet: str | None = None,
    ) -> "Note":
        self = super().__new__(cls, message)
        self.category = category
        self.path = path
        self.line = line
        self.snippet = snippet
        return self


@dataclass(frozen=True)
class Move:
    """A source and its proposed destination"""

    source: Path
    destination: Path


@dataclass(frozen=True)
class Edit:
    """Proposed file bytes at the original path, before any moves"""

    path: Path
    before: bytes | None
    after: bytes


@dataclass(frozen=True)
class Migration:
    """A read-only migration preview with conflicts and retained inputs"""

    package_root: Path
    config_path: Path
    moves: tuple[Move, ...]
    edits: tuple[Edit, ...]
    fingerprints: tuple[tuple[Path, str], ...]
    blockers: tuple[Note, ...]
    follow_up: tuple[Note, ...]


def fingerprint(path: Path) -> str:
    """
    Hash bytes, modes, and the complete directory inventory without following links

    Include missing paths and symlink targets as distinct states. Directory
    digests include every descendant's full relative path and state in sorted
    order, so changed hierarchy, added files, and removed files invalidate a
    preview. Ignore timestamps. Propagate read errors so callers cannot accept
    an incomplete inventory.
    """
    digest = hashlib.sha256()

    def add(value: bytes) -> None:
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)

    def visit(item: Path) -> None:
        add(os.fsencode(item.relative_to(path).as_posix()))
        try:
            mode = item.lstat().st_mode
        except FileNotFoundError:
            add(b"missing")
            return
        add(str(mode).encode())
        if stat.S_ISLNK(mode):
            add(os.fsencode(os.readlink(item)))
        elif stat.S_ISREG(mode):
            try:
                add(item.read_bytes())
            except OSError as error:
                raise MigrationError(f"Cannot fingerprint {item}: {error}") from error
        elif stat.S_ISDIR(mode):
            for child in sorted(item.iterdir()):
                visit(child)
        else:
            raise MigrationError(f"Unsupported filesystem input: {item}")

    visit(path)
    return digest.hexdigest()


def absolute_path(path: Path) -> Path:
    """Normalise a path without concealing symlink components"""
    return Path(os.path.abspath(path))


def moved_path(path: Path, moves: tuple[Move, ...]) -> Path:
    """Resolve a source through its most specific directory move"""
    for move in sorted(moves, key=lambda move: len(move.source.parts), reverse=True):
        if path.is_relative_to(move.source):
            return move.destination / path.relative_to(move.source)
    return path


def check_symlinks(path: Path) -> None:
    """Reject linked path components before reading migration inputs"""
    for component in (path, *path.parents):
        if component.is_symlink():
            raise MigrationError(f"Migration path contains a symlink: {component}")


def tree_files(path: Path) -> list[Path]:
    """Inventory regular files and reject symlinks or unreadable directories"""
    check_symlinks(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise MigrationError(f"Migration source is not a file or directory: {path}")
    files: list[Path] = []
    for child in sorted(path.iterdir()):
        files.extend(tree_files(child))
    return files
