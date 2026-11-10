"""API snapshot and command-line comparison"""

from __future__ import annotations

from pathlib import Path

from great_docs._api_evolution.model import (
    ApiDiff,
    ApiSnapshot,
    CliChange,
    CliCommandInfo,
    ParameterChange,
    ParameterInfo,
    SymbolChange,
    SymbolInfo,
)


def diff_snapshots(old: ApiSnapshot, new: ApiSnapshot) -> ApiDiff:
    """
    Compute the diff between two API snapshots.

    Parameters
    ----------
    old
        The earlier API snapshot.
    new
        The later API snapshot.

    Returns
    -------
    ApiDiff
    """
    result = ApiDiff(
        old_version=old.version,
        new_version=new.version,
        package_name=new.package_name,
    )

    old_names = set(old.symbols)
    new_names = set(new.symbols)

    # Added symbols
    for name in sorted(new_names - old_names):
        sym = new.symbols[name]
        result.added.append(
            SymbolChange(
                symbol=name,
                change_type="added",
                details=[f"New {sym.kind}: {name}"],
            )
        )

    # Removed symbols — always breaking
    for name in sorted(old_names - new_names):
        sym = old.symbols[name]
        result.removed.append(
            SymbolChange(
                symbol=name,
                change_type="removed",
                details=[f"Removed {sym.kind}: {name}"],
                is_breaking=True,
                migration_hint=f"'{name}' was removed. Check the changelog for a replacement.",
            )
        )

    # Changed symbols
    for name in sorted(old_names & new_names):
        old_sym = old.symbols[name]
        new_sym = new.symbols[name]
        change = _diff_symbol(name, old_sym, new_sym)
        if change is not None:
            result.changed.append(change)

    # CLI changes
    result.cli_changes = _diff_cli(old.cli_commands, new.cli_commands)

    return result


def _diff_symbol(name: str, old: SymbolInfo, new: SymbolInfo) -> SymbolChange | None:
    """Compare two versions of the same symbol."""
    details: list[str] = []
    param_changes: list[ParameterChange] = []
    is_breaking = False
    migration_hints: list[str] = []

    # Kind changed (e.g., function -> class)
    if old.kind != new.kind:
        details.append(f"Kind changed: {old.kind} → {new.kind}")
        is_breaking = True
        migration_hints.append(f"'{name}' changed from {old.kind} to {new.kind}.")

    # Async changed
    if old.is_async != new.is_async:
        if new.is_async:
            details.append("Now async")
            is_breaking = True
            migration_hints.append(f"'{name}' is now async — callers must use 'await'.")
        else:
            details.append("No longer async")
            is_breaking = True

    # Return annotation changed
    if old.return_annotation != new.return_annotation:
        details.append(
            f"Return type: {old.return_annotation or '(none)'} → "
            f"{new.return_annotation or '(none)'}"
        )

    # Base classes changed (for classes)
    if old.bases != new.bases:
        removed_bases = set(old.bases) - set(new.bases)
        added_bases = set(new.bases) - set(old.bases)
        if removed_bases:
            details.append(f"Removed base(s): {', '.join(sorted(removed_bases))}")
            is_breaking = True
        if added_bases:
            details.append(f"Added base(s): {', '.join(sorted(added_bases))}")

    # Decorators changed
    if old.decorators != new.decorators:
        removed_decs = set(old.decorators) - set(new.decorators)
        added_decs = set(new.decorators) - set(old.decorators)
        if removed_decs:
            details.append(f"Removed decorator(s): {', '.join(sorted(removed_decs))}")
        if added_decs:
            details.append(f"Added decorator(s): {', '.join(sorted(added_decs))}")

    # Parameter changes (for functions / class constructors)
    if old.kind in ("function", "class") and new.kind in ("function", "class"):
        param_changes = _diff_parameters(old.parameters, new.parameters)
        for pc in param_changes:
            if pc.is_breaking:
                is_breaking = True
            details.append(_describe_param_change(pc))

    if not details:
        return None

    hint = " ".join(migration_hints) if migration_hints else None

    return SymbolChange(
        symbol=name,
        change_type="changed",
        details=details,
        parameter_changes=param_changes,
        is_breaking=is_breaking,
        migration_hint=hint,
    )


def _diff_parameters(
    old_params: list[ParameterInfo],
    new_params: list[ParameterInfo],
) -> list[ParameterChange]:
    """Diff two parameter lists and detect breaking changes."""
    changes: list[ParameterChange] = []

    old_by_name = {p.name: p for p in old_params}
    new_by_name = {p.name: p for p in new_params}

    old_names = [p.name for p in old_params]
    new_names = [p.name for p in new_params]

    old_set = set(old_names)
    new_set = set(new_names)

    # Removed parameters — breaking
    for name in old_names:
        if name not in new_set:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="removed",
                    old_value=name,
                    is_breaking=True,
                )
            )

    # Added parameters
    for name in new_names:
        if name not in old_set:
            new_p = new_by_name[name]
            # New parameter without a default is breaking (positional)
            has_default = new_p.default is not None
            is_keyword_only = new_p.kind == "KEYWORD_ONLY"
            breaking = not has_default and not is_keyword_only
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="added",
                    new_value=name,
                    is_breaking=breaking,
                )
            )

    # Changed parameters (type, default, kind)
    for name in old_names:
        if name not in new_set:
            continue
        old_p = old_by_name[name]
        new_p = new_by_name[name]

        if old_p.annotation != new_p.annotation:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="retyped",
                    old_value=old_p.annotation,
                    new_value=new_p.annotation,
                    is_breaking=False,  # Type changes are risky but not always breaking
                )
            )

        if old_p.default != new_p.default:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="default_changed",
                    old_value=old_p.default,
                    new_value=new_p.default,
                    is_breaking=False,
                )
            )

        if old_p.kind != new_p.kind:
            changes.append(
                ParameterChange(
                    parameter=name,
                    change_type="kind_changed",
                    old_value=old_p.kind,
                    new_value=new_p.kind,
                    is_breaking=True,
                )
            )

    # Check for positional reorderings (breaking for positional args)
    old_positional = [
        n for n in old_names if n in new_set and old_by_name[n].kind != "KEYWORD_ONLY"
    ]
    new_positional = [
        n for n in new_names if n in old_set and new_by_name[n].kind != "KEYWORD_ONLY"
    ]
    if old_positional != new_positional and old_positional and new_positional:
        changes.append(
            ParameterChange(
                parameter="(order)",
                change_type="reordered",
                old_value=", ".join(old_positional),
                new_value=", ".join(new_positional),
                is_breaking=True,
            )
        )

    return changes


