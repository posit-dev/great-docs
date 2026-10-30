"""
The Quarto command-line tool as great-docs runs it

Every command that runs Quarto first calls `ensure_installed`. A render runs in the Quarto
project's directory with the environment from `environment`, and reports the pages Quarto
starts, its warnings and how long each page took.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

from .._subprocess import TEXT_MODE_KWARGS
from .steps import BuildError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from ..config import Config

__all__ = [
    "MIN_VERSION",
    "Progress",
    "QuartoNotFoundError",
    "QuartoVersionError",
    "RenderResult",
    "ensure_installed",
    "environment",
    "installed_version",
    "is_transient_error",
    "page_timings",
    "parse_progress",
    "render",
]

# The bundled extensions set the stage at which their filters run, which
# Quarto's extension schema accepts from this release
MIN_VERSION = (1, 9, 18)

# Quarto can fail while copying output in large projects when one process renames
# a file as another removes it. A retry can succeed after the filesystem race ends.
_TRANSIENT_ERRORS = ("No such file or directory", "renameSync", "os error 2")

_PROGRESS = re.compile(r"\[\s*(\d+)/(\d+)\]\s+(.+)")
_ANSI = re.compile(r"\033\[[0-9;]*m")


class QuartoNotFoundError(BuildError):
    """A missing Quarto CLI"""


class QuartoVersionError(BuildError):
    """An installed Quarto CLI older than great-docs supports"""


def installed_version() -> tuple[int, ...] | None:
    """
    Read the version of the Quarto CLI on the `PATH`

    Returns
    -------
    :
        The version components, or `None` if Quarto fails to report a recognisable version.
    """
    try:
        proc = subprocess.run(
            ["quarto", "--version"],
            capture_output=True,
            timeout=30,
            check=True,
            **TEXT_MODE_KWARGS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.match(r"\s*(\d+(?:\.\d+)*)", proc.stdout)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def ensure_installed() -> None:
    """
    Check that a supported Quarto CLI is on the `PATH`

    A Quarto whose version cannot be read passes the check.

    Raises
    ------
    QuartoNotFoundError
        If Quarto is not on the `PATH`.
    QuartoVersionError
        If Quarto is older than `MIN_VERSION`.
    """
    if shutil.which("quarto") is None:
        raise QuartoNotFoundError(
            "Quarto was not found on your system. Quarto is a system-level "
            "dependency of great-docs and is not bundled with the Python package.\n\n"
            "See the troubleshooting guide:\n"
            "  https://posit-dev.github.io/great-docs/recipes/fix-common-build-errors.html\n\n"
            "Or fetch the binary programmatically by using your OS package (brew, yum, winget)."
        )
    version = installed_version()
    if version is not None and version < MIN_VERSION:
        found = ".".join(map(str, version))
        required = ".".join(map(str, MIN_VERSION))
        raise QuartoVersionError(
            f"great-docs requires Quarto {required} or later, but found Quarto {found}. "
            "Upgrade Quarto from https://quarto.org/docs/get-started/"
        )


def environment(config: Config) -> dict[str, str]:
    """
    Create the environment for Quarto and the Python it runs

    Use Python from a virtual environment in the project root (`.venv` or `venv`), falling
    back to the running interpreter. Prepend the project root and any existing `src/` and
    `python/` directories to `PYTHONPATH` so notebooks and pre-render scripts can import the
    package without installing it.

    Parameters
    ----------
    config
        The project's configuration.

    Returns
    -------
    :
        A copy of this process's environment with `QUARTO_PYTHON` and `PYTHONPATH` set, and
        `PYTHONUTF8` defaulting to `1` so Python reads and writes UTF-8 on Windows.
    """
    env = os.environ.copy()
    root = config.project_root
    venv_pythons = (
        root / ".venv" / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "bin" / "python",
        root / "venv" / "Scripts" / "python.exe",
    )
    env["QUARTO_PYTHON"] = next(
        (str(python) for python in venv_pythons if python.exists()), sys.executable
    )

    package_dirs = [str(root)]
    package_dirs += [str(root / name) for name in ("src", "python") if (root / name).is_dir()]
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([*package_dirs, existing] if existing else package_dirs)

    _ = env.setdefault("PYTHONUTF8", "1")
    return env


class Progress(NamedTuple):
    """A page that Quarto has started to render"""

    current: int
    """Position of the page in the render, from 1"""

    total: int
    """Number of pages in the render"""

    page: str
    """Path of the page's output, relative to the project"""


