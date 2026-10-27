"""Scripted recordings: run the `steps:` in a script and record the session.

The steps are typed into a shell running in a pseudo-terminal, with nothing
shown on screen. Output is timed as it arrives, so the recording plays at the
pace the commands really ran. A copy of the screen is kept with the terminal
emulator, which is what `wait_for` patterns and the prompt are matched against.
"""

from __future__ import annotations

import codecs
import os
import random
import re
import select
import shlex
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .emulator import TerminalEmulator
from .parser import Event, Recording, TermInfo

# Each action, and the options that go with it
ACTIONS: dict[str, tuple[str, ...]] = {
    "type": ("delay",),
    "run": ("delay", "timeout"),
    "key": ("count", "delay"),
    "sleep": (),
    "wait_for": ("timeout", "screen"),
    "marker": (),
}
# Steps written as a single word
WORDS = ("enter", "hide", "show")

KEYS = {
    "enter": "\r",
    "tab": "\t",
    "backspace": "\x7f",
    "escape": "\x1b",
    "space": " ",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "delete": "\x1b[3~",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
}

# Set for the shell unless the script's `record.env` says otherwise: a plain prompt that the
# default `prompt_pattern` matches, and no history file, so steps don't end up in yours
DEFAULT_ENV = {
    "PS1": "$ ",
    "TERM": "xterm-256color",
    "HISTFILE": "",
    "BASH_SILENCE_DEPRECATION_WARNING": "1",
}
# Removed from the environment, since they'd override the terminal size
_SIZE_VARS = ("COLUMNS", "LINES")

# How long to wait for the shell to exit after the last step
_EXIT_WAIT = 2.0


def key_sequence(name: str) -> str | None:
    """The characters a key sends, or None for a key that isn't known."""
    if name in KEYS:
        return KEYS[name]
    modifier, _, letter = name.partition("+")
    if len(letter) == 1 and "a" <= letter <= "z":
        if modifier == "ctrl":
            return chr(ord(letter) - ord("a") + 1)
        if modifier == "alt":
            return "\x1b" + letter
    return None


def screen_text(emulator: TerminalEmulator) -> str:
    """The screen's text, with trailing spaces removed from each row and blank rows at the end
    left out."""
    rows = ["".join(c.char for c in row).rstrip() for row in emulator.screen.cells]
    while rows and not rows[-1]:
        rows.pop()
    return "\n".join(rows)


class StepsError(Exception):
    """A script's steps can't be run, or a step failed."""

    def __init__(self, message: str, screen: str | None = None) -> None:
        super().__init__(message)
        self.screen = screen
        """The screen text when a step failed, if the session had started."""


@dataclass
class RecordSettings:
    """The script's `record:` section."""

    shell: str = "sh"
    cols: int = 80
    rows: int = 24
    cwd: Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    typing_delay: float = 0.05
    typing_jitter: float = 0.3
    timeout: float = 10.0
    prompt_pattern: str = r"\$ $"


@dataclass
class Step:
    """One entry in the script's `steps:` list."""

    action: str
    value: Any = None
    options: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        """The step as it's written in the script, for progress and error messages."""
        if self.action in WORDS:
            return self.action
        return f"{self.action}: {self.value}"


def load_steps(path: str | Path) -> tuple[RecordSettings, list[Step]]:
    """Read the `record:` settings and the `steps:` from a script.

    Parameters
    ----------
    path
        The `.termshow.yml` script.

    Returns
    -------
    tuple[RecordSettings, list[Step]]
        The settings, with `cwd` resolved against the script's directory, and the steps.

    Raises
    ------
    StepsError
        If the script can't be read, its `record` or `steps` section has errors, or it has no
        steps.
    """
    from .validate import ERROR, check_script_text

    path = Path(path)
    problems = []
    data = check_script_text(path.read_text(encoding="utf-8"), path.name, problems)
    # Mistakes elsewhere in the script don't stop it from being recorded
    errors = [
        p
        for p in problems
        if p.severity == ERROR and (data is None or re.match(r"(record|steps)\b", p.where))
    ]
    if errors:
        raise StepsError("\n".join(str(p) for p in errors))

    raw = _read_yaml(path)
    if not raw.get("steps"):
        raise StepsError(f"{path.name} has no steps to run")

    record = raw.get("record") or {}
    settings = RecordSettings(
        **{k: v for k, v in record.items() if k not in ("cwd", "env")},
        cwd=(path.parent / record.get("cwd", ".")).resolve(),
        env={k: _env_value(v) for k, v in (record.get("env") or {}).items()},
    )
    steps = []
    for item in raw["steps"]:
        if isinstance(item, str):
            steps.append(Step(item))
        else:
            action = next(k for k in item if k in ACTIONS)
            options = {k: v for k, v in item.items() if k != action}
            steps.append(Step(action, item[action], options))
    return settings, steps