def _describe_param_change(pc: ParameterChange) -> str:
    """Human-readable description of a parameter change."""
    prefix = "⚠ " if pc.is_breaking else ""
    match pc.change_type:
        case "added":
            return f"{prefix}New parameter: {pc.parameter}"
        case "removed":
            return f"{prefix}Removed parameter: {pc.parameter}"
        case "retyped":
            return f"{prefix}Parameter '{pc.parameter}' type: {pc.old_value} → {pc.new_value}"
        case "default_changed":
            return f"{prefix}Parameter '{pc.parameter}' default: {pc.old_value} → {pc.new_value}"
        case "kind_changed":
            return f"{prefix}Parameter '{pc.parameter}' kind: {pc.old_value} → {pc.new_value}"
        case "reordered":
            return f"{prefix}Parameters reordered: [{pc.old_value}] → [{pc.new_value}]"
        case _:
            return f"{prefix}Parameter '{pc.parameter}': {pc.change_type}"


def _flatten_cli(cmd: CliCommandInfo | None, prefix: str = "") -> dict[str, CliCommandInfo]:
    """Flatten a CLI tree into `{full_path: CliCommandInfo}`."""
    if cmd is None:
        return {}
    path = f"{prefix} {cmd.name}".strip() if prefix else cmd.name
    result = {path: cmd}
    for sub in cmd.subcommands:
        result.update(_flatten_cli(sub, path))
    return result


def _diff_cli_command(path: str, old: CliCommandInfo, new: CliCommandInfo) -> CliChange | None:
    """Compare two versions of the same CLI command."""
    details: list[str] = []
    is_breaking = False

    # Options diff
    old_opts = {o.name: o for o in old.options}
    new_opts = {o.name: o for o in new.options}

    for name in sorted(set(new_opts) - set(old_opts)):
        details.append(f"New option: {name}")
    for name in sorted(set(old_opts) - set(new_opts)):
        details.append(f"Removed option: {name}")
        is_breaking = True
    for name in sorted(set(old_opts) & set(new_opts)):
        o, n = old_opts[name], new_opts[name]
        if o.is_flag != n.is_flag:
            details.append(f"Option '{name}' flag changed: {o.is_flag} → {n.is_flag}")
            is_breaking = True
        if o.required != n.required and n.required:
            details.append(f"Option '{name}' is now required")
            is_breaking = True
        if o.default != n.default:
            details.append(f"Option '{name}' default: {o.default!r} → {n.default!r}")

    # Group ↔ non-group change
    if old.is_group != new.is_group:
        details.append(f"Group status changed: {old.is_group} → {new.is_group}")
        is_breaking = True

    if not details:
        return None
    return CliChange(
        command=path,
        change_type="changed",
        details=details,
        is_breaking=is_breaking,
    )


def _diff_cli(old: CliCommandInfo | None, new: CliCommandInfo | None) -> list[CliChange]:
    """Diff two CLI command trees."""
    old_cmds = _flatten_cli(old)
    new_cmds = _flatten_cli(new)
    changes: list[CliChange] = []

    old_paths = set(old_cmds)
    new_paths = set(new_cmds)

    for path in sorted(new_paths - old_paths):
        changes.append(
            CliChange(command=path, change_type="added", details=[f"New command: {path}"])
        )

    for path in sorted(old_paths - new_paths):
        changes.append(
            CliChange(
                command=path,
                change_type="removed",
                details=[f"Removed command: {path}"],
                is_breaking=True,
            )
        )

    for path in sorted(old_paths & new_paths):
        change = _diff_cli_command(path, old_cmds[path], new_cmds[path])
        if change is not None:
            changes.append(change)

    return changes


def api_diff(
    project_root: Path,
    old_version: str,
    new_version: str,
    package_name: str | None = None,
) -> ApiDiff | None:
    """
    High-level entry point: diff a package between two git tags.

    Parameters
    ----------
    project_root
        Root of the git repository.
    old_version
        Old git tag (e.g., `"v1.0.0"`).
    new_version
        New git tag (e.g., `"v2.0.0"`). Use `"HEAD"` for the working tree.
    package_name
        Python package name. Read from the project's metadata if omitted.

    Returns
    -------
    ApiDiff | None
        The diff, or `None` if snapshots could not be built.
    """
    from .snapshot import _detect_package_name, snapshot_at_tag, snapshot_from_griffe

    if package_name is None:
        package_name = _detect_package_name(project_root)
        if package_name is None:
            return None

    # Build snapshots
    if new_version.upper() == "HEAD":
        new_snap = snapshot_from_griffe(package_name, version="HEAD")
    else:
        new_snap = snapshot_at_tag(project_root, new_version, package_name)

    old_snap = snapshot_at_tag(project_root, old_version, package_name)

    if old_snap is None or new_snap is None:
        return None

    return diff_snapshots(old_snap, new_snap)