def parse_progress(line: str) -> Progress | None:
    """
    Read page progress from a line of Quarto's output

    Parameters
    ----------
    line
        A line of output, which may contain terminal colour codes.

    Returns
    -------
    :
        The page's position, total page count and path, or `None` if the line contains no
        progress report.
    """
    match = _PROGRESS.search(_ANSI.sub("", line))
    if match is None:
        return None
    return Progress(int(match.group(1)), int(match.group(2)), match.group(3).strip())


def page_timings(stamps: Sequence[tuple[str, float]], ended: float) -> list[dict[str, Any]]:
    """
    Compute how long each page took to render

    Measure each page from its start until the next page starts. Measure the last page
    until the render ends.

    Parameters
    ----------
    stamps
        Each page and the `time.monotonic()` reading when Quarto started it, in order.
    ended
        The `time.monotonic()` reading when the render ended.

    Returns
    -------
    :
        One `{"page": ..., "seconds": ...}` entry per page, in order, with seconds rounded to
        milliseconds.
    """
    ends = [stamp for _, stamp in stamps[1:]] + [ended]
    return [
        {"page": page, "seconds": round(end - stamp, 3)}
        for (page, stamp), end in zip(stamps, ends, strict=False)
    ]


def is_transient_error(stderr: str) -> bool:
    """
    Recognise a render failure that a second attempt is likely to fix

    Parameters
    ----------
    stderr
        Quarto's standard error from the failed render.

    Returns
    -------
    :
        Whether Quarto failed on a filesystem race while copying its output.
    """
    return any(pattern in stderr for pattern in _TRANSIENT_ERRORS)


@dataclass(frozen=True)
class RenderResult:
    """The outcome of one `quarto render`"""

    returncode: int
    """Quarto's exit status"""

    stderr: str
    """Everything Quarto wrote to standard error"""

    page_timings: list[dict[str, Any]]
    """Each rendered page and its duration in seconds, as `page_timings` computes them"""

    @property
    def failed_transiently(self) -> bool:
        """Whether the render failed in a way that a second attempt is likely to fix"""
        return self.returncode != 0 and is_transient_error(self.stderr)


def render(
    project: Path,
    env: Mapping[str, str] | None = None,
    *,
    on_page: Callable[[Progress], None] | None = None,
    on_warning: Callable[[str], None] | None = None,
) -> RenderResult:
    """
    Render a Quarto project once

    Report page starts and warnings through callbacks, and discard other output. Keep
    standard error in the result. Callbacks run on two threads, one per output stream.

    Parameters
    ----------
    project
        The directory holding the project's `_quarto.yml`.
    env
        The environment for Quarto. `None` passes on this process's environment.
    on_page
        Called as Quarto starts each page.
    on_warning
        Called with each `WARN` line, without colour codes.

    Returns
    -------
    :
        Quarto's exit status, standard error and page timings.

    Raises
    ------
    OSError
        If Quarto cannot be started.
    """
    process = subprocess.Popen(
        ["quarto", "render"],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=1,
        **TEXT_MODE_KWARGS,
    )
    stamps: list[tuple[str, float]] = []
    stderr: list[str] = []

    def handle(line: str) -> None:
        progress = parse_progress(line)
        if progress is not None:
            stamps.append((progress.page, time.monotonic()))
            if on_page is not None:
                on_page(progress)
            return
        plain = _ANSI.sub("", line).strip()
        if plain.startswith("WARN") and on_warning is not None:
            on_warning(plain)

    def read_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            stderr.append(line)
            handle(line)

    reader = threading.Thread(target=read_stderr, daemon=True)
    reader.start()
    assert process.stdout is not None
    for line in process.stdout:
        handle(line)
    _ = process.wait()
    reader.join(timeout=5)
    return RenderResult(process.returncode, "".join(stderr), page_timings(stamps, time.monotonic()))
