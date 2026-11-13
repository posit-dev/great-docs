"""
Live preview with rebuilds after documentation and package source edits

Edits to documentation sources, `great-docs.yml` or the documented package trigger
preparation in a staging directory while `quarto preview` serves the build directory.
Only changed files are copied into the previewed project, so Quarto re-renders the affected
pages.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import watchfiles

from .._project.layout import Layout
from . import quarto
from .steps import BuildError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

__all__ = [
    "Staging",
    "forget_package",
    "serve",
    "source_changes",
    "source_filter",
    "stage",
    "sync",
    "watched_dirs",
]

# Seconds allowed for `quarto preview` to exit before it is killed
_STOP_SECONDS = 5


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
) -> None:
    """
    Preview a prepared project and rebuild it after source edits

    The preview keeps running across rebuilds, including after edits to `great-docs.yml`.
    A failed rebuild leaves the previewed project unchanged. After each successful rebuild,
    compare the `project` settings with those from the last successful preparation. Print
    a notice if they differ: `quarto preview` may need a restart to apply them. Watching
    stops when `quarto preview` exits.

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

    Raises
    ------
    KeyboardInterrupt
        If the user stops watching with Ctrl+C.
    """
    staging = stage(layout)
    published = _digests(layout.build_dir)
    stopped = threading.Event()
    preview = subprocess.Popen(
        [quarto.executable(), "preview", "--no-browser"], cwd=layout.build_dir, env=env
    )

    def wait_for_preview() -> None:
        _ = preview.wait()
        stopped.set()

    threading.Thread(target=wait_for_preview, daemon=True).start()
    try:
        for paths in source_changes(layout, package, stopped):
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
    layout: Layout, package: Path | None, stop: threading.Event
) -> Iterator[set[Path]]:
    """
    Wait for documentation and package edits and yield changed paths in batches

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

    Yields
    ------
    :
        The files changed, added or deleted since the previous batch.

    Raises
    ------
    KeyboardInterrupt
        If the user stops watching with Ctrl+C.
    """
    accept = source_filter(layout, package)
    directories = watched_dirs(layout, package)
    for changes in watchfiles.watch(*directories, watch_filter=accept, stop_event=stop):
        yield {Path(path) for _, path in changes}


def watched_dirs(layout: Layout, package: Path | None) -> list[Path]:
    """
    List watch directories without nested or duplicate entries

    Parameters
    ----------
    layout
        The project's directories.
    package
        The documented package's source directory, or `None` when no package was
        located.

    Returns
    -------
    :
        The documentation source directory and, if available, the package directory.
        If one contains the other, only the containing directory is returned.
    """
    if package is None or package.is_relative_to(layout.source_dir):
        return [layout.source_dir]
    if layout.source_dir.is_relative_to(package):
        return [package]
    return [layout.source_dir, package]


def source_filter(layout: Layout, package: Path | None) -> Callable[[watchfiles.Change, str], bool]:
    """
    Create a filter for changes to the documentation sources and the package

    Parameters
    ----------
    layout
        The project's directories.
    package
        The documented package's source directory, or `None` when no package was
        located.

    Returns
    -------
    :
        A filter that accepts a change and its path, excluding editor and Python
        byproducts, hidden files and directories, and generated output. Hidden path
        components are checked below the documentation source directory, or below the
        package directory for paths outside the documentation source directory.
    """
    default = watchfiles.DefaultFilter(ignore_paths=layout.generated_dirs())

    def accept(change: watchfiles.Change, path: str) -> bool:
        if not default(change, path):
            return False
        file = Path(path)
        root = layout.source_dir
        if package is not None and not file.is_relative_to(root):
            root = package
        relative = file.relative_to(root)
        return not any(part.startswith(".") for part in relative.parts)

    return accept


def sync(staged: Path, served: Path, published: Mapping[str, bytes]) -> dict[str, bytes]:
    """
    Copy a newly prepared project's changes into the previewed project

    Replace changed files and remove files no longer generated by preparation. Leave
    Quarto's output, such as the rendered site, untouched.

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