def _read_yaml(path: Path) -> dict[str, Any]:
    from yaml12 import read_yaml

    data = read_yaml(path)
    return data if isinstance(data, dict) else {}


def _env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def record_steps(
    settings: RecordSettings,
    steps: list[Step],
    *,
    title: str = "",
    on_step: Callable[[int, Step], None] | None = None,
) -> Recording:
    """Run the steps in a new shell and return the recording.

    Parameters
    ----------
    settings
        The shell, terminal size, and timing defaults.
    steps
        What to do, in order.
    title
        The recording's title.
    on_step
        Called with the index and the step before each step runs, to report progress.

    Returns
    -------
    Recording
        The session, ending when the last step finishes, with an exit event (`x`) at the end.

    Raises
    ------
    StepsError
        If the shell can't be started, doesn't show its prompt, or exits early, or if a wait
        times out. The message says which step failed, and `screen` holds the screen text.
    """
    if sys.platform == "win32":
        raise StepsError("scripted recording needs a POSIX system (macOS or Linux)")

    session = _Session(settings)
    try:
        session.start()
        prompt = re.compile(settings.prompt_pattern)
        try:
            session.wait_for(prompt, timeout=settings.timeout)
        except StepsError as e:
            raise StepsError(f"while starting {settings.shell!r}: {e}", session.screen_text())
        for i, step in enumerate(steps):
            if on_step:
                on_step(i, step)
            try:
                _run_step(session, step, settings, prompt)
            except StepsError as e:
                raise StepsError(f"steps[{i}] ({step.describe()}): {e}", session.screen_text())
        exit_code = session.finish()
    finally:
        session.close()

    events = session.events + [Event(session.end_time, "x", str(exit_code))]
    env = {**DEFAULT_ENV, **settings.env}
    return Recording(
        term=TermInfo(cols=settings.cols, rows=settings.rows, type=env["TERM"]),
        title=title,
        events=events,
    )


def _run_step(session: _Session, step: Step, settings: RecordSettings, prompt: re.Pattern) -> None:
    opts = step.options
    delay = opts.get("delay", settings.typing_delay)
    timeout = opts.get("timeout", settings.timeout)
    if step.action == "type":
        session.type_text(step.value, delay)
    elif step.action == "run":
        session.type_text(step.value, delay)
        before_enter = session.output_count
        session.press(KEYS["enter"], delay)
        # Only output after Enter counts, so the prompt the command was typed at doesn't
        try:
            session.wait_for(prompt, timeout=timeout, after=before_enter)
        except StepsError:
            # A command like `exit` ends the session, which isn't a failure by itself
            if not session.exited:
                raise
    elif step.action == "key":
        for _ in range(opts.get("count", 1)):
            session.press(key_sequence(step.value), delay)
    elif step.action == "enter":
        session.press(KEYS["enter"], delay)
    elif step.action == "sleep":
        session.pump(step.value)
    elif step.action == "wait_for":
        screen = opts.get("screen", False)
        pattern = re.compile(step.value, re.MULTILINE if screen else 0)
        session.wait_for(pattern, timeout=timeout, screen=screen)
    elif step.action == "marker":
        session.events.append(Event(session.now(), "m", str(step.value)))
    elif step.action == "hide":
        session.hide()
    elif step.action == "show":
        session.show()


