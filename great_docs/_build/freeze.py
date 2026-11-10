"""
Page freezing and freeze cache persistence

Quarto reuses a page's cached results only while its source is unchanged. Pages are frozen
from the same sources a build renders. Each build stores its cache in its Quarto project.
The persisted cache beside the configuration preserves results for later builds. It stores
the latest version's results at its root and historical results in a subdirectory per version.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .._content.naming import strip_numeric_prefix
from .._subprocess import TEXT_MODE_KWARGS
from .._utils import recognised_build_dirs, validate_tree_symlinks
from . import quarto
from .steps import count_listed, run_steps

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .._project.layout import Layout
    from ..config import Config
    from .log import BuildLog
    from .steps import Step

__all__ = ["find_page", "merge", "prepare", "render_page", "save"]

# Keep this directory name in sync with the restore script copied into Quarto projects.
_VERSIONS_DIR = "_versions"


def prepare(steps: Iterable[Step], log: BuildLog, build_dir: Path) -> None:
    """
    Prepare the Quarto project with the build's steps before rendering

    Run preparation steps in build order, excluding steps that publish remote content.
    Number listed steps consecutively and count only the listed steps that run.

    Parameters
    ----------
    steps
        The build's preparation steps.
    log
        The build log that the steps write to.
    build_dir
        The working directory for steps that run the project's code.

    Raises
    ------
    BuildError
        If a step reports a failure. The log already contains the report.
    """
    local = [step for step in steps if not step.remote_content]
    log.total_steps = count_listed(local)
    run_steps(local, log, build_dir)


def find_page(build_dir: Path, page: str) -> Path | None:
    """
    Find the build directory's copy of an authored page

    The build may publish a page under another name: underscores become hyphens and a
    numeric ordering prefix is dropped (`24-freeze_demo.qmd` becomes `freeze-demo.qmd`). Try
    the authored file name first, then each published form.

    Parameters
    ----------
    build_dir
        The Quarto project's directory.
    page
        The page's path as the user gave it.

    Returns
    -------
    :
        The first file in the build directory with a matching name, or `None` if none matches.
    """
    name = Path(page).name
    hyphenated = name.replace("_", "-")
    names = (name, hyphenated, strip_numeric_prefix(name), strip_numeric_prefix(hyphenated))
    for candidate in dict.fromkeys(names):
        found = next(build_dir.rglob(candidate), None)
        if found is not None:
            return found
    return None


def render_page(config: Config, build_dir: Path, page: Path) -> subprocess.CompletedProcess[str]:
    """
    Render one Quarto page and execute its code, even if it is frozen

    Use the build's Quarto environment so the page runs with the same Python and can import
    the project's package without installing it.

    Parameters
    ----------
    config
        The project's configuration.
    build_dir
        The Quarto project's directory.
    page
        The page's source in the build directory.

    Returns
    -------
    :
        Quarto's exit status and captured output.
    """
    return subprocess.run(
        ["quarto", "render", str(page.relative_to(build_dir))],
        cwd=build_dir,
        env=quarto.environment(config),
        capture_output=True,
        check=False,
        **TEXT_MODE_KWARGS,
    )


def merge(source: Path, destination: Path) -> int:
    """
    Merge freeze cache files while preserving destination files absent from the source

    Quarto stores several pages' results in each section directory. Copy files individually
    to preserve other pages in the destination. Ensure each non-empty copied JavaScript file
    ends with a newline.

    Parameters
    ----------
    source
        The cache to copy.
    destination
        The cache to update, created if missing.

    Returns
    -------
    :
        The number of files copied.
    """
    copied = 0
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        target = destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(item, target)
        if target.suffix == ".js":
            data = target.read_bytes()
            if data and not data.endswith(b"\n"):
                _ = target.write_bytes(data + b"\n")
        copied += 1
    return copied


def save(layout: Layout) -> int | None:
    """
    Replace the persisted freeze cache with separate caches for each build

    Store the latest version's cache, or a non-versioned build's cache, at the root of
    the persisted cache. Store each historical version's cache under
    `_versions/<build directory name>/` so versions can cache different results for the
    same page.

    Parameters
    ----------
    layout
        The project's layout, which locates the build directories and the persisted cache.

    Returns
    -------
    :
        The number of files in the persisted cache, or `None` when no build has a cache.

    Raises
    ------
    ValueError
        If a cache contains a symlink.
    """
    persisted = layout.freeze_dir
    destinations = {layout.build_dir: persisted} | {
        build: persisted / _VERSIONS_DIR / build.name for build in recognised_build_dirs(layout)
    }
    caches = {
        build / "_freeze": destination
        for build, destination in destinations.items()
        if (build / "_freeze").is_dir()
    }
    if not caches:
        return None

    for cache in (persisted, *caches):
        validate_tree_symlinks(cache)
    if persisted.exists():
        shutil.rmtree(persisted)
    persisted.mkdir(parents=True)
    for source, destination in caches.items():
        _ = merge(source, destination)
    return sum(1 for path in persisted.rglob("*") if path.is_file())
