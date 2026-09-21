"""Apply reviewed layout changes with a recoverable filesystem journal"""

from __future__ import annotations

import ctypes
import json
import os
import shlex
import stat
import sys
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from great_docs._layout import Layout

from .content import read_config
from .model import (
    Migration,
    MigrationError,
    absolute_path,
    check_symlinks,
    fingerprint,
    moved_path,
    tree_files,
)

_JOURNAL = Path(".great-docs-cache/layout-migration")
_STATES = {"planned", "intent", "done", "undo_intent", "undone"}


@dataclass
class _Operation:
    kind: str
    path: str
    before: str
    after: str
    mode: int = 0
    destination: str = ""
    backup: str = ""
    replacement: str = ""
    stage: str = ""
    state: str = "planned"


@dataclass
class _Manifest:
    config: str
    operations: list[_Operation] = field(default_factory=list)
    schema_version: int = 1
    status: str = "active"


def _relative(root: Path, path: Path) -> str:
    if ".." in path.parts or not path.is_absolute():
        raise MigrationError(f"Migration path must be absolute and contained: {path}")
    check_symlinks(path)
    if path == root or not path.is_relative_to(root):
        raise MigrationError(f"Migration path is outside the package: {path}")
    relative = path.relative_to(root)
    if relative.is_relative_to(_JOURNAL) or _JOURNAL.is_relative_to(relative):
        raise MigrationError(f"Migration path overlaps its recovery journal: {path}")
    return relative.as_posix()


def _target(root: Path, relative: str, *, journal: bool = False) -> Path:
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or path == Path("."):
        raise MigrationError(f"Unsafe recorded migration path: {relative!r}")
    result = root / path
    check_symlinks(result)
    if not journal:
        _relative(root, result)
    return result


def _verify(path: Path, expected: str, *, read_only_external: bool = False) -> None:
    if not read_only_external:
        check_symlinks(path)
    if path.is_dir() and not path.is_symlink():
        tree_files(path)
    if fingerprint(path) != expected:
        raise MigrationError(f"Migration input changed; request a fresh preview: {path}")


def _absent(path: Path) -> None:
    check_symlinks(path)
    if path.exists():
        raise MigrationError(f"Migration destination already exists: {path}")
    for parent in path.parents:
        if parent.exists() and not parent.is_dir():
            raise MigrationError(f"Migration destination parent is not a directory: {parent}")


def _validate(migration: Migration) -> None:
    root = migration.package_root
    if root != absolute_path(root) or not root.is_dir():
        raise MigrationError(f"Invalid package root: {root}")
    check_symlinks(root)
    _relative(root, migration.config_path)
    if migration.blockers:
        raise MigrationError("Migration is blocked: " + "; ".join(migration.blockers))
    reviewed = dict(migration.fingerprints)
    for path, expected in reviewed.items():
        if not path.is_absolute() or ".." in path.parts:
            raise MigrationError(f"Invalid reviewed path: {path}")
        _verify(path, expected, read_only_external=not path.is_relative_to(root))
    sources = [move.source for move in migration.moves]
    destinations = [move.destination for move in migration.moves]
    for index, move in enumerate(migration.moves):
        _relative(root, move.source)
        _relative(root, move.destination)
        if move.source not in reviewed or not move.source.exists():
            raise MigrationError(f"Move source has no reviewed inventory: {move.source}")
        if any(
            move.source.is_relative_to(other) or other.is_relative_to(move.source)
            for other in sources[:index]
        ) or any(
            move.destination.is_relative_to(other) or other.is_relative_to(move.destination)
            for other in destinations[:index] + sources
        ):
            raise MigrationError(f"Migration paths overlap: {move.source}, {move.destination}")
        _absent(move.destination)
    edited: set[Path] = set()
    for edit in migration.edits:
        _relative(root, edit.path)
        if edit.path in edited or any(
            edit.path.is_relative_to(target) or target.is_relative_to(edit.path)
            for target in destinations
        ):
            raise MigrationError(f"Migration edit paths overlap: {edit.path}")
        edited.add(edit.path)
        if edit.before is None:
            _absent(edit.path)
        elif not edit.path.is_file() or edit.path.read_bytes() != edit.before:
            raise MigrationError(f"Migration input changed; request a fresh preview: {edit.path}")
        elif not any(edit.path.is_relative_to(path) for path in reviewed):
            raise MigrationError(f"Edited file has no reviewed fingerprint: {edit.path}")
    if any(a != b and (a.is_relative_to(b) or b.is_relative_to(a)) for a in edited for b in edited):
        raise MigrationError("Migration edits overlap files and directories")


