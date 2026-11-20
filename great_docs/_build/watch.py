"""
Live preview with rebuilds after documentation and package source edits

Edits to documentation sources, `great-docs.yml` or the documented package trigger
preparation in a staging directory while `quarto preview` serves the build directory.
Only changed files are copied into the previewed project, so Quarto re-renders the affected
pages. An API reference extension adds its directory and helper modules, and the files,
directories and globs it declares, to the watched inputs. The session keeps the same
directories and filter for every rebuild, so an input outside them is watched only after
the preview restarts.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fnmatch
import glob
import hashlib
import importlib
import shutil
import subprocess
import sys
import threading
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import watchfiles

from .._project.layout import Layout
from .steps import BuildError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

__all__ = [
    "Staging",
    "WatchInputs",
    "forget_package",
    "serve",
    "source_changes",
    "stage",
    "sync",
    "watched_dirs",
]

# Seconds allowed for `quarto preview` to exit before it is killed
_STOP_SECONDS = 5


@dataclasses.dataclass(frozen=True)
class WatchInputs:
    """
    The directories and change filter that one preview session watches

    The selection stays the same across successful and failed rebuilds.
    """

    directories: tuple[Path, ...]
    """Existing, non-nested directories that the file watcher observes"""
    accept: Callable[[watchfiles.Change, str], bool]
    """The change filter, which also excludes hidden files and generated output"""
    _patterns: tuple[Path, ...]

    @classmethod
    def make(
        cls, layout: Layout, package: Path | None, dependencies: tuple[Path, ...] = ()
    ) -> WatchInputs:
        """
        Select the inputs that a preview session watches

        Parameters
        ----------
        layout
            The project's directories.
        package
            The documented package's source directory, or `None` when no package was
            located.
        dependencies
            The extension's preview inputs as absolute paths: its directory, its helper
            modules and the files, directories or globs it declares.

        Returns
        -------
        :
            The directories and filter that cover the documentation sources, the package
            and the dependencies.
        """
        paths = _input_paths(dependencies)
        roots = (layout.source_dir,) if package is None else (layout.source_dir, package)
        trees = (*roots, *(path for path in paths if not glob.has_magic(str(path))))
        patterns = tuple(path for path in paths if glob.has_magic(str(path)))
        return cls(
            tuple(watched_dirs(layout, package, paths)),
            _source_filter(layout, trees, patterns),
            patterns,
        )

    def uncovered(self, paths: tuple[Path, ...]) -> tuple[Path, ...]:
        """
        Find the inputs that the session's change filter does not cover

        A glob selected when the session started keeps covering its new matches. A glob
        added later is covered only when the filter already accepts its directory prefix.

        Parameters
        ----------
        paths
            The preview inputs of a rebuild's extension.

        Returns
        -------
        :
            The uncovered inputs, resolved, in their given order and without repeats.
        """
        missing: list[Path] = []
        for path in _input_paths(paths):
            if glob.has_magic(str(path)):
                if path in self._patterns:
                    continue
                prefix = _pattern_root(path)
                if self.accept(watchfiles.Change.modified, str(prefix)):
                    continue
            elif self.accept(watchfiles.Change.modified, str(path)):
                continue
            missing.append(path)
        return tuple(missing)


def _input_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """
    Resolve input paths and drop repeats, keeping their order

    Parameters
    ----------
    paths
        Absolute input paths or globs.

    Returns
    -------
    :
        The resolved paths in first-seen order.
    """
    return tuple(dict.fromkeys(path.resolve() for path in paths))


def _pattern_root(path: Path) -> Path:
    """
    Find the part of a glob before its first wildcard component

    Parameters
    ----------
    path
        An absolute glob, or a path without wildcards.

    Returns
    -------
    :
        The leading components that contain no wildcard.
    """
    prefix = Path(path.anchor)
    for part in path.parts[1:] if path.anchor else path.parts:
        if glob.has_magic(part):
            break
        prefix /= part
    return prefix


def _watch_directory(path: Path) -> Path:
    """
    Find the nearest existing directory that observes an input, even one not yet created

    Parameters
    ----------
    path
        An absolute input path or glob.

    Returns
    -------
    :
        The input itself when it is a directory, otherwise its nearest existing ancestor.
        For a glob, the search starts at the part before its first wildcard.
    """
    directory = _pattern_root(path) if glob.has_magic(str(path)) else path
    while not directory.is_dir():
        directory = directory.parent
    return directory


def _matches_pattern(path: Path, pattern: Path) -> bool:
    """
    Check whether a path matches a glob or lies inside a directory that matches it

    Each `**` component matches zero or more path components. Every other component
    matches exactly one.

    Parameters
    ----------
    path
        The changed path.
    pattern
        An absolute glob.

    Returns
    -------
    :
        Whether the glob matches the path or one of its ancestors.
    """
    path_parts, pattern_parts = path.parts, pattern.parts

    @cache
    def matches(path_index: int, pattern_index: int) -> bool:
        """
        Check whether the remaining glob components match the remaining path components

        Parameters
        ----------
        path_index, pattern_index
            The positions of the first unmatched path and glob components.

        Returns
        -------
        :
            Whether the rest of the glob matches the rest of the path or a prefix of it.
        """
        if pattern_index == len(pattern_parts):
            return True
        if pattern_parts[pattern_index] == "**":
            return matches(path_index, pattern_index + 1) or (
                path_index < len(path_parts) and matches(path_index + 1, pattern_index)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], pattern_parts[pattern_index])
            and matches(path_index + 1, pattern_index + 1)
        )

    return matches(0, 0)


@dataclasses.dataclass(frozen=True)
class Staging(Layout):
    """
    A project layout with a separate build directory for rebuilds

    Content discovery excludes the generated directories of both layouts. Rebuilds cannot
    read generated files from the project being previewed.

    Attributes
    ----------
    served
        The layout whose build directory `quarto preview` serves.
    """

    served: Layout

    def is_reserved_directory(self, path: Path) -> bool:
        """
        Check whether content discovery should skip a directory

        Parameters
        ----------
        path
            A directory encountered while walking authored content.

        Returns
        -------
        :
            Whether either layout reserves the directory.
        """
        return super().is_reserved_directory(path) or self.served.is_reserved_directory(path)

    def generated_dirs(self) -> list[Path]:
        """
        List the directories that hold generated copies of authored files

        Returns
        -------
        :
            The generated directories of both layouts.
        """
        return [*super().generated_dirs(), *self.served.generated_dirs()]


def serve(
    layout: Layout,
    env: Mapping[str, str],
    rebuild: Callable[[Staging], Mapping[str, Any]],
    quarto_config: Mapping[str, Any],
    package: Path | None,
    *,
    inputs: WatchInputs | None = None,
) -> None:
    """
    Preview a prepared project and rebuild it after source edits

    A rebuild that fails with a `BuildError` or `ValueError` leaves the previewed project
    unchanged, and watching continues. Any other error stops the preview after closing the
    file watcher and stopping `quarto preview`. After each successful rebuild, compare the
    `project` settings with those from the last successful preparation. Print a notice if
    they differ: `quarto preview` may need a restart to apply them. Watching stops when
    `quarto preview` exits.

    Parameters
    ----------
    layout
        The project's directories. Its build directory holds the prepared project.
    env
        The environment for `quarto preview`.
    rebuild
        A function that prepares the project in the staging layout's build directory and
        returns its Quarto configuration. It raises `BuildError` after reporting a failed
        step, or `ValueError` for invalid configuration or output directories.
    quarto_config
        The initial prepared project's Quarto configuration.
    package
        The documented package's source directory, or `None` when no package was
        located. Edits to this directory also trigger rebuilds.
    inputs
        The inputs to watch for the whole session, or `None` to watch the documentation
        sources and the package. An input that a later rebuild's extension adds outside
        them is watched only after a restart.

    Raises
    ------
    KeyboardInterrupt
        If the user stops watching with Ctrl+C.
    """
    staging = stage(layout)
    published = _digests(layout.build_dir)
    stopped = threading.Event()
    preview = subprocess.Popen(["quarto", "preview", "--no-browser"], cwd=layout.build_dir, env=env)

    def wait_for_preview() -> None:
        """Wait for `quarto preview` to exit, then signal the watcher to stop"""
        _ = preview.wait()
        stopped.set()

    threading.Thread(target=wait_for_preview, daemon=True).start()
    try:
        with contextlib.closing(source_changes(layout, package, stopped, inputs=inputs)) as changes:
            for paths in changes:
                print(f"\n🔄 Rebuilding after changes to {_describe(paths, layout)}")
                try:
                    rebuilt = rebuild(staging)
                except BuildError:
                    print("The preview keeps the last successful build.")
                except ValueError as error:
                    print(f"Error: {error}\nThe preview keeps the last successful build.")
                else:
                    published = sync(staging.build_dir, layout.build_dir, published)
                    if rebuilt.get("project") != quarto_config.get("project"):
                        print(
                            "⚠️  Quarto may not apply the changed project settings until it "
                            "restarts: stop and rerun `great-docs build --watch`."
                        )
                    quarto_config = rebuilt
                print("👀 Watching for changes... (Ctrl+C to stop)")
    finally:
        _stop(preview)
        shutil.rmtree(staging.build_dir, ignore_errors=True)


def source_changes(
    layout: Layout,
    package: Path | None,
    stop: threading.Event,
    *,
    inputs: WatchInputs | None = None,
) -> Generator[set[Path], None, None]:
    """
    Wait for documentation and package edits and yield changed paths in batches

    Keep the iterator open while rebuilding, so the file watcher records edits made
    between batches. Close it when watching ends to release the watcher.

    Parameters
    ----------
    layout
        The project's directories. Edits anywhere in the source directory count, except in
        hidden directories and directories that hold generated output.
    package
        The documented package's source directory, watched with the same exclusions as
        the documentation sources, or `None` when no package was located.
    stop
        An event that ends the watch when set.
    inputs
        The inputs to watch, or `None` to watch the documentation sources and the
        package.

    Yields
    ------
    :
        The files changed, added or deleted since the previous batch.

    Raises
    ------
    KeyboardInterrupt
        If the user stops watching with Ctrl+C.
    """
    selected = inputs if inputs is not None else WatchInputs.make(layout, package)
    with contextlib.closing(
        watchfiles.watch(*selected.directories, watch_filter=selected.accept, stop_event=stop)
    ) as changes:
        for batch in changes:
            yield {Path(path) for _, path in batch}


def watched_dirs(
    layout: Layout, package: Path | None, dependencies: tuple[Path, ...] = ()
) -> list[Path]:
    """
    List watch directories without nested or duplicate entries

    Parameters
    ----------
    layout
        The project's directories.
    package
        The documented package's source directory, or `None` when no package was
        located.
    dependencies
        The extension's preview inputs as absolute paths. A missing input or a glob is
        watched through its nearest existing ancestor.

    Returns
    -------
    :
        The documentation source directory, the package directory and a directory for
        each dependency, without nested or duplicate entries.
    """
    roots = [layout.source_dir]
    if package is not None:
        roots.append(package)
    roots.extend(_watch_directory(path) for path in _input_paths(dependencies))
    unique = list(dict.fromkeys(roots))
    return [
        root
        for root in unique
        if not any(root != other and root.is_relative_to(other) for other in unique)
    ]


def _source_filter(
    layout: Layout, trees: tuple[Path, ...], patterns: tuple[Path, ...]
) -> Callable[[watchfiles.Change, str], bool]:
    """
    Create a filter that accepts changes to the selected inputs

    Parameters
    ----------
    layout
        The project's directories, whose generated directories are excluded.
    trees
        Absolute files and directory trees to observe. An exact file does not
        include its siblings.
    patterns
        Absolute glob declarations, including those with no current match.

    Returns
    -------
    :
        A filter that accepts a change and its path, excluding editor and Python
        byproducts, hidden files and directories, and generated output. Hidden path
        components are checked below the matching directory tree, the directory of
        a matching file, or the matching glob's prefix.
    """
    default = watchfiles.DefaultFilter(ignore_paths=layout.generated_dirs())
    selected = tuple((tree, tree if tree.is_dir() else tree.parent) for tree in trees)

    def accept(change: watchfiles.Change, path: str) -> bool:
        """
        Check whether a change concerns a selected input

        Parameters
        ----------
        change
            The kind of change.
        path
            The changed path.

        Returns
        -------
        :
            Whether to rebuild for the change.
        """
        if not default(change, path):
            return False
        file = Path(path)
        root = next((root for tree, root in selected if file.is_relative_to(tree)), None)
        if root is None:
            pattern = next(
                (pattern for pattern in patterns if _matches_pattern(file, pattern)), None
            )
            if pattern is None:
                return False
            root = _pattern_root(pattern)
        relative = file.relative_to(root)
        return not any(part.startswith(".") for part in relative.parts)

    return accept


def sync(staged: Path, served: Path, published: Mapping[str, bytes]) -> dict[str, bytes]:
    """
    Copy a newly prepared project's changes into the previewed project

    Replace changed files and remove files no longer generated by preparation. Leave
    Quarto's output, such as the rendered site, untouched.

    Call only after a successful preparation, so a failed rebuild never replaces the last
    successful sources.

    Parameters
    ----------
    staged
        The newly prepared project.
    served
        The project that `quarto preview` serves.
    published
        The previous preparation's file digests, keyed by path relative to the project.

    Returns
    -------
    :
        The digests of the newly prepared project's files.
    """
    current = _digests(staged)
    changed = [path for path, digest in current.items() if published.get(path) != digest]
    removed = [path for path in published if path not in current]
    for path in changed:
        target = served / path
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(staged / path, target)
    for path in removed:
        (served / path).unlink(missing_ok=True)
    print(f"Updated {len(changed)} and removed {len(removed)} file(s) in the preview.")
    return current


def _digests(project: Path) -> dict[str, bytes]:
    """
    Compute SHA-256 digests for every file in a prepared project

    Parameters
    ----------
    project
        The project directory.

    Returns
    -------
    :
        The SHA-256 digest of each file, by POSIX path relative to the project.
    """
    return {
        path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).digest()
        for path in project.rglob("*")
        if path.is_file()
    }


def forget_package(name: str) -> None:
    """
    Clear cached modules so the next package import reloads them

    Watch-mode rebuilds share a process, so dynamic introspection would otherwise
    reuse imported modules. Remove the package and its submodules from `sys.modules`
    while keeping modules from other packages loaded. Invalidate the import system's
    directory caches so the next import can find newly added modules.

    Python can reuse stale bytecode when an edit preserves the source file's size
    and whole-second modification time. Delete each module's cached bytecode where
    possible so the next import reads the edited source.

    Parameters
    ----------
    name
        The package's importable name, such as `yaml12` or `firebird.base`.
    """
    for module in [key for key in sys.modules if key == name or key.startswith(f"{name}.")]:
        spec = getattr(sys.modules.pop(module), "__spec__", None)
        if spec is not None and spec.has_location and spec.cached:
            with contextlib.suppress(OSError):
                Path(spec.cached).unlink()
    importlib.invalidate_caches()


def stage(served: Layout) -> Staging:
    """
    Create a layout for rebuilds in the previewed project's cache directory

    Parameters
    ----------
    served
        The layout whose build directory `quarto preview` serves.

    Returns
    -------
    :
        The staging layout, whose build directory is `watch/` in the cache directory.
    """
    paths = {field.name: getattr(served, field.name) for field in dataclasses.fields(Layout)}
    paths["build_dir"] = served.cache_dir / "watch"
    return Staging(**paths, served=served)


def _describe(paths: set[Path], layout: Layout) -> str:
    """
    Name a batch of changed files for the build log

    Parameters
    ----------
    paths
        The changed files.
    layout
        The project's directories.

    Returns
    -------
    :
        Up to three paths, relative to the package root where possible, and a count of
        any remaining paths.
    """
    names = sorted(
        path.relative_to(layout.package_root).as_posix()
        if path.is_relative_to(layout.package_root)
        else str(path)
        for path in paths
    )
    shown = ", ".join(names[:3])
    return shown if len(names) <= 3 else f"{shown} and {len(names) - 3} more"


def _stop(preview: subprocess.Popen[bytes]) -> None:
    """
    Stop `quarto preview` if it is still running

    Parameters
    ----------
    preview
        The `quarto preview` process.
    """
    if preview.poll() is not None:
        return
    preview.terminate()
    try:
        _ = preview.wait(timeout=_STOP_SECONDS)
    except subprocess.TimeoutExpired:
        preview.kill()
        _ = preview.wait()
