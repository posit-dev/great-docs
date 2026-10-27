"""
Counts of exceptions handled by `great_docs`

Python imports this observer at start-up when the harness adds its directory to
`PYTHONPATH`. If `GREAT_DOCS_HARNESS_CENSUS` names a directory, the process writes
`<pid>.json` there at exit, with a count for each distinct handled exception.

The observer patches nothing and imports no `great_docs` module. It needs `sys.monitoring`
(Python 3.12) and stays inactive on older interpreters.
"""

from __future__ import annotations

import atexit
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import CodeType, TracebackType

CENSUS_VARIABLE = "GREAT_DOCS_HARNESS_CENSUS"

# Exception type, message, raising function, raising location, handling function, handling
# location. Locations are `file:line` relative to the `great_docs` package directory.
CensusKey = tuple[str, str, str, str, str, str]

# Retain enough text for path normalisation before the harness truncates messages.
# Truncating a path here could prevent its replacement.
_MESSAGE_LIMIT = 4000


def _package_directory() -> str | None:
    """
    Locate the `great_docs` package without importing it

    Returns
    -------
    :
        The resolved package directory with a trailing separator, or `None` when the
        interpreter cannot find `great_docs`.
    """
    spec = importlib.util.find_spec("great_docs")
    if spec is None or not spec.submodule_search_locations:
        return None
    return os.path.realpath(list(spec.submodule_search_locations)[0]) + os.sep


class Census:
    """
    Exception counts restricted to handlers within one package directory

    Parameters
    ----------
    package_dir :
        Resolved package directory, ending with a path separator.
    """

    def __init__(self, package_dir: str) -> None:
        self.package_dir = package_dir
        self.counts: dict[CensusKey, int] = {}
        self._relative_paths: dict[str, str | None] = {}

    def _relative(self, filename: str) -> str | None:
        """
        Resolve a code filename relative to the package directory

        Parameters
        ----------
        filename :
            A code object's `co_filename`.

        Returns
        -------
        :
            The POSIX path relative to the package, or `None` for a file outside it.
        """
        if filename not in self._relative_paths:
            real = os.path.realpath(filename)
            inside = real.startswith(self.package_dir)
            relative = Path(real).relative_to(self.package_dir).as_posix() if inside else None
            self._relative_paths[filename] = relative
        return self._relative_paths[filename]

    def handled(self, code: CodeType, offset: int, exc: BaseException) -> None:
        """
        Count an exception if its handler is inside the package

        The raising function is the innermost traceback frame inside the package, so an
        exception that a library raises is attributed to the package function that called it.

        Parameters
        ----------
        code :
            Code object of the function that handles the exception.
        offset :
            Bytecode offset of the handler. Unused.
        exc :
            The handled exception.
        """
        handler_file = self._relative(code.co_filename)
        if handler_file is None:
            return
        tb: TracebackType | None = exc.__traceback__
        handled_line = tb.tb_lineno if tb is not None else code.co_firstlineno
        raised_function, raised_at = code.co_qualname, f"{handler_file}:{handled_line}"
        while tb is not None:
            frame_file = self._relative(tb.tb_frame.f_code.co_filename)
            if frame_file is not None:
                raised_function = tb.tb_frame.f_code.co_qualname
                raised_at = f"{frame_file}:{tb.tb_lineno}"
            tb = tb.tb_next
        kind = type(exc)
        name = kind.__qualname__
        if kind.__module__ != "builtins":
            name = f"{kind.__module__}.{name}"
        key: CensusKey = (
            name,
            _message(exc),
            raised_function,
            raised_at,
            code.co_qualname,
            f"{handler_file}:{handled_line}",
        )
        self.counts[key] = self.counts.get(key, 0) + 1

    def write(self, directory: Path) -> None:
        """
        Write the counts to `<pid>.json` in a directory

        Parameters
        ----------
        directory :
            Destination; created when missing.
        """
        directory.mkdir(parents=True, exist_ok=True)
        records = [[*key, count] for key, count in sorted(self.counts.items())]
        payload = {"package_dir": self.package_dir, "argv": sys.argv[:2], "records": records}
        _ = (directory / f"{os.getpid()}.json").write_text(json.dumps(payload), encoding="utf-8")


def _message(exc: BaseException) -> str:
    """
    Format and truncate an exception message on one line

    Parameters
    ----------
    exc :
        The exception to describe.

    Returns
    -------
    :
        The message, with runs of whitespace replaced by one space and cut to a fixed length.
    """
    # Contain message-formatting errors so observation does not disrupt the program.
    try:
        text = str(exc)
    except (TypeError, ValueError, AttributeError, LookupError, RecursionError):
        text = "<unprintable>"
    return " ".join(text.split())[:_MESSAGE_LIMIT]


def _start() -> None:
    """Enable exception counts when a destination and monitoring tool are available"""
    target = os.environ.get(CENSUS_VARIABLE)
    if not target or sys.version_info < (3, 12):
        return
    package_dir = _package_directory()
    if package_dir is None:
        return
    census = Census(package_dir)
    monitoring = sys.monitoring
    for tool in (3, 4):
        try:
            monitoring.use_tool_id(tool, "great-docs-harness")
        except ValueError:
            continue
        _ = monitoring.register_callback(tool, monitoring.events.EXCEPTION_HANDLED, census.handled)
        monitoring.set_events(tool, monitoring.events.EXCEPTION_HANDLED)
        _ = atexit.register(census.write, Path(target))
        return


_start()