def _write(path: Path, content: bytes, mode: int) -> None:
    check_symlinks(path)
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        if os.name == "nt":
            os.chmod(path, stat.S_IMODE(mode))
        else:
            os.fchmod(stream.fileno(), stat.S_IMODE(mode))
        os.fsync(stream.fileno())


def _encoded(manifest: _Manifest) -> bytes:
    return (json.dumps(asdict(manifest), indent=2, ensure_ascii=True) + "\n").encode()


def _save(journal: Path, manifest: _Manifest) -> None:
    check_symlinks(journal / "manifest.json")
    temporary = journal / "manifest.next"
    _write(temporary, _encoded(manifest), 0o600)
    os.replace(temporary, journal / "manifest.json")


def _prepare(migration: Migration, journal: Path, manifest: _Manifest) -> None:
    root = migration.package_root
    parents: set[Path] = set()
    for path in [
        *(edit.path for edit in migration.edits),
        *(move.destination for move in migration.moves),
    ]:
        parent = path.parent
        while parent != root and not parent.exists():
            parents.add(parent)
            parent = parent.parent
    for parent in sorted(parents, key=lambda path: (len(path.parts), path)):
        manifest.operations.append(
            _Operation("mkdir", _relative(root, parent), fingerprint(parent), "")
        )
    (journal / "backups").mkdir()
    (journal / "proposed").mkdir()
    for index, edit in enumerate(migration.edits):
        mode = edit.path.stat().st_mode if edit.before is not None else stat.S_IFREG | 0o644
        backup = f"backups/{index}" if edit.before is not None else ""
        replacement = f"proposed/{index}"
        if backup:
            _write(journal / backup, edit.before, mode)
        _write(journal / replacement, edit.after, mode)
        manifest.operations.append(
            _Operation(
                "edit",
                _relative(root, edit.path),
                fingerprint(edit.path),
                fingerprint(journal / replacement),
                mode=mode,
                backup=backup,
                replacement=replacement,
                stage=_relative(
                    root, edit.path.with_name(f".{edit.path.name}.migration-{uuid.uuid4().hex}")
                ),
            )
        )
    for move in migration.moves:
        expected = fingerprint(move.source)
        manifest.operations.append(
            _Operation(
                "move",
                _relative(root, move.source),
                expected,
                expected,
                destination=_relative(root, move.destination),
            )
        )
    _save(journal, manifest)


def _rename_function() -> Callable[[Path, Path], None]:
    """Select an exclusive rename primitive without an overwriting fallback"""
    if sys.platform == "win32":
        return os.rename
    if sys.platform not in {"darwin", "linux"}:
        raise MigrationError(f"Exclusive rename is unavailable on {sys.platform}")
    library = ctypes.CDLL(None, use_errno=True)
    name = "renamex_np" if sys.platform == "darwin" else "renameat2"
    try:
        rename = getattr(library, name)
    except AttributeError as error:
        raise MigrationError(f"Exclusive rename is unavailable: {name}") from error
    darwin = sys.platform == "darwin"
    rename.argtypes = (
        [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        if darwin
        else [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    )
    rename.restype = ctypes.c_int

    def exclusive(source: Path, destination: Path) -> None:
        if darwin:
            result = rename(os.fsencode(source), os.fsencode(destination), 0x00000004)
        else:
            result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
        if result != 0:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number), str(source), None, str(destination))

    return exclusive


def _preflight_moves(migration: Migration) -> None:
    rename = _rename_function()
    for move in migration.moves:
        parent = move.destination.parent
        while not parent.exists():
            parent = parent.parent
        if move.source.stat().st_dev != parent.stat().st_dev:
            raise MigrationError(
                f"Cross-filesystem migration move is unsupported: {move.source} to {move.destination}"
            )
    probe = migration.package_root / f".migration-probe-{uuid.uuid4().hex}"
    try:
        rename(probe, probe.with_suffix(".target"))
    except FileNotFoundError:
        return
    raise MigrationError("Exclusive rename availability could not be verified")


def _move(source: Path, destination: Path) -> None:
    _absent(destination)
    check_symlinks(source)
    _rename_function()(source, destination)


def _replace(root: Path, operation: _Operation, data: bytes, expected: str) -> None:
    path = _target(root, operation.path)
    stage = _target(root, operation.stage)
    _write(stage, data, operation.mode)
    _verify(stage, operation.before if operation.state == "undo_intent" else operation.after)
    _verify(path, expected)
    if not operation.backup:
        _move(stage, path)
    else:
        os.replace(stage, path)


