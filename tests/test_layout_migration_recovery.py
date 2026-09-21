from __future__ import annotations

import errno
import importlib
import json
import os
import shlex
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from great_docs._layout import Layout
from great_docs._layout_migration import Edit, MigrationError, Move, analyse
from great_docs._layout_migration.model import fingerprint

if TYPE_CHECKING:
    from great_docs._layout_migration.apply import _Manifest, _Operation


def put(root: Path, name: str, data: bytes) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    put(tmp_path, "pyproject.toml", b'[project]\nname = "sample"\nversion = "1"\n')
    put(tmp_path, "sample/__init__.py", b"")
    put(tmp_path, "great-docs.yml", b"module: sample\nbibliography: refs.bib\n")
    put(tmp_path, "refs.bib", b"@book{x}\n")
    put(tmp_path, "user_guide/page.md", b"[Home](../index.qmd)\n")
    put(tmp_path, "index.qmd", b"# Home\n")
    put(tmp_path, "_freeze/page/cache.json", b"\xff\x00cached")
    put(tmp_path, ".gitignore", b"great-docs/\n")
    (tmp_path / "great-docs.yml").chmod(0o640)
    return tmp_path


def snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        str(path.relative_to(root)): (path.stat().st_mode, path.read_bytes())
        for path in root.rglob("*")
        if path.is_file() and ".great-docs-cache" not in path.parts
    }


def api() -> ModuleType:
    module = importlib.import_module("great_docs._layout_migration")
    assert hasattr(module, "apply"), "Migration application API is missing"
    return module


def test_apply_preserves_modes_cache_and_generated_files(project: Path) -> None:
    put(project, "great-docs/old.html", b"old generated output")
    migration = analyse(Layout.make(project), Path("docs"))
    assert not migration.blockers
    api().apply(migration)
    assert not (project / "great-docs.yml").exists()
    assert (project / "docs/great-docs.yml").read_bytes() == (
        b"module: sample\nbibliography: ../refs.bib\n"
    )
    assert (project / "docs/great-docs.yml").stat().st_mode & 0o777 == 0o640
    assert (project / "docs/_freeze/page/cache.json").read_bytes() == b"\xff\x00cached"
    assert (project / "great-docs/old.html").read_bytes() == b"old generated output"
    assert api().recovery_instructions(project) == ()
    assert not (project / ".great-docs-cache/layout-migration").exists()


@pytest.mark.parametrize("when", ["before", "edit", "move", "freeze"])
def test_handled_failure_restores_original_bytes(
    project: Path, monkeypatch: pytest.MonkeyPatch, when: str
) -> None:
    application = api()
    module = importlib.import_module("great_docs._layout_migration.apply")
    migration = analyse(Layout.make(project), Path("docs"))
    before = snapshot(project)
    save = module._save
    failed = False

    def fail(journal: Path, manifest: _Manifest) -> None:
        nonlocal failed
        selected = any(
            operation.state == "done"
            and (
                (when == "edit" and operation.kind == "edit")
                or (when == "move" and operation.kind == "move")
                or (when == "freeze" and operation.path == "_freeze")
            )
            for operation in manifest.operations
        )
        if not failed and (when == "before" or selected):
            failed = True
            raise OSError("Injected journal failure")
        save(journal, manifest)

    monkeypatch.setattr(module, "_save", fail)
    with pytest.raises(MigrationError, match="Injected"):
        application.apply(migration)
    assert failed
    assert snapshot(project) == before
    assert application.recovery_instructions(project) == ()


