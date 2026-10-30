"""
Documentation build steps and fatal errors
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO, cast

import griffe

if TYPE_CHECKING:
    from pathlib import Path

    from great_docs._build_log import BuildLog

__all__ = [
    "USER_CODE_ERRORS",
    "BuildError",
    "Skipped",
    "Step",
    "StepError",
    "Warn",
    "count_listed",
    "run_steps",
]

# Steps that import or run project code can warn on missing or broken modules, missing
# attributes, errors raised by that code, and failures to load the package with griffe.
# These exception types stop the build outside steps that handle project code failures.
USER_CODE_ERRORS: tuple[type[Exception], ...] = (
    ImportError,
    SyntaxError,
    AttributeError,
    RuntimeError,
    OSError,
    griffe.GriffeError,
)


class BuildError(RuntimeError):
    """
    A build failure that leaves no usable site

    The failure is reported in the build log or on standard error before this exception is
    raised. Command-line callers can exit without printing the message again.
    """


class StepError(BuildError):
    """
    A reported step failure that stops the build

    Parameters
    ----------
    message
        The failure line in the build log and the exception's message.
    detail
        Text shown below the failure line, such as Quarto's error output.
    """

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class Skipped:
    """
    The outcome and log message of a skipped step

    Attributes
    ----------
    reason
        Why the step did nothing, shown in the build log.
    """

    reason: str


# A step's outcome is a result line, a skip reason, or `None` for no result line.
Outcome = str | Skipped | None


@dataclass(frozen=True)
class Warn:
    """
    Recoverable step failures and their build log messages

    Attributes
    ----------
    catches
        Exception types reported as warnings. All other exceptions stop the build.
    message
        The warning's prefix; the log shows `"{message}: {error}"`.
    summary
        The step's result line after a warning.
    """

    catches: tuple[type[Exception], ...]
    message: str
    summary: str


@dataclass(frozen=True)
class Step:
    """
    A build step with its logging and exception policies

    Attributes
    ----------
    title
        The step's heading in the build log.
    run
        The step's action, returning a summary, `Skipped`, or `None` for an unlisted step.
    warn
        The failures the build survives, or `None` when every failure stops the build.
    fails_on
        Exception types raised to report a problem in the project. The runner logs the
        failure and raises `BuildError` with the original exception as its cause.
    user_code
        Whether the step imports or runs the project's code. These steps run in the build
        directory so project code resolves relative paths from there.
    quiet
        Whether the step's `print()` output goes to the build log as detail lines.
    listed
        Whether the step has a numbered heading and a result line. An unlisted step belongs
        to the preceding listed step, including its warning count.
    """

    title: str
    run: Callable[[], Outcome]
    warn: Warn | None = None
    fails_on: tuple[type[Exception], ...] = ()
    user_code: bool = False
    quiet: bool = True
    listed: bool = True


def count_listed(steps: Sequence[Step]) -> int:
    """
    Count the steps that have a numbered heading

    Parameters
    ----------
    steps
        The steps of a build.

    Returns
    -------
    :
        The total that the build log shows in each heading.
    """
    return sum(step.listed for step in steps)


def run_steps(steps: Sequence[Step], log: BuildLog, build_dir: Path) -> None:
    """
    Run build steps in order and log their outcomes

    Number listed steps consecutively. Report exceptions covered by a step's warning
    policy as warnings and continue. Report a `StepError` or an exception in `fails_on` as
    the step's failure, print the footer and stop. Re-raise `StepError` unchanged; convert
    exceptions in `fails_on` to `BuildError` with the original exception as the cause.
    Existing `BuildError` exceptions and all other exceptions propagate without a report.

    Parameters
    ----------
    steps
        The steps to run.
    log
        The build log.
    build_dir
        The working directory for steps that run the project's code.

    Raises
    ------
    BuildError
        If a step reports a failure with a `StepError` or an exception in `fails_on`; its
        message is the failure line. Any other `BuildError` from a step propagates unreported.
    """
    number = 0
    for step in steps:
        if step.listed:
            number += 1
            log.step_start(number, step.title)
        warn_on = step.warn.catches if step.warn else ()
        try:
            with _step_context(step, log, build_dir):
                outcome = step.run()
        except StepError as error:
            _report_failure(log, error.message, error.detail)
            raise
        except BuildError:
            raise
        except step.fails_on as error:
            _report_failure(log, f"{step.title} failed", str(error))
            raise BuildError(f"{step.title} failed: {error}") from error
        except warn_on as error:
            assert step.warn is not None
            log.warn(f"{step.warn.message}: {error}")
            outcome = step.warn.summary
        if isinstance(outcome, Skipped):
            log.step_skip(number, outcome.reason)
        elif outcome is not None:
            log.step_done(outcome)


def _report_failure(log: BuildLog, message: str, detail: str) -> None:
    """
    Report a failure that ends the build

    Parameters
    ----------
    log
        The build log.
    message
        The failure line.
    detail
        Text shown below the failure line; nothing when empty.
    """
    log.step_fail(message)
    if detail:
        log.error_detail(detail)
    log.footer()


@contextlib.contextmanager
def _step_context(step: Step, log: BuildLog, build_dir: Path) -> Generator[None]:
    """
    Set a step's working directory and standard output

    Parameters
    ----------
    step
        The step about to run.
    log
        The build log.
    build_dir
        The working directory for a step that runs the project's code.

    Yields
    ------
    :
        Nothing; the step runs inside the block.
    """
    with contextlib.ExitStack() as stack:
        if step.user_code:
            stack.enter_context(contextlib.chdir(build_dir))
        if step.quiet:
            stack.enter_context(_prints_to_detail(log))
        yield


@contextlib.contextmanager
def _prints_to_detail(log: BuildLog) -> Generator[None]:
    """
    Send `print()` output to the build log as detail lines

    The build log keeps writing to the stream it was created with.

    Parameters
    ----------
    log
        The build log.

    Yields
    ------
    :
        Nothing; output printed inside the block becomes detail lines.
    """
    stream = _DetailStream(log)
    # The stream implements only `write` and `flush`, which is all `print()` needs
    with contextlib.redirect_stdout(cast("TextIO", stream)):
        try:
            yield
        finally:
            stream.flush()


class _DetailStream:
    """
    A text stream that logs non-blank lines as build details

    It has no `encoding` attribute. Code that needs a full text stream, such as the marimo
    import, temporarily replaces it and discards its own output.

    Parameters
    ----------
    log
        The build log.
    """

    def __init__(self, log: BuildLog) -> None:
        self._log = log
        self._pending = ""

    def write(self, text: str) -> int:
        """
        Log complete lines from `text` and buffer the unfinished final line

        Parameters
        ----------
        text
            Text to write.

        Returns
        -------
        :
            The number of characters written.
        """
        *lines, self._pending = (self._pending + text).split("\n")
        for line in lines:
            if line.strip():
                self._log.detail(line.rstrip())
        return len(text)

    def flush(self) -> None:
        """
        Log the buffered final line
        """
        if self._pending.strip():
            self._log.detail(self._pending.rstrip())
        self._pending = ""