def _perform(root: Path, journal: Path, manifest: _Manifest) -> None:
    for operation in manifest.operations:
        path = _target(root, operation.path)
        if operation.kind == "edit":
            for move in manifest.operations:
                if move.kind == "move" and path.is_relative_to(root / move.path):
                    _verify(root / move.path, move.after)
        _verify(path, operation.after if operation.kind == "move" else operation.before)
        operation.state = "intent"
        _save(journal, manifest)
        _verify(path, operation.after if operation.kind == "move" else operation.before)
        if operation.kind == "mkdir":
            _absent(path)
            path.mkdir()
            operation.mode = path.stat().st_mode
            operation.after = fingerprint(path)
        elif operation.kind == "edit":
            proposed = _target(journal, operation.replacement, journal=True)
            _verify(proposed, operation.after)
            _replace(root, operation, proposed.read_bytes(), operation.before)
            for move in manifest.operations:
                if move.kind == "move" and path.is_relative_to(root / move.path):
                    move.after = fingerprint(root / move.path)
        else:
            _move(path, _target(root, operation.destination))
        operation.state = "done"
        _save(journal, manifest)


def _rollback(root: Path, journal: Path, manifest: _Manifest) -> bool:
    complete = True
    for operation in reversed(manifest.operations):
        if operation.state in {"planned", "undone"}:
            continue
        try:
            path = _target(root, operation.path)
            if operation.kind == "move":
                destination = _target(root, operation.destination)
                if not destination.exists() and fingerprint(path) == operation.after:
                    operation.state = "undone"
                    _save(journal, manifest)
                    continue
                _absent(path)
                _verify(destination, operation.after)
                operation.state = "undo_intent"
                _save(journal, manifest)
                _verify(destination, operation.after)
                _move(destination, path)
            elif operation.kind == "edit":
                stage = _target(root, operation.stage)
                if stage.exists():
                    _verify(stage, operation.after)
                    stage.unlink()
                if fingerprint(path) != operation.before:
                    _verify(path, operation.after)
                    operation.state = "undo_intent"
                    _save(journal, manifest)
                    if operation.backup:
                        backup = _target(journal, operation.backup, journal=True)
                        _verify(backup, operation.before)
                        _replace(root, operation, backup.read_bytes(), operation.after)
                    else:
                        _verify(path, operation.after)
                        path.unlink()
            else:
                if path.exists():
                    _verify(path, operation.after)
                    operation.state = "undo_intent"
                    _save(journal, manifest)
                    _verify(path, operation.after)
                    path.rmdir()
            operation.state = "undone"
            _save(journal, manifest)
        except (OSError, ValueError):
            complete = False
    return complete


def _clean(journal: Path, manifest: _Manifest) -> None:
    expected: dict[Path, str] = {}
    for operation in manifest.operations:
        if operation.backup:
            expected[journal / operation.backup] = operation.before
        if operation.replacement:
            expected[journal / operation.replacement] = operation.after
    files = set(tree_files(journal))
    directories = {path for path in journal.rglob("*") if path.is_dir()}
    manifest_path = journal / "manifest.json"
    if files - {*expected, manifest_path} or directories - {
        journal / "backups",
        journal / "proposed",
    }:
        raise MigrationError(f"Recovery journal contains unrecognised files: {journal}")
    for path, digest in expected.items():
        _verify(path, digest)
    if manifest_path.exists() and manifest_path.read_bytes() != _encoded(manifest):
        raise MigrationError(f"Recovery manifest changed: {manifest_path}")
    for path, digest in expected.items():
        _verify(path, digest)
        path.unlink()
    if manifest_path.exists():
        manifest_path.unlink()
    for name in ("backups", "proposed"):
        path = journal / name
        if path.exists():
            path.rmdir()
    journal.rmdir()


