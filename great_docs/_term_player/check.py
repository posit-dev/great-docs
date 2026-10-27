"""Drift detection: run a script's steps again and compare the result with its recording.

Both recordings are played through the terminal emulator, and the screen text is compared at
each marker and at the end. Timing and the exact output bytes aren't compared, since they change
from run to run even when nothing that matters has. Text that does change every run, such as a
version number or a temporary path, can be left out with `ignore` patterns.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from .emulator import TerminalEmulator
from .parser import Recording, parse_termshow
from .steps import Step, StepsError, load_steps, record_steps, screen_text

# What ignored text is replaced with on both sides
MASK = "…"


class CheckError(Exception):
    """A script can't be checked: it has no recording, no steps, or a mistake."""


@dataclass
class Snapshot:
    """The screen text at one point in a recording."""

    where: str
    """`marker 'LABEL'`, or `the end`."""
    text: str


@dataclass
class Difference:
    """One place where the new run doesn't match the recording."""

    where: str
    """The snapshot (`marker 'Install'`, `the end`), or `markers` when they don't line up."""
    lines: list[str]
    """A unified diff of the two screens, or for `markers`, a message."""


@dataclass
class CheckResult:
    """The outcome of checking one script."""

    recording_path: Path
    recording: Recording
    """The new run of the steps, for writing with `--update`."""
    differences: list[Difference]
    snapshots: int
    """How many points were compared."""

    @property
    def drifted(self) -> bool:
        return bool(self.differences)


def snapshots(recording: Recording) -> list[Snapshot]:
    """The screen at each marker (`m` event) and at the end of the recording."""
    emulator = TerminalEmulator(cols=recording.term.cols, rows=recording.term.rows)
    shots = []
    for event in recording.events:
        if event.code == "o":
            emulator.feed(event.data)
        elif event.code == "r":
            cols, _, rows = event.data.partition("x")
            if cols.isdigit() and rows.isdigit():
                emulator.resize(int(cols), int(rows))
        elif event.code == "m":
            shots.append(Snapshot(f"marker {event.data!r}", screen_text(emulator)))
    shots.append(Snapshot("the end", screen_text(emulator)))
    return shots


def mask(text: str, ignore: list[re.Pattern]) -> str:
    """Replace the text each pattern matches, row by row, with `MASK`."""
    if not ignore:
        return text
    rows = []
    for row in text.split("\n"):
        for pattern in ignore:
            row = pattern.sub(MASK, row)
        rows.append(row)
    return "\n".join(rows)


def compare(
    old: Recording, new: Recording, ignore: list[re.Pattern], *, name: str = "recording"
) -> tuple[list[Difference], int]:
    """Compare two recordings' screens. Returns the differences and the number of points compared.

    When the two have different markers, only the end is compared, since the screens at the
    markers can't be paired up.
    """
    before, after = snapshots(old), snapshots(new)
    differences = []
    if [s.where for s in before] != [s.where for s in after]:
        differences.append(
            Difference(
                "markers",
                [
                    f"{name} has {_markers(before)}, and the steps now give {_markers(after)}",
                ],
            )
        )
        before, after = before[-1:], after[-1:]
    for a, b in zip(before, after):
        old_text, new_text = mask(a.text, ignore), mask(b.text, ignore)
        if old_text != new_text:
            diff = difflib.unified_diff(
                old_text.split("\n"),
                new_text.split("\n"),
                fromfile=f"{name}, at {a.where}",
                tofile=f"the steps now, at {b.where}",
                lineterm="",
            )
            differences.append(Difference(a.where, list(diff)))
    return differences, len(after)


def _markers(shots: list[Snapshot]) -> str:
    labels = [s.where.removeprefix("marker ") for s in shots[:-1]]
    return "no markers" if not labels else f"markers {', '.join(labels)}"


def recording_for(script_path: Path) -> Path:
    """The recording a script belongs to: `demo.termshow` for `demo.termshow.yml`."""
    if not script_path.name.endswith(".termshow.yml"):
        raise CheckError(f"{script_path.name} isn't named NAME.termshow.yml")
    return script_path.with_name(script_path.name[: -len(".yml")])


def load_ignore(script_path: Path) -> list[str]:
    """The script's `check.ignore` patterns."""
    from yaml12 import read_yaml

    from .validate import ERROR, check_script_text

    problems = []
    check_script_text(script_path.read_text(encoding="utf-8"), script_path.name, problems)
    errors = [p for p in problems if p.severity == ERROR and re.match(r"check\b", p.where)]
    if errors:
        raise CheckError("\n".join(str(p) for p in errors))
    data = read_yaml(script_path)
    check = data.get("check") if isinstance(data, dict) else None
    return list((check or {}).get("ignore") or [])


def check_script(
    script_path: str | Path,
    *,
    ignore: Sequence[str] = (),
    shell: str | None = None,
    on_step: Callable[[int, Step], None] | None = None,
) -> CheckResult:
    """Run a script's steps and compare the result with the recording next to it.

    Parameters
    ----------
    script_path
        The `NAME.termshow.yml` script. Its recording is `NAME.termshow`.
    ignore
        Patterns to leave out of the comparison, added to the script's `check.ignore`.
    shell
        Runs the steps in this shell instead of the script's `record.shell`.
    on_step
        Called with the index and the step before each step runs.

    Returns
    -------
    CheckResult
        The differences, which are empty when the recording is up to date.

    Raises
    ------
    CheckError
        If the script has no recording or no steps, or has a mistake in `record`, `steps`, or
        `check`.
    StepsError
        If a step fails, as with `termshow record --steps`.
    """
    script_path = Path(script_path)
    recording_path = recording_for(script_path)
    if not recording_path.exists():
        raise CheckError(
            f"{recording_path} doesn't exist yet. Record it with "
            f"`great-docs termshow record --steps {script_path}`"
        )
    patterns = [*load_ignore(script_path), *ignore]
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as e:
            raise CheckError(f"{pattern!r} isn't a valid regular expression ({e})") from None
    try:
        settings, steps = load_steps(script_path)
    except StepsError as e:
        raise CheckError(str(e)) from None

    old = parse_termshow(recording_path)
    # The screens can only be compared at the size the recording was made at
    settings = replace(settings, cols=old.term.cols, rows=old.term.rows)
    if shell:
        settings = replace(settings, shell=shell)
    new = record_steps(settings, steps, title=recording_path.stem, on_step=on_step)
    differences, count = compare(old, new, compiled, name=recording_path.name)
    return CheckResult(recording_path, new, differences, count)