class _Session:
    """A shell in a pseudo-terminal, with its output timed and fed to an emulator."""

    def __init__(self, settings: RecordSettings) -> None:
        self.settings = settings
        self.emulator = TerminalEmulator(cols=settings.cols, rows=settings.rows)
        self.events: list[Event] = []
        self.exited = False
        self.end_time = 0.0
        # Output chunks read so far, so a wait can tell whether anything new has arrived
        self.output_count = 0
        self._random = random.Random(0)  # the same jitter every run
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pid = 0
        self._fd = -1
        self._start = 0.0
        self._hidden_at: float | None = None
        self._hidden_total = 0.0
        self._recording = True

    def start(self) -> None:
        import fcntl
        import pty
        import struct
        import termios

        try:
            argv = shlex.split(self.settings.shell)
        except ValueError as e:
            raise StepsError(f"can't read record.shell: {e}") from None
        env = {k: v for k, v in os.environ.items() if k not in _SIZE_VARS}
        env.update(DEFAULT_ENV)
        env.update(self.settings.env)
        winsize = struct.pack("HHHH", self.settings.rows, self.settings.cols, 0, 0)

        pid, fd = pty.fork()
        if pid == 0:  # pragma: no cover - the child process
            # fd 1 is the terminal here (`sys.stdout` may have been replaced, as under pytest)
            try:
                fcntl.ioctl(1, termios.TIOCSWINSZ, winsize)
                if self.settings.cwd is not None:
                    os.chdir(self.settings.cwd)
                os.execvpe(argv[0], argv, env)
            except OSError as e:
                # Shown on the screen, which the error message includes
                os.write(1, f"{argv[0]}: {e.strerror}\r\n".encode())
            os._exit(127)

        self._pid, self._fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        self._start = time.monotonic()

    # The clock --------------------------------------------------------------------------------

    def now(self) -> float:
        """Recording time. It stops while the session is hidden."""
        if self._hidden_at is not None:
            return self._hidden_at
        return round(time.monotonic() - self._start - self._hidden_total, 3)

    def hide(self) -> None:
        if self._hidden_at is None:
            self._hidden_at = self.now()

    def show(self) -> None:
        if self._hidden_at is not None:
            hidden_at, self._hidden_at = self._hidden_at, None
            self._hidden_total += self.now() - hidden_at

    # Input and output -------------------------------------------------------------------------

    def _write(self, text: str) -> None:
        if self.exited:
            raise StepsError("the shell has exited")
        os.write(self._fd, text.encode("utf-8"))

    def type_text(self, text: str, delay: float) -> None:
        # One input event per typed string, at its first keystroke: that's where prompt
        # detection looks for the prompt
        self.events.append(Event(self.now(), "i", text))
        for ch in text:
            self._write(ch)
            self.pump(self._jitter(delay))

    def press(self, keys: str, delay: float) -> None:
        self._write(keys)
        self.pump(self._jitter(delay))

    def _jitter(self, delay: float) -> float:
        spread = self.settings.typing_jitter
        return delay * self._random.uniform(1 - spread, 1 + spread) if spread else delay

    def pump(self, seconds: float, until: Callable[[], bool] | None = None) -> bool:
        """Read output for `seconds`, or until `until()` is true. Returns whether it was."""
        deadline = time.monotonic() + seconds
        while True:
            if until is not None and until():
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            if self.exited:
                if until is not None:
                    return False
                time.sleep(remaining)
                return False
            readable, _, _ = select.select([self._fd], [], [], remaining)
            if readable:
                self._read()

    def _read(self) -> None:
        try:
            data = os.read(self._fd, 65536)
        except OSError:  # EIO on Linux once the shell has exited
            data = b""
        if not data:
            self.exited = True
            return
        text = self._decoder.decode(data)
        if text and self._recording:
            self.events.append(Event(self.now(), "o", text))
            self.emulator.feed(text)
            self.output_count += 1

    def wait_for(
        self,
        pattern: re.Pattern,
        *,
        timeout: float,
        screen: bool = False,
        after: int | None = None,
    ) -> None:
        """Wait until `pattern` matches the cursor's line, or the screen with `screen`.

        With `after`, a match only counts once more than that many output chunks have been read.
        """

        def matched() -> bool:
            if after is not None and self.output_count <= after:
                return False
            return bool(pattern.search(self.screen_text() if screen else self.cursor_line()))

        if self.pump(timeout, until=matched):
            return
        place = "the screen" if screen else "the cursor's line"
        if self.exited:
            raise StepsError(f"the shell exited before '{pattern.pattern}' appeared on {place}")
        raise StepsError(f"'{pattern.pattern}' didn't appear on {place} within {timeout:g}s")

    # The screen -------------------------------------------------------------------------------

    def screen_text(self) -> str:
        return screen_text(self.emulator)

    def cursor_line(self) -> str:
        """The text of the cursor's row, up to the cursor or to the last character."""
        screen = self.emulator.screen
        text = "".join(c.char for c in screen.cells[screen.cursor_row])
        stripped = text.rstrip()
        # Keep spaces before the cursor, so the `$ ` of a prompt still ends in a space
        return text[: screen.cursor_col] if screen.cursor_col > len(stripped) else stripped

    # Ending -----------------------------------------------------------------------------------

    def finish(self) -> int:
        """Stop recording, end the shell, and return its exit status."""
        self.end_time = self.now()
        self._recording = False
        if not self.exited:
            try:
                self._write("\x04")  # Ctrl+D
            except OSError:
                pass
        deadline = time.monotonic() + _EXIT_WAIT
        while time.monotonic() < deadline:
            pid, status = os.waitpid(self._pid, os.WNOHANG)
            if pid:
                self._pid = 0
                return os.WEXITSTATUS(status) if os.WIFEXITED(status) else 1
            if not self.exited:
                self.pump(0.05)
            else:
                time.sleep(0.02)
        return 1

    def close(self) -> None:
        """Stop the shell if it's still running and release the terminal."""
        if self._pid:
            import signal

            try:
                os.kill(self._pid, signal.SIGKILL)
                os.waitpid(self._pid, 0)
            except (OSError, ChildProcessError):
                pass
            self._pid = 0
        if self._fd >= 0:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = -1