def apply(migration: Migration) -> None:
    """
    Apply a reviewed migration and retain evidence when recovery needs inspection

    Recheck all reviewed inputs before changing sources. Restore command-owned
    results after handled failures only while their bytes and modes match.
    Interrupted or incomplete transactions block another migration until their
    recorded paths and originals have been recovered manually.

    Parameters
    ----------
    migration
        Reviewed operations produced by migration analysis.

    Raises
    ------
    MigrationError
        If the preview is stale, a path is unsafe, recovery is pending, or an
        operation fails. The error reports whether manual recovery remains.
    """
    root = migration.package_root
    journal = root / _JOURNAL
    check_symlinks(journal)
    if journal.exists():
        raise MigrationError(
            f"Pending migration recovery: {journal}. Inspect recovery instructions first."
        )
    try:
        _validate(migration)
    except OSError as error:
        raise MigrationError(f"Cannot revalidate migration: {error}") from error
    if not migration.moves and not migration.edits:
        return
    try:
        _preflight_moves(migration)
    except OSError as error:
        raise MigrationError(f"Exclusive rename preflight failed: {error}") from error
    manifest = _Manifest(_relative(root, moved_path(migration.config_path, migration.moves)))
    try:
        journal.parent.mkdir(exist_ok=True)
        check_symlinks(journal)
        journal.mkdir(mode=0o700)
    except OSError as error:
        raise MigrationError(
            f"Cannot create migration recovery journal {journal}: {error}"
        ) from error
    try:
        _prepare(migration, journal, manifest)
        _validate(migration)
        _perform(root, journal, manifest)
        config = _target(root, manifest.config)
        read_config(config.read_text(encoding="utf-8"))
        Layout.make(root, config)
        for operation in manifest.operations:
            if operation.kind == "move":
                _absent(_target(root, operation.path))
                _verify(_target(root, operation.destination), operation.after)
            elif operation.kind == "edit":
                _verify(moved_path(root / operation.path, migration.moves), operation.after)
        manifest.status = "complete"
        _save(journal, manifest)
    except (OSError, ValueError) as error:
        complete = _rollback(root, journal, manifest)
        if complete:
            try:
                manifest.status = "rolled_back"
                _save(journal, manifest)
                _clean(journal, manifest)
            except (OSError, ValueError):
                complete = False
        suffix = "Original files restored." if complete else f"Manual recovery required: {journal}."
        raise MigrationError(f"Migration failed: {error}. {suffix}") from error
    try:
        _clean(journal, manifest)
    except (OSError, ValueError) as error:
        raise MigrationError(
            f"Migration applied; recovery journal cleanup requires inspection: {journal}: {error}"
        ) from error


