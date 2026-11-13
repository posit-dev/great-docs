"""
The Quarto command-line tool as great-docs runs it

Every command that runs Quarto first calls `ensure_installed`. A render runs in the Quarto
project's directory with the environment from `environment`, and reports the pages Quarto
starts, its warnings and how long each page took.

Setting `GREAT_DOCS_QUARTO` to `q2`, or to the path of a `q2` binary, renders and previews
with Quarto 2 instead (experimental). Quarto 2 reports no per-page progress, so a render
reports its pages when it ends.
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
    "EXECUTABLE_ENV",
    "MIN_VERSION",
    "Progress",
    "QuartoNotFoundError",
    "QuartoVersionError",
    "RenderResult",
    "ensure_installed",
    "environment",
    "executable",
    "installed_version",
    "is_q2",
    "is_transient_error",
    "page_timings",
    "parse_progress",
    "render",
]

EXECUTABLE_ENV = "GREAT_DOCS_QUARTO"
"""The environment variable that names the Quarto command, `quarto` when unset"""

# The bundled extensions set the stage at which their filters run, which
# Quarto's extension schema accepts from this release
MIN_VERSION = (1, 9, 18)

# Quarto 2 has its own version numbers. No release is known to render a great-docs
# site completely; this is the first one tried.
Q2_MIN_VERSION = (0, 45, 0)

# Quarto can fail while copying output in large projects when one process renames
# a file as another removes it. A retry can succeed after the filesystem race ends.
_TRANSIENT_ERRORS = ("No such file or directory", "renameSync", "os error 2")

_PROGRESS = re.compile(r"\[\s*(\d+)/(\d+)\]\s+(.+)")
_ANSI = re.compile(r"\033\[[0-9;]*m")

# Quarto 2 prints `q2 (quarto 2) 0.45.0`; with `-v` it logs each output once rendering
# ends, and closes with `Rendered 3 of 4 files to ...`
_Q2_VERSION = re.compile(r"\(quarto 2\)\s*(\d+(?:\.\d+)*)", re.IGNORECASE)
_Q2_OUTPUT = re.compile(r"\bINFO\b.*\bOutput: (.+)$")
_Q2_RENDERED = re.compile(r"^Rendered (\d+) of (\d+) files")
# Warnings read `Warning [Q-11-7]: ...`, or `Warning: ...` without a code
_Q2_WARNING = re.compile(r"^Warning:?\s*(?:\[(Q-[\d-]+)\])?:?\s*(.*)$")


class QuartoNotFoundError(BuildError):
    """A missing Quarto CLI"""


class QuartoVersionError(BuildError):
    """An installed Quarto CLI older than great-docs supports"""


def executable() -> str:
    """
    Return the Quarto command that renders and previews sites

    Returns
    -------
    :
        The value of `GREAT_DOCS_QUARTO`, or `quarto` when it is unset or empty.
    """
    return os.environ.get(EXECUTABLE_ENV, "").strip() or "quarto"


def is_q2() -> bool:
    """
    Whether great-docs renders with Quarto 2

    Returns
    -------
    :
        Whether the Quarto command is a `q2` binary, by its file name.
    """
    name = os.path.basename(executable()).lower()
    return name == "q2" or name.startswith(("q2.", "q2-"))


def installed_version() -> tuple[int, ...] | None:
    """
    Read the version of the Quarto CLI that great-docs runs

    Returns
    -------
    :
        The version components, or `None` if Quarto fails to report a recognisable version.
        Quarto 2 reports its own version numbers, which start at 0.
    """
    try:
        proc = subprocess.run(
            [executable(), "--version"],
            capture_output=True,
            timeout=30,
            check=True,
            **TEXT_MODE_KWARGS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = _Q2_VERSION.search(proc.stdout) or re.match(r"\s*(\d+(?:\.\d+)*)", proc.stdout)
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
        If Quarto is older than `MIN_VERSION`, or Quarto 2 older than `Q2_MIN_VERSION`.
    """
    if shutil.which(executable()) is None:
        if is_q2():
            raise QuartoNotFoundError(
                f"Quarto 2 was not found: {EXECUTABLE_ENV} is {executable()!r}, which is not "
                "an executable on the PATH. Set it to the path of a q2 binary, or unset it "
                "to render with Quarto 1."
            )
        raise QuartoNotFoundError(
            "Quarto was not found on your system. Quarto is a system-level "
            "dependency of great-docs and is not bundled with the Python package.\n\n"
            "See the troubleshooting guide:\n"
            "  https://posit-dev.github.io/great-docs/recipes/fix-common-build-errors.html\n\n"
            "Or fetch the binary programmatically by using your OS package (brew, yum, winget)."
        )
    version = installed_version()
    minimum, product = (Q2_MIN_VERSION, "Quarto 2") if is_q2() else (MIN_VERSION, "Quarto")
    if version is not None and version < minimum:
        found = ".".join(map(str, version))
        required = ".".join(map(str, minimum))
        raise QuartoVersionError(
            f"great-docs requires {product} {required} or later, but found {product} {found}. "
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

    # Quarto 2 ignores `QUARTO_PYTHON` and runs whichever `jupyter` and `python3` the
    # `PATH` finds first, so put the chosen Python's scripts directory first
    if is_q2():
        scripts = os.path.dirname(env["QUARTO_PYTHON"])
        env["PATH"] = os.pathsep.join([scripts, env.get("PATH", "")])
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

    Quarto 2 names its pages only once it has rendered them all, so `on_page` then runs for
    every page at the end and the result has no page timings. Its warnings reach
    `on_warning` once per warning code, with a count.

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
    q2 = is_q2()
    command = [executable(), "render"]
    if q2:
        command += ["-v", "--color", "never"]
    process = subprocess.Popen(
        command,
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=1,
        **TEXT_MODE_KWARGS,
    )
    stamps: list[tuple[str, float]] = []
    stderr: list[str] = []
    q2_outputs: list[str] = []
    q2_warnings: dict[str, list[str]] = {}

    def report_q2_warnings() -> None:
        if on_warning is not None:
            for warnings in q2_warnings.values():
                more = f" (and {len(warnings) - 1} more like it)" if len(warnings) > 1 else ""
                on_warning(f"WARN {warnings[0]}{more}")
        q2_warnings.clear()

    def handle_q2(line: str) -> None:
        plain = _ANSI.sub("", line).strip()
        output = _Q2_OUTPUT.search(plain)
        if output is not None:
            q2_outputs.append(os.path.relpath(output.group(1).strip(), project))
        elif warning := _Q2_WARNING.match(plain):
            code, message = warning.group(1) or "", warning.group(2).strip()
            q2_warnings.setdefault(code, []).append(f"[{code}] {message}" if code else message)
        elif _Q2_RENDERED.match(plain):
            # Report warnings first: a caller may stop taking them after the last page
            report_q2_warnings()
            for current, page in enumerate(q2_outputs, 1):
                if on_page is not None:
                    on_page(Progress(current, len(q2_outputs), page))

    def handle(line: str) -> None:
        if q2:
            handle_q2(line)
            return
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
    report_q2_warnings()
    return RenderResult(process.returncode, "".join(stderr), page_timings(stamps, time.monotonic()))
