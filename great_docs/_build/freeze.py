"""
Page freezing and freeze cache persistence

Quarto reuses a page's cached results only while its source is unchanged. Pages are frozen
from the same sources a build renders. Each build stores its cache in its Quarto project.
The persisted cache beside the configuration preserves those results for the next build.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .._content_naming import strip_numeric_prefix
from .._subprocess import TEXT_MODE_KWARGS
from .._utils import recognised_build_dirs, validate_tree_symlinks
from .steps import count_listed, run_steps

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .._build_log import BuildLog
    from .._layout import Layout
    from .steps import Step

__all__ = ["find_page", "merge", "prepare", "render_page", "save"]


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


def render_page(build_dir: Path, page: Path) -> subprocess.CompletedProcess[str]:
    """
    Render one Quarto page and execute its code, even if it is frozen

    Parameters
    ----------
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
    Replace the persisted freeze cache with merged caches from all builds

    The latest version and non-versioned builds store their cache in the default build
    directory. Historical versions use recognised build directories beside it. Merge
    historical caches first so the latest version wins when versions cache the same file.

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
    builds = (*recognised_build_dirs(layout), layout.build_dir)
    sources = [build / "_freeze" for build in builds if (build / "_freeze").is_dir()]
    if not sources:
        return None

    destination = layout.freeze_dir
    for cache in (destination, *sources):
        validate_tree_symlinks(cache)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for source in sources:
        _ = merge(source, destination)
    return sum(1 for path in destination.rglob("*") if path.is_file())