def _load(root: Path, journal: Path) -> _Manifest:
    check_symlinks(journal / "manifest.json")
    try:
        data = json.loads((journal / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {
            "config",
            "operations",
            "schema_version",
            "status",
        }:
            raise MigrationError("Invalid migration recovery manifest fields")
        if data["schema_version"] != 1 or data["status"] not in {
            "active",
            "complete",
            "rolled_back",
        }:
            raise MigrationError("Unsupported migration recovery manifest schema or status")
        _target(root, data["config"])
        if not isinstance(data["operations"], list):
            raise MigrationError("Invalid migration recovery operations")
        operations = []
        for item in data["operations"]:
            if not isinstance(item, dict) or set(item) != set(_Operation.__dataclass_fields__):
                raise MigrationError("Invalid migration recovery operation fields")
            if any(not isinstance(value, str) for key, value in item.items() if key != "mode"):
                raise MigrationError("Invalid migration recovery operation values")
            operation = _Operation(**item)
            if operation.kind not in {"mkdir", "edit", "move"} or operation.state not in _STATES:
                raise MigrationError("Invalid migration recovery operation kind or state")
            if not isinstance(operation.mode, int) or not 0 <= operation.mode <= 0o177777:
                raise MigrationError("Invalid migration recovery mode")
            for digest in (operation.before, operation.after):
                if digest and (
                    len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)
                ):
                    raise MigrationError("Invalid migration recovery digest")
            for relative in (operation.path, operation.destination, operation.stage):
                if relative:
                    _target(root, relative)
            for relative, directory in (
                (operation.backup, "backups"),
                (operation.replacement, "proposed"),
            ):
                if relative:
                    path = _target(journal, relative, journal=True)
                    if path.parent != journal / directory or not path.name.isdecimal():
                        raise MigrationError(f"Unsafe recorded backup path: {relative!r}")
            operations.append(operation)
        return _Manifest(data["config"], operations, data["schema_version"], data["status"])
    except (OSError, ValueError, TypeError) as error:
        raise MigrationError(f"Cannot inspect migration recovery manifest: {error}") from error


def recovery_instructions(package_root: Path) -> tuple[str, ...]:
    """
    Describe recorded operations and commands for manual recovery without writes

    Validate every recorded path before returning instructions. Report current
    bytes against the expected operation results, including an operation whose
    filesystem change preceded its completion record. Preserve changed files
    and backups for a human to compare and merge. Limit completed and rolled-back
    journals to cleanup guidance. Omit reversal commands for operations that
    were never started or were already undone.
    """
    windows = sys.platform == "win32"

    def quote(path: Path) -> str:
        if windows:
            escaped = str(path)
            for character in "'\u2018\u2019\u201a\u201b":
                escaped = escaped.replace(character, character * 2)
            return "'" + escaped + "'"
        return shlex.quote(str(path))

    def move_command(source: Path, destination: Path) -> str:
        before, after = quote(source), quote(destination)
        if windows:
            return (
                f"if ([System.IO.Directory]::Exists({before})) {{ "
                f"[System.IO.Directory]::Move({before}, {after}) "
                f"}} else {{ [System.IO.File]::Move({before}, {after}) }}"
            )
        return f"mv -n {before} {after}"

    root = absolute_path(package_root)
    journal = root / _JOURNAL
    check_symlinks(journal)
    if not journal.exists():
        return ()
    if not (journal / "manifest.json").exists():
        return (
            f"Inspect the incomplete recovery journal at {quote(journal)}; no complete manifest was recorded. Preserve its files before moving it aside.",
        )
    manifest = _load(root, journal)
    lines = [
        f"Inspect the {manifest.status} migration journal: {quote(journal / 'manifest.json')}.",
        "Run the commands below in PowerShell."
        if windows
        else "Run the commands below in a POSIX shell.",
    ]
    archive = move_command(
        journal, journal.with_name("layout-migration-recovered-" + uuid.uuid4().hex)
    )
    if manifest.status in {"complete", "rolled_back"}:
        result = (
            "Migration completed" if manifest.status == "complete" else "Migration was rolled back"
        )
        lines.extend(
            (
                f"{result}; only journal cleanup remains. Preserve the current project files.",
                f"After inspecting the remaining journal files, archive the journal with: {archive}",
            )
        )
        return tuple(lines)
    lines.append(
        "Preserve later user edits before running any recovery commands; compare and merge changed files manually."
    )
    for operation in reversed(manifest.operations):
        path = _target(root, operation.path)
        state = operation.state
        if state in {"intent", "undo_intent"}:
            state += " (no completion record; inspect both locations)"
        lines.append(f"Inspect {operation.kind} {quote(path)}: {state}.")
        if operation.state in {"planned", "undone"}:
            continue
        if operation.kind == "move":
            destination = _target(root, operation.destination)
            matches = fingerprint(destination) == operation.after
            lines.append(
                f"Inspect destination {quote(destination)}: {'matches expected result' if matches else 'missing or changed since migration'}."
            )
            lines.append(
                f"After verifying the original path is absent and preserving any changed files, restore with: {move_command(destination, path)}"
            )
        elif operation.kind == "edit":
            moves = [
                move
                for move in manifest.operations
                if move.kind == "move" and path.is_relative_to(root / move.path)
            ]
            current = path
            if moves:
                move = moves[0]
                destination = root / move.destination / path.relative_to(root / move.path)
                check_symlinks(destination)
                if destination.exists():
                    current = destination
            matches = fingerprint(current) == operation.after
            lines.append(
                f"Inspect current file {quote(current)}: {'matches expected result' if matches else 'missing or changed since migration'}."
            )
            if operation.backup:
                backup = _target(journal, operation.backup, journal=True)
                comparison = (
                    f"Get-FileHash -LiteralPath @({quote(backup)}, {quote(current)}) -Algorithm SHA256"
                    if windows
                    else f"diff -u {quote(backup)} {quote(current)}"
                )
                restore = (
                    f"[System.IO.File]::Copy({quote(backup)}, {quote(path)}, $false)"
                    if windows
                    else f"cp -p -n {quote(backup)} {quote(path)}"
                )
                lines.append(
                    f"Compare the original bytes and mode {stat.S_IMODE(operation.mode):04o}: {comparison}"
                )
                lines.append(
                    f"After restoring moved directories and preserving the current file elsewhere, restore the absent original path with: {restore}"
                )
            else:
                lines.append(
                    f"Preserve or remove the command-created file manually after inspection: {quote(current)}."
                )
            if operation.stage and (root / operation.stage).exists():
                lines.append(
                    f"Inspect the staged replacement before removing it: {quote(root / operation.stage)}."
                )
        else:
            remove_empty = (
                f"[System.IO.Directory]::Delete({quote(path)}, $false)"
                if windows
                else f"rmdir {quote(path)}"
            )
            lines.append(
                f"After recovering its contents, remove the empty command-created directory with: {remove_empty}"
            )
    lines.append(
        f"After verifying recovery, archive the journal outside its active location with: {archive}"
    )
    return tuple(lines)
