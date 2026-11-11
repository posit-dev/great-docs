"""API snapshot acquisition and saved-snapshot loading"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from great_docs._api_evolution.model import ApiSnapshot, ParameterInfo, SymbolInfo
from great_docs._project import Project
from great_docs._project.layout import PACKAGE_DIRS, Layout, LayoutError
from great_docs._subprocess import TEXT_MODE_KWARGS
from great_docs.config import ConfigError

if TYPE_CHECKING:
    from griffe import Alias, Object


class BinaryOnlySnapshotError(RuntimeError):
    """
    A tagged module with compiled files but no source or stubs to snapshot
    """

    def __init__(self, module: str, tag: str) -> None:
        super().__init__(
            f"Cannot snapshot {module!r} at {tag!r}: the tag has compiled files but no "
            "Python source or `.pyi` stubs. For versioned docs, set "
            "`versions[].api_snapshot` to a prewritten snapshot file."
        )


def _annotation_str(annotation) -> str | None:
    """Extract a string representation from a griffe annotation."""
    if annotation is None:
        return None
    # griffe annotations can be Name, Expression, or str
    return str(annotation)


def _extract_parameters(obj) -> list[ParameterInfo]:
    """Extract parameter info from a griffe callable."""
    params: list[ParameterInfo] = []
    for param in obj.parameters:
        # Skip 'self' and 'cls'
        if param.name in ("self", "cls"):
            continue
        params.append(
            ParameterInfo(
                name=param.name,
                annotation=_annotation_str(param.annotation),
                default=str(param.default) if param.default is not None else None,
                kind=param.kind.name,
            )
        )
    return params


def _extract_bases(obj) -> list[str]:
    """Extract base class names from a griffe class."""
    return [str(base) for base in obj.bases]


def _extract_decorators(obj) -> list[str]:
    """Extract decorator expressions from a griffe function or class"""
    return [str(dec.value) for dec in obj.decorators]


def _symbol_info_for_dotted(pkg, dotted: str) -> SymbolInfo | None:
    """
    Look up API information for a documented symbol

    Parameters
    ----------
    pkg
        The loaded package.
    dotted
        The symbol's dotted name relative to the package.

    Returns
    -------
    :
        The symbol's API information, or `None` if a name component is missing
        or an alias target is missing or cyclic.
    """
    from griffe import AliasResolutionError, CyclicAliasError

    obj = pkg
    for part in dotted.split("."):
        try:
            members = obj.members
        except (AliasResolutionError, CyclicAliasError):
            return None
        if part not in members:
            return None
        obj = members[part]

    # An unresolved alias still reports kind `alias`; accessing its API details would raise.
    kind = obj.kind.value
    if kind == "alias":
        return None

    return SymbolInfo(
        name=dotted,
        kind=kind,
        parameters=_extract_parameters(obj) if kind in ("function", "class") else [],
        bases=_extract_bases(obj) if kind == "class" else [],
        decorators=_extract_decorators(obj) if kind in ("function", "class") else [],
        is_async=getattr(obj, "is_async", False),
        return_annotation=_annotation_str(
            getattr(obj, "annotation", None) or getattr(obj, "returns", None)
        ),
    )


def _exported_names(pkg: Object | Alias) -> list[str]:
    """
    List the names a package exports at its top level

    Use the package's `__all__` as expanded by griffe. If the package imports
    `__all__`, use the defining module's exports. Fall back to members without
    a leading underscore when no export names can be read.

    Parameters
    ----------
    pkg
        The loaded package.

    Returns
    -------
    :
        The export names, or public member names when no exports can be read.
    """
    from griffe import AliasResolutionError, CyclicAliasError

    exports = pkg.exports
    all_member = pkg.members.get("__all__")
    if exports is None and all_member is not None and all_member.is_alias:
        # An imported `__all__` leaves package exports unset; use its defining module.
        try:
            exports = all_member.final_target.module.exports
        except (AliasResolutionError, CyclicAliasError):
            exports = None

    # Unexpanded exports remain expressions; only strings can identify snapshot symbols.
    names = [name for name in exports or [] if isinstance(name, str)]
    return names or [name for name in pkg.members if not name.startswith("_")]


def snapshot_from_griffe(
    package_name: str,
    version: str,
    documented_names: list[str] | None = None,
    search_paths: list[str] | None = None,
) -> ApiSnapshot:
    """
    Build an API snapshot from documented names or top-level exports

    Skip names that are missing or whose aliases cannot be resolved.

    Parameters
    ----------
    package_name
        The Python package name (e.g., `"great_tables"`).
    version
        Version label for this snapshot.
    documented_names
        Package-relative dotted names to capture, including submodule and method names.
        When `None` or empty, capture the package's top-level public exports.
    search_paths
        Additional paths to search for the package source. For a historical version
        extracted to a temporary directory, include that directory here.

    Returns
    -------
    :
        The snapshot, keyed by the requested dotted names or by top-level export names.
    """
    import griffe

    normalized = package_name.replace("-", "_")

    loader_kwargs: dict = {}
    if search_paths:
        loader_kwargs["search_paths"] = search_paths
        # A same-named package in the working directory would override these source paths.
        loader_kwargs["try_relative_path"] = False
        loader_kwargs["allow_inspection"] = False

    pkg = griffe.load(normalized, **loader_kwargs)

    skip = {"__version__", "__author__", "__email__", "__all__"}
    names = documented_names or [name for name in _exported_names(pkg) if name not in skip]
    symbols: dict[str, SymbolInfo] = {}
    for name in names:
        info = _symbol_info_for_dotted(pkg, name)
        if info is not None:
            symbols[name] = info

    return ApiSnapshot(version=version, package_name=normalized, symbols=symbols)


def list_version_tags(project_root: Path) -> list[str]:
    """
    List git tags that look like version numbers, sorted oldest-first.

    Tags matching patterns like `v1.0.0`, `1.0.0`, `v0.12.3` are included. Non-version tags are
    excluded.
    """
    import re

    try:
        result = subprocess.run(
            ["git", "tag", "--sort=creatordate"],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        version_re = re.compile(r"^v?\d+\.\d+(\.\d+)?$")
        tags = []
        for line in result.stdout.strip().split("\n"):
            tag = line.strip()
            if tag and version_re.match(tag):
                tags.append(tag)
        return tags

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _get_tag_date(project_root: Path, tag: str) -> str | None:
    """Return the date (YYYY-MM-DD) of a git tag, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ai", tag],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Format is "2024-01-15 12:34:56 -0500" — take date part
            return result.stdout.strip().split(" ")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _extract_package_at_tag(
    project_root: Path,
    tag: str,
    package_name: str,
    destination: Path,
) -> Path | None:
    """
    Extract tagged source for an importable module

    Search the project root, then its `src`, `python` and `lib` directories as they were at
    the tag. Accept package directories, module files and stubs. Extract the first matching
    source, including its containing top-level package when the name is dotted.

    Parameters
    ----------
    project_root
        The project's root directory. Git paths are relative to this directory, which may
        be a subdirectory of the repository.
    tag
        The git tag, branch or commit.
    package_name
        The importable module name, which may be dotted, such as `firebird.base`.
    destination
        The directory in which to extract the package.

    Returns
    -------
    :
        The directory within `destination` to search for `package_name`, or `None` if the
        module is absent at the tag or extraction fails.
    """
    parts = package_name.replace("-", "_").split(".")
    source_dirs = [PurePosixPath(directory) for directory in ("", *PACKAGE_DIRS)]
    candidates: dict[str, tuple[PurePosixPath, PurePosixPath]] = {}
    for source_dir in source_dirs:
        module_path = source_dir.joinpath(*parts)
        for path in (module_path, module_path.with_suffix(".py"), module_path.with_suffix(".pyi")):
            archive_path = source_dir / parts[0] if path == module_path or len(parts) > 1 else path
            candidates[path.as_posix()] = (source_dir, archive_path)

    try:
        # git reads these paths relative to its working directory, the project root
        listing = subprocess.run(
            ["git", "ls-tree", "--name-only", tag, "--", *candidates],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
        if listing.returncode != 0:
            return None
        present = set(listing.stdout.splitlines())
        selected = next((candidates[path] for path in candidates if path in present), None)
        if selected is None:
            return None
        source_dir, archive_path = selected

        # Loading a dotted module requires its containing top-level package.
        archive = subprocess.run(
            ["git", "archive", tag, archive_path.as_posix()],
            cwd=project_root,
            capture_output=True,
            timeout=30,
        )
        if archive.returncode != 0:
            return None
        untar = subprocess.run(
            ["tar", "xf", "-"],
            cwd=destination,
            input=archive.stdout,
            capture_output=True,
            timeout=30,
        )
        if untar.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    return destination / source_dir


def _tag_has_binary_module(project_root: Path, tag: str, module: str) -> bool:
    """
    Check whether a Git tag contains compiled files for an importable module

    A module file may carry an interpreter and platform suffix before `.so` or `.pyd`.
    Package directories may contain compiled members under their module path.
    """
    try:
        prefix = subprocess.run(
            ["git", "rev-parse", "--show-prefix"],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", tag],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    if prefix.returncode != 0 or listing.returncode != 0:
        return False

    project_path = PurePosixPath(prefix.stdout.strip())
    parts = module.replace("-", "_").split(".")
    files = [PurePosixPath(path) for path in listing.stdout.splitlines()]
    for source_dir in ("", *PACKAGE_DIRS):
        module_path = project_path.joinpath(source_dir, *parts)
        for path in files:
            if path.suffix not in {".so", ".pyd"}:
                continue
            if path.is_relative_to(module_path) or (
                path.parent == module_path.parent and path.name.startswith(f"{module_path.name}.")
            ):
                return True
    return False


def snapshot_at_tag(
    project_root: Path,
    tag: str,
    package_name: str,
    documented_names: list[str] | None = None,
) -> ApiSnapshot | None:
    """
    Build an API snapshot from an importable module's tagged source

    Search the project root, then its `src`, `python` and `lib` directories at the tag.
    Extract the first matching package, module file or stub, including its containing
    top-level package when the name is dotted.

    Parameters
    ----------
    project_root
        The project's root directory. Git paths are relative to this directory, which may
        be a subdirectory of the repository.
    tag
        The git tag name, such as `"v1.0.0"`.
    package_name
        The importable module name, which may be dotted, such as `firebird.base`.
    documented_names
        Dotted names to capture, including submodule-qualified and method symbols. When `None`,
        the snapshot holds only the package's top-level public exports.

    Returns
    -------
    :
        The snapshot, or `None` if the module is absent at the tag or extraction fails.

    Raises
    ------
    BinaryOnlySnapshotError
        If the tag has compiled module files but no Python source or stubs to inspect.
    """
    with tempfile.TemporaryDirectory(prefix="gd_api_diff_", ignore_cleanup_errors=True) as tmp:
        source_dir = _extract_package_at_tag(project_root, tag, package_name, Path(tmp))
        if source_dir is None:
            if _tag_has_binary_module(project_root, tag, package_name):
                raise BinaryOnlySnapshotError(package_name, tag)
            return None

        module_path = source_dir.joinpath(*package_name.replace("-", "_").split("."))
        if module_path.is_dir() and not any(
            path.suffix in {".py", ".pyi"} for path in module_path.rglob("*")
        ):
            if _tag_has_binary_module(project_root, tag, package_name):
                raise BinaryOnlySnapshotError(package_name, tag)

        # Griffe does not load standalone stubs by import name. Give each stub without
        # Python source a temporary source twin so tagged APIs stay statically readable.
        for stub in source_dir.rglob("*.pyi"):
            source = stub.with_suffix(".py")
            if not source.exists():
                source.write_bytes(stub.read_bytes())

        snap = snapshot_from_griffe(
            package_name,
            version=tag,
            documented_names=documented_names,
            search_paths=[str(source_dir)],
        )

        # Attempt CLI introspection from the version-specific source
        from .._cliref import click as cli_click

        cli_module = cli_click.read_module_at_tag(project_root, tag, package_name)
        if cli_module:
            snap.cli_commands = cli_click.snapshot_from_source(source_dir, cli_module)

        return snap


def _detect_package_name(project_root: Path, config_path: Path | None = None) -> str | None:
    """
    Detect the project's importable module name

    Parameters
    ----------
    project_root
        The directory holding the packaging files and Great Docs configuration.
    config_path
        An explicitly selected Great Docs configuration file, if any.

    Returns
    -------
    :
        The configured or discovered importable module, or `None` when the project does not
        identify one.
    """
    try:
        layout = Layout.make(project_root, config_path)
        project = Project.make(layout.load_config(), layout)
    except (ConfigError, LayoutError):
        return None
    return project.importable_name


def load_snapshots_for_annotations(
    snapshot_dir: Path,
    current_version: str,
    previous_version: str | None,
) -> tuple[ApiSnapshot | None, ApiSnapshot | None]:
    """
    Load current and previous snapshots from a directory.

    Parameters
    ----------
    snapshot_dir
        Directory containing `<version>.json` snapshot files.
    current_version
        Version tag for the current snapshot.
    previous_version
        Version tag for the previous snapshot, or None.

    Returns
    -------
    tuple[ApiSnapshot | None, ApiSnapshot | None]
        `(current, previous)` snapshot pair.
    """
    current = None
    previous = None

    current_path = snapshot_dir / f"{current_version}.json"
    if current_path.exists():
        current = ApiSnapshot.load(current_path)

    if previous_version:
        prev_path = snapshot_dir / f"{previous_version}.json"
        if prev_path.exists():
            previous = ApiSnapshot.load(prev_path)

    return current, previous
