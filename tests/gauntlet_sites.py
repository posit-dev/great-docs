"""
Build selected Great Docs Gauntlet sites on demand

Rendered-output tests read sites under `test-packages/_rendered/`, but a fresh
checkout contains no rendered sites. This module builds the citation fixtures
required by a default test run without running a complete `make hub-build`.

The builder runs only the project-preparation, API-reference, and Quarto render
stages. It omits the discovery and refresh stages used by a complete Gauntlet
build, so its output can differ from `make hub-build` output.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Callable, Iterable

from great_docs._layout import Layout

# These packages cover both citation backlink forms. The first has three
# definitions and one reference, which produces a caret backlink. The second
# has one definition and two references, which produces lettered backlinks.
CITATION_SITES: tuple[str, ...] = (
    "gdtest_docstring_references",
    "gdtest_long_docs",
)

_TEST_PACKAGES_DIR = Path(__file__).resolve().parent.parent / "test-packages"
RENDERED_DIR = _TEST_PACKAGES_DIR / "_rendered"

# Treat these exceptions as an unavailable rendered fixture. The dependent
# tests already skip when a site is absent. Fatal API-reference configuration
# errors raise `SystemExit`; any unlisted exception indicates a builder defect
# and propagates.
BUILD_FAILURES: tuple[type[BaseException], ...] = (
    OSError,
    subprocess.SubprocessError,
    ImportError,
    SystemExit,
    ValueError,
    KeyError,
)

# Limit each Quarto render to ten minutes.
_RENDER_TIMEOUT_SECONDS = 600.0

# Preserve a live process's lock beyond the maximum Quarto render time.
_LIVE_HOLDER_STALE_SECONDS = 900.0


def site_dir(rendered_dir: Path, name: str) -> Path:
    """
    Return a Gauntlet package's rendered site directory

    Parameters
    ----------
    rendered_dir
        The `_rendered` root that holds one subdirectory per package.
    name
        The gauntlet package name.

    Returns
    -------
    Path
        The package's `_site` directory, resolved from whichever layout the
        package's `great-docs.yml` actually uses. An unbuilt package uses the
        root-layout default inside `rendered_dir`.
    """
    package_dir = rendered_dir / name
    if not package_dir.is_dir():
        # Do not let `Layout.make` search above the fixture root for an absent
        # package; use the root-layout default inside the fixture tree.
        return package_dir / "great-docs" / "_site"
    return Layout.make(package_dir).site_dir


def sentinel_path(rendered_dir: Path, name: str) -> Path:
    """
    Return the sentinel path that guards a package build

    Parameters
    ----------
    rendered_dir
        The `_rendered` root to build into.
    name
        The gauntlet package name.

    Returns
    -------
        The path beside the package directory. Replacing the package directory
        therefore preserves the sentinel.
    """
    return rendered_dir / f".{name}.building"


def ensure_sites(
    rendered_dir: Path,
    names: Iterable[str],
    builder: Callable[[Path, str], Path] | None = None,
    timeout: float = 300.0,
) -> list[str]:
    """
    Build each missing Gauntlet site

    Preserve existing sites so a complete local Gauntlet build takes
    precedence over these on-demand fixtures.

    Parameters
    ----------
    rendered_dir
        The `_rendered` root to build into.
    names
        Names of the Gauntlet packages to prepare.
    builder
        Callable that builds one package and returns its site directory.
        Defaults to `build_site`.
    timeout
        Maximum seconds to wait while another process builds the package.

    Returns
    -------
        Names built by this call, in input order.
    """
    if builder is None:
        builder = build_site

    built: list[str] = []
    for name in names:
        if site_dir(rendered_dir, name).is_dir():
            continue

        handle = _claim_sentinel(rendered_dir, name, timeout)
        if handle is None:
            continue
        sentinel = sentinel_path(rendered_dir, name)

        try:
            try:
                os.write(handle, str(os.getpid()).encode())
            finally:
                os.close(handle)
        except OSError as exc:
            warnings.warn(
                f"could not claim the build lock for Gauntlet site {name}: {exc}",
                stacklevel=2,
            )
            sentinel.unlink(missing_ok=True)
            continue

        try:
            builder(rendered_dir, name)
        except BUILD_FAILURES as exc:
            warnings.warn(f"could not build Gauntlet site {name}: {exc}", stacklevel=2)
            continue
        finally:
            # Release the lock after success, a handled failure, or a
            # propagating exception.
            sentinel.unlink(missing_ok=True)
        built.append(name)
    return built


def _claim_sentinel(rendered_dir: Path, name: str, timeout: float) -> int | None:
    """
    Claim the sentinel that guards a package build

    Parameters
    ----------
    rendered_dir
        The `_rendered` root being built into.
    name
        The Gauntlet package name.
    timeout
        Maximum seconds to wait while another process builds the package.

    Returns
    -------
        An open file descriptor for a claimed sentinel, or `None` when another
        process owns the build.
    """
    sentinel = sentinel_path(rendered_dir, name)
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    try:
        return os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        pass

    # A process holding a stale sentinel may have exited or stalled.
    is_stale, file_identity = _sentinel_is_stale(rendered_dir, name)
    if is_stale:
        # Remove only the file inspected by the staleness check. Another
        # process may have replaced it before this second `stat` call.
        try:
            current_stat = sentinel.stat()
            current_identity = (current_stat.st_dev, current_stat.st_ino)
        except FileNotFoundError:
            _wait_for_site(rendered_dir, name, timeout)
            return None

        if file_identity is not None and current_identity == file_identity:
            try:
                sentinel.unlink()
            except FileNotFoundError:
                _wait_for_site(rendered_dir, name, timeout)
                return None
        else:
            _wait_for_site(rendered_dir, name, timeout)
            return None

        # Limit contention after removing a stale sentinel to one retry.
        try:
            return os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            _wait_for_site(rendered_dir, name, timeout)
            return None
    elif file_identity is None:
        # The owner released the sentinel before the staleness check. Retry
        # once because no process may still be building the site.
        try:
            return os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            _wait_for_site(rendered_dir, name, timeout)
            return None
    else:
        _wait_for_site(rendered_dir, name, timeout)
        return None


def _sentinel_is_stale(rendered_dir: Path, name: str) -> tuple[bool, tuple[int, int] | None]:
    """
    Determine whether a build sentinel is stale

    Parameters
    ----------
    rendered_dir
        The `_rendered` root being built into.
    name
        The Gauntlet package name.

    Returns
    -------
        Whether the sentinel is stale and, when inspected, its device and inode.
        A sentinel is stale when its process has exited, its contents are not a
        PID, or its modification time exceeds the live-process limit. A missing
        sentinel returns `(False, None)`. The file identity reduces concurrent
        builds by preventing removal of a replacement sentinel; it does not
        guarantee exclusive execution.
    """
    sentinel = sentinel_path(rendered_dir, name)
    try:
        content = sentinel.read_text()
        stat_result = sentinel.stat()
    except FileNotFoundError:
        return (False, None)

    try:
        pid = int(content.strip())
    except ValueError:
        return (True, (stat_result.st_dev, stat_result.st_ino))

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return (True, (stat_result.st_dev, stat_result.st_ino))
    except OSError:
        # A signalling failure cannot prove that the process has exited. Use
        # the modification-time limit as the fallback.
        pass

    # The wait timeout limits callers, while this longer threshold limits how
    # long a live process may retain a stalled build.
    mtime = stat_result.st_mtime
    now = time.time()
    age = now - mtime
    is_stale = age > _LIVE_HOLDER_STALE_SECONDS
    return (is_stale, (stat_result.st_dev, stat_result.st_ino))


def _wait_for_site(rendered_dir: Path, name: str, timeout: float) -> None:
    """
    Wait for another process to finish a package build

    Parameters
    ----------
    rendered_dir
        The `_rendered` root being built into.
    name
        The Gauntlet package name.
    timeout
        Maximum seconds to wait.

    A timeout warns and leaves the site unavailable.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if site_dir(rendered_dir, name).is_dir():
            return
        if not sentinel_path(rendered_dir, name).exists():
            return
        time.sleep(0.05)
    warnings.warn(
        f"timed out waiting for another process to build Gauntlet site {name}",
        stacklevel=3,
    )