def interrupt_after_freeze(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    rename = module._move

    def interrupt(source: Path, destination: Path) -> None:
        rename(source, destination)
        if source == project / "_freeze":
            raise KeyboardInterrupt

    monkeypatch.setattr(module, "_move", interrupt)
    with pytest.raises(KeyboardInterrupt):
        api().apply(analyse(Layout.make(project), Path("docs")))


def test_interrupted_move_keeps_manifest_backups_and_blocks_retry(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = api()
    interrupt_after_freeze(project, monkeypatch)
    journal = project / ".great-docs-cache/layout-migration"
    manifest = json.loads((journal / "manifest.json").read_text())
    freeze = next(
        operation for operation in manifest["operations"] if operation["path"] == "_freeze"
    )
    assert freeze["state"] == "intent"
    assert (project / "docs/_freeze/page/cache.json").read_bytes() == b"\xff\x00cached"
    assert any(
        path.read_bytes().startswith(b"module: sample") for path in (journal / "backups").iterdir()
    )
    instructions = "\n".join(application.recovery_instructions(project))
    assert "_freeze" in instructions and "completion" in instructions
    before = snapshot(project)
    with pytest.raises(MigrationError, match="recovery"):
        application.apply(analyse(Layout.make(project), Path("docs")))
    assert snapshot(project) == before


def test_changed_destination_and_failed_rollback_preserve_user_bytes(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = api()
    module = importlib.import_module("great_docs._layout_migration.apply")
    rename = module._move

    def fail(source: Path, destination: Path) -> None:
        if source == project / "docs/great-docs.yml":
            raise PermissionError("Rollback denied")
        rename(source, destination)
        if source == project / "_freeze":
            put(project, "docs/_freeze/page/cache.json", b"user cache")
            raise OSError("Failure after changed destination")

    monkeypatch.setattr(module, "_move", fail)
    with pytest.raises(MigrationError, match="recovery"):
        application.apply(analyse(Layout.make(project), Path("docs")))
    assert (project / "docs/_freeze/page/cache.json").read_bytes() == b"user cache"
    assert (project / "docs/great-docs.yml").exists()
    assert (project / "refs.bib").read_bytes() == b"@book{x}\n"
    instructions = "\n".join(application.recovery_instructions(project))
    assert "changed" in instructions and "backups" in instructions


@pytest.mark.parametrize("change", ["content", "inventory", "mode", "target", "parent_link"])
def test_stale_preview_aborts_before_source_mutation(project: Path, change: str) -> None:
    migration = analyse(Layout.make(project), Path("docs"))
    if change == "content":
        put(project, "refs.bib", b"new bibliography")
    elif change == "inventory":
        put(project, "_freeze/added/cache", b"new cache")
    elif change == "mode":
        (project / "great-docs.yml").chmod(0o600)
    elif change == "target":
        put(project, "docs/great-docs.yml", b"user destination")
    else:
        (project / "docs").symlink_to(project / "sample", target_is_directory=True)
    before = snapshot(project)
    with pytest.raises(MigrationError):
        api().apply(migration)
    assert snapshot(project) == before
    assert not (project / ".great-docs-cache/layout-migration").exists()


def test_forged_external_move_is_rejected(project: Path, tmp_path: Path) -> None:
    migration = analyse(Layout.make(project), Path("docs"))
    migration = replace(
        migration, moves=(Move(project / "great-docs.yml", tmp_path.parent / "escape.yml"),)
    )
    before = snapshot(project)
    with pytest.raises(MigrationError, match="path|outside"):
        api().apply(migration)
    assert snapshot(project) == before


def test_symlink_journal_is_rejected(project: Path) -> None:
    (project / ".great-docs-cache").mkdir()
    (project / ".great-docs-cache/layout-migration").symlink_to(
        project / "sample", target_is_directory=True
    )
    before = snapshot(project)
    with pytest.raises(MigrationError, match="symlink"):
        api().apply(analyse(Layout.make(project), Path("docs")))
    assert snapshot(project) == before


def test_manifest_paths_are_validated_before_recovery_output(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = api()
    interrupt_after_freeze(project, monkeypatch)
    manifest_path = project / ".great-docs-cache/layout-migration/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["operations"][0]["path"] = "../outside"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(MigrationError, match="path|outside"):
        application.recovery_instructions(project)


def test_failure_after_edit_before_completion_restores_original(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = api()
    module = importlib.import_module("great_docs._layout_migration.apply")
    replace_file = module._replace
    before = snapshot(project)
    failed = False

    def fail(root: Path, operation: _Operation, data: bytes, expected: str) -> None:
        nonlocal failed
        replace_file(root, operation, data, expected)
        if not failed:
            failed = True
            raise OSError("Edit completed without journal completion")

    monkeypatch.setattr(module, "_replace", fail)
    with pytest.raises(MigrationError, match="Original files restored"):
        application.apply(analyse(Layout.make(project), Path("docs")))
    assert snapshot(project) == before
    assert not (project / "docs").exists()


def test_later_edit_to_original_path_is_preserved(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = api()
    module = importlib.import_module("great_docs._layout_migration.apply")
    replace_file = module._replace

    def fail(root: Path, operation: _Operation, data: bytes, expected: str) -> None:
        replace_file(root, operation, data, expected)
        put(root, operation.path, b"user revision")
        raise OSError("Edited file changed afterwards")

    monkeypatch.setattr(module, "_replace", fail)
    with pytest.raises(MigrationError, match="recovery"):
        application.apply(analyse(Layout.make(project), Path("docs")))
    assert (project / "great-docs.yml").read_bytes() == b"user revision"
    assert (project / "_freeze/page/cache.json").read_bytes() == b"\xff\x00cached"
    assert "changed" in "\n".join(application.recovery_instructions(project))


@pytest.mark.parametrize("field", ["path", "destination", "stage", "backup", "replacement"])
def test_recovery_rejects_unsafe_paths_in_every_field(
    project: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    application = api()
    interrupt_after_freeze(project, monkeypatch)
    manifest_path = project / ".great-docs-cache/layout-migration/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["operations"][0][field] = "/outside"
    manifest_path.write_text(json.dumps(manifest))
    before = snapshot(project)
    with pytest.raises(MigrationError, match="path"):
        application.recovery_instructions(project)
    assert snapshot(project) == before


def test_recovery_quotes_shell_metacharacters(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = api()
    quoted_root = project.with_name(project.name + " ' $(touch bad)")
    project.rename(quoted_root)
    project = quoted_root
    source = project / "_freeze" / "space ' $(touch bad).json"
    source.write_bytes(b"cache")
    interrupt_after_freeze(project, monkeypatch)
    instructions = "\n".join(application.recovery_instructions(project))
    assert shlex.quote(str(project / "docs/_freeze")) in instructions
    assert not (project / "bad").exists()


@pytest.mark.parametrize("target", ["external", "symlink", "journal", "overlap"])
def test_forged_edit_is_rejected_without_writes(project: Path, target: str) -> None:
    migration = analyse(Layout.make(project), Path("docs"))
    if target == "external":
        path = project.parent / "outside-new.txt"
    elif target == "symlink":
        (project / "link").symlink_to(project / "sample", target_is_directory=True)
        path = project / "link/new.txt"
    elif target == "journal":
        path = project / ".great-docs-cache/layout-migration/forged"
    else:
        path = project / "docs/user_guide/page.md"
    migration = replace(migration, edits=(*migration.edits, Edit(path, None, b"forged")))
    before = snapshot(project)
    with pytest.raises(MigrationError):
        api().apply(migration)
    assert snapshot(project) == before


def test_external_reviewed_input_is_rechecked_and_never_mutated(project: Path) -> None:
    external = put(project.parent, project.name + "-external", b"retained external bytes")
    migration = analyse(Layout.make(project), Path("docs"))
    migration = replace(
        migration, fingerprints=(*migration.fingerprints, (external, fingerprint(external)))
    )
    external.write_bytes(b"later external bytes")
    before = snapshot(project)
    with pytest.raises(MigrationError, match="changed"):
        api().apply(migration)
    assert snapshot(project) == before
    assert external.read_bytes() == b"later external bytes"


def test_recovered_new_cache_files_roll_back_without_touching_builds(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from great_docs._utils import QUARTO_YML_HEADER

    cache = project / "_freeze"
    cache.rename(project / "saved-cache")
    put(project, "great-docs/_quarto.yml", QUARTO_YML_HEADER.encode())
    put(project, "great-docs/_freeze/cache/result", b"\xff\x00recovered")
    migration = analyse(Layout.make(project), Path("docs"))
    assert not migration.blockers
    before = snapshot(project)
    application = api()
    module = importlib.import_module("great_docs._layout_migration.apply")
    save = module._save
    failed = False

    def fail(journal: Path, manifest: _Manifest) -> None:
        nonlocal failed
        if not failed and any(
            operation.kind == "move" and operation.state == "done"
            for operation in manifest.operations
        ):
            failed = True
            raise OSError("Failure after recovered cache writes")
        save(journal, manifest)

    monkeypatch.setattr(module, "_save", fail)
    with pytest.raises(MigrationError, match="Original files restored"):
        application.apply(migration)
    assert snapshot(project) == before
    assert not (project / "docs").exists()


def test_invalid_final_configuration_restores_original(project: Path) -> None:
    migration = analyse(Layout.make(project), Path("docs"))
    migration = replace(
        migration,
        edits=tuple(
            replace(edit, after=b"- invalid configuration")
            if edit.path == migration.config_path
            else edit
            for edit in migration.edits
        ),
    )
    before = snapshot(project)
    with pytest.raises(MigrationError, match="configuration"):
        api().apply(migration)
    assert snapshot(project) == before


def test_user_file_added_to_journal_survives_cleanup(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = api()
    module = importlib.import_module("great_docs._layout_migration.apply")
    save = module._save

    def add_file(journal: Path, manifest: _Manifest) -> None:
        save(journal, manifest)
        if manifest.status == "complete":
            put(journal, "user.txt", b"user journal note")

    monkeypatch.setattr(module, "_save", add_file)
    with pytest.raises(MigrationError, match="cleanup"):
        application.apply(analyse(Layout.make(project), Path("docs")))
    assert (
        project / ".great-docs-cache/layout-migration/user.txt"
    ).read_bytes() == b"user journal note"
    assert (project / "docs/_freeze/page/cache.json").read_bytes() == b"\xff\x00cached"


def test_repeated_apply_of_migrated_layout_is_noop(project: Path) -> None:
    application = api()
    application.apply(analyse(Layout.make(project), Path("docs")))
    before = snapshot(project)
    application.apply(analyse(Layout.make(project), Path("docs")))
    assert snapshot(project) == before


def test_move_refuses_destination_created_after_check(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    absent = module._absent
    source = project / "great-docs.yml"
    destination = project / "raced.yml"
    original = source.read_bytes()

    def race(path: Path) -> None:
        absent(path)
        if path == destination:
            path.write_bytes(b"later user file")

    monkeypatch.setattr(module, "_absent", race)
    with pytest.raises(FileExistsError):
        module._move(source, destination)
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"later user file"


def test_unavailable_exclusive_rename_aborts_before_writes(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    before = snapshot(project)

    def unavailable() -> Callable[[Path, Path], None]:
        raise MigrationError("Exclusive rename is unavailable")

    monkeypatch.setattr(module, "_rename_function", unavailable, raising=False)
    with pytest.raises(MigrationError, match="unavailable"):
        api().apply(analyse(Layout.make(project), Path("docs")))
    assert snapshot(project) == before
    assert not (project / ".great-docs-cache/layout-migration").exists()


def test_exclusive_rename_propagates_filesystem_errors(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    source = project / "great-docs.yml"
    destination = project / "cross-device.yml"
    original = source.read_bytes()

    def cross_device(source: Path, destination: Path) -> None:
        raise OSError(errno.EXDEV, "Cross-device rename refused")

    monkeypatch.setattr(module, "_rename_function", lambda: cross_device, raising=False)
    with pytest.raises(OSError) as failure:
        module._move(source, destination)
    assert failure.value.errno == errno.EXDEV
    assert source.read_bytes() == original
    assert not destination.exists()


def test_user_directory_in_journal_preserves_backups(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    save = module._save

    def add_directory(journal: Path, manifest: _Manifest) -> None:
        save(journal, manifest)
        if manifest.status == "complete":
            (journal / "backups/user-directory").mkdir()

    monkeypatch.setattr(module, "_save", add_directory)
    with pytest.raises(MigrationError, match="cleanup"):
        api().apply(analyse(Layout.make(project), Path("docs")))
    journal = project / ".great-docs-cache/layout-migration"
    assert (journal / "backups/user-directory").is_dir()
    assert (journal / "backups/0").read_bytes().startswith(b"module: sample")
    assert (journal / "manifest.json").exists()


def test_destination_change_during_rollback_intent_is_preserved(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    save = module._save
    failed = False

    def change_destination(journal: Path, manifest: _Manifest) -> None:
        nonlocal failed
        if not failed and any(
            operation.path == "_freeze" and operation.state == "done"
            for operation in manifest.operations
        ):
            failed = True
            raise OSError("Rollback required")
        save(journal, manifest)
        if any(
            operation.path == "_freeze" and operation.state == "undo_intent"
            for operation in manifest.operations
        ):
            put(project, "docs/_freeze/page/cache.json", b"later user cache")

    monkeypatch.setattr(module, "_save", change_destination)
    with pytest.raises(MigrationError, match="recovery"):
        api().apply(analyse(Layout.make(project), Path("docs")))
    assert (project / "docs/_freeze/page/cache.json").read_bytes() == b"later user cache"
    assert not (project / "_freeze").exists()
    assert api().recovery_instructions(project)


def test_windows_selects_exclusive_os_rename(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32"))
    assert module._rename_function() is module.os.rename


def test_unrecognised_platform_refuses_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="unsupported"))
    with pytest.raises(MigrationError, match="unavailable"):
        module._rename_function()


@pytest.mark.parametrize("status", ["complete", "rolled_back"])
def test_cleanup_interrupted_after_backup_deletion_never_recommends_rollback(
    project: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    journal = project / ".great-docs-cache/layout-migration"
    unlink = Path.unlink
    save = module._save
    before = snapshot(project)

    def interrupt_cleanup(path: Path, missing_ok: bool = False) -> None:
        unlink(path, missing_ok=missing_ok)
        if path == journal / "backups/0":
            raise KeyboardInterrupt

    def fail_after_edit(path: Path, manifest: _Manifest) -> None:
        if status == "rolled_back" and any(
            operation.kind == "edit" and operation.state == "done"
            for operation in manifest.operations
        ):
            raise OSError("Request rollback before cleanup interruption")
        save(path, manifest)

    monkeypatch.setattr(Path, "unlink", interrupt_cleanup)
    monkeypatch.setattr(module, "_save", fail_after_edit)
    with pytest.raises(KeyboardInterrupt):
        api().apply(analyse(Layout.make(project), Path("docs")))
    data = json.loads((journal / "manifest.json").read_text())
    assert data["status"] == status
    assert not (journal / "backups/0").exists()
    if status == "rolled_back":
        assert snapshot(project) == before
    else:
        assert (project / "docs/great-docs.yml").read_bytes() == (
            b"module: sample\nbibliography: ../refs.bib\n"
        )
        assert (project / "docs/_freeze/page/cache.json").read_bytes() == b"\xff\x00cached"
    preserved = snapshot(project)
    instructions = "\n".join(api().recovery_instructions(project))
    assert "cleanup" in instructions.lower()
    assert "archive" in instructions.lower()
    assert "restore with:" not in instructions
    assert "cp -p" not in instructions
    assert "rmdir" not in instructions
    assert "backups/0" not in instructions
    assert snapshot(project) == preserved


@pytest.mark.parametrize("state", ["planned", "undone"])
@pytest.mark.parametrize("kind", ["mkdir", "edit", "move"])
def test_active_recovery_omits_reversal_for_inactive_operations(
    project: Path, monkeypatch: pytest.MonkeyPatch, state: str, kind: str
) -> None:
    interrupt_after_freeze(project, monkeypatch)
    journal = project / ".great-docs-cache/layout-migration"
    manifest_path = journal / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    operation = next(item for item in manifest["operations"] if item["kind"] == kind)
    operation["state"] = state
    manifest["operations"] = [operation]
    manifest_path.write_text(json.dumps(manifest))
    preserved = snapshot(project)
    instructions = "\n".join(api().recovery_instructions(project))
    assert state in instructions
    assert "restore with:" not in instructions
    assert "cp -p" not in instructions
    assert "rmdir" not in instructions
    assert "command-created file manually" not in instructions
    assert snapshot(project) == preserved


def test_windows_recovery_uses_literal_quoted_powershell_commands(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    quoted_root = project.with_name(project.name + " ' [literal] $(touch bad)")
    project.rename(quoted_root)
    project = quoted_root
    interrupt_after_freeze(project, monkeypatch)
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32"))
    preserved = snapshot(project)
    instructions = "\n".join(api().recovery_instructions(project))
    assert "PowerShell" in instructions
    assert "POSIX" not in instructions
    assert "'" + str(project).replace("'", "''") in instructions
    assert "[System.IO.Directory]::Move(" in instructions
    assert "[System.IO.File]::Move(" in instructions
    assert "[System.IO.File]::Copy(" in instructions and ", $false)" in instructions
    assert "[System.IO.Directory]::Delete(" in instructions
    assert "Get-FileHash -LiteralPath" in instructions
    assert "mv -n" not in instructions and "cp -p" not in instructions
    assert "-Recurse" not in instructions and "-Force" not in instructions
    assert snapshot(project) == preserved


def test_windows_incomplete_journal_path_uses_powershell_quoting(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    quoted_root = project.with_name(project.name + " ' $(touch bad)")
    project.rename(quoted_root)
    journal = quoted_root / ".great-docs-cache/layout-migration"
    journal.mkdir(parents=True)
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32"))
    instructions = "\n".join(api().recovery_instructions(quoted_root))
    assert "'" + str(journal).replace("'", "''") + "'" in instructions


def test_windows_recovery_escapes_smart_single_quotes(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("great_docs._layout_migration.apply")
    quoted_root = project.with_name(project.name + " ‘$(touch bad)’‚‛")
    project.rename(quoted_root)
    journal = quoted_root / ".great-docs-cache/layout-migration"
    journal.mkdir(parents=True)
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32"))
    instructions = "\n".join(api().recovery_instructions(quoted_root))
    assert "‘‘$(touch bad)’’‚‚‛‛" in instructions