def quarto_available() -> bool:
    """
    Return whether the Quarto CLI is available on `PATH`

    Returns
    -------
        Whether the `quarto` executable is available.
    """
    return shutil.which("quarto") is not None


def build_site(rendered_dir: Path, name: str) -> Path:
    """
    Build and render one Gauntlet package

    Generate the package and prepare its documentation in a private staging
    directory, render the site with Quarto, then publish the completed package
    with one move. A concurrent process can duplicate the work because the
    sentinel is advisory, but staging prevents either process from exposing
    incomplete output. Publishing briefly removes an existing destination
    before replacing it.

    Parameters
    ----------
    rendered_dir
        The `_rendered` root to build into.
    name
        The Gauntlet package name.

    Returns
    -------
    The rendered `_site` directory.
    """
    if str(_TEST_PACKAGES_DIR) not in sys.path:
        sys.path.insert(0, str(_TEST_PACKAGES_DIR))

    from synthetic.catalog import get_spec
    from synthetic.generator import generate_package

    from great_docs import GreatDocs
    from great_docs._apiref.api_reference import APIReference

    rendered_dir.mkdir(parents=True, exist_ok=True)
    staging = rendered_dir / f".building-{name}-{os.getpid()}"
    try:
        pkg_dir = generate_package(get_spec(name), staging)
        _add_to_sys_path(pkg_dir)

        docs = GreatDocs(str(pkg_dir))
        with contextlib.redirect_stdout(io.StringIO()):
            docs._prepare_build_directory()

        # API-reference paths resolve from the working directory. Run this
        # stage from the generated documentation project.
        original_dir = Path.cwd()
        try:
            os.chdir(docs.build_dir)
            with contextlib.redirect_stdout(io.StringIO()):
                APIReference(str(docs.build_dir / "_quarto.yml")).build()
        finally:
            os.chdir(original_dir)

        result = subprocess.run(
            ["quarto", "render"],
            cwd=docs.build_dir,
            env=docs._get_quarto_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=_RENDER_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            diagnostics = result.stderr or result.stdout
            tail = "\n".join(diagnostics.splitlines()[-40:])
            raise subprocess.SubprocessError(
                f"Quarto could not render {name} (exit code {result.returncode}):\n{tail}"
            )

        # The docs layout renders Quarto's default `_site` inside the build
        # directory, separate from the public site. Mirror `GreatDocs.build()`
        # because this builder runs the render stages directly.
        if docs.layout.site_dir != docs.build_dir / "_site":
            from great_docs._versioned_build import assemble_site

            assemble_site(docs.build_dir, [], "", docs.layout.site_dir, layout=docs.layout)

        published = rendered_dir / name
        _clear_package_dir(rendered_dir, name)
        os.replace(pkg_dir, published)
        _rehome_sys_path(pkg_dir, published)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        # A successful publish redirects imports to the final package. Remove
        # staging paths after an earlier failure because the directory is gone.
        staging_str = str(staging)
        sys.path[:] = [
            entry
            for entry in sys.path
            if entry != staging_str and not entry.startswith(staging_str + os.sep)
        ]

    return site_dir(rendered_dir, name)


def _clear_package_dir(rendered_dir: Path, name: str) -> None:
    """
    Remove a package directory before publishing its replacement

    A concurrent process may publish a complete site while this process builds
    the same fixture. Either result is equivalent, so the later publish may
    replace the earlier one. Validate the destination before removal to keep
    it within the rendered root and restrict it to generated Gauntlet packages.

    Parameters
    ----------
    rendered_dir
        The `_rendered` root to build into.
    name
        The Gauntlet package name.

    """
    stale = rendered_dir / name
    if not stale.exists():
        return
    if stale.parent != rendered_dir:
        raise ValueError(f"{stale} cannot be removed because it is outside {rendered_dir}")
    if not name.startswith("gdtest_"):
        raise ValueError(f"{name} cannot be replaced because it is not a Gauntlet package")
    shutil.rmtree(stale)


def _add_to_sys_path(pkg_dir: Path) -> None:
    """
    Add a generated package to `sys.path` for Griffe imports

    Add conventional source subdirectories to support non-flat package layouts.

    Parameters
    ----------
    pkg_dir
        The generated package directory.

    """
    if str(pkg_dir) not in sys.path:
        sys.path.insert(0, str(pkg_dir))
    for subdir_name in ("src", "python", "lib"):
        sub = pkg_dir / subdir_name
        if sub.is_dir() and str(sub) not in sys.path:
            sys.path.insert(0, str(sub))


def _rehome_sys_path(pkg_dir: Path, published: Path) -> None:
    """
    Redirect staging `sys.path` entries to the published package

    Publishing moves the package out of staging. Replace each absolute staging
    path so later imports resolve against the published package.

    Parameters
    ----------
    pkg_dir
        The staging package directory that `_add_to_sys_path` recorded.
    published
        The same package directory after the publish move.

    """
    pkg_dir_str = str(pkg_dir)
    published_str = str(published)
    for index, entry in enumerate(sys.path):
        if entry == pkg_dir_str:
            sys.path[index] = published_str
        elif entry.startswith(pkg_dir_str + os.sep):
            sys.path[index] = published_str + entry[len(pkg_dir_str) :]
