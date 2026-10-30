from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from great_docs._build.steps import (
    BuildError,
    Outcome,
    Skipped,
    Step,
    StepError,
    Warn,
    count_listed,
    run_steps,
)
from great_docs._build_log import BuildLog

# The elapsed time at the end of a result line, such as `<0.1s`
_TIMING = re.compile(r"\s+<?\d+(\.\d+)?s$")


def _log(steps: list[Step]) -> tuple[BuildLog, io.StringIO]:
    stream = io.StringIO()
    log = BuildLog(stream=stream, force_color=False, width=60, total_steps=count_listed(steps))
    return log, stream


def _lines(stream: io.StringIO) -> list[str]:
    """Return non-blank log lines without right-aligned timings or heading borders"""
    lines: list[str] = []
    for line in stream.getvalue().splitlines():
        text = _TIMING.sub("", line.rstrip(" -"))
        if text.strip():
            lines.append(text)
    return lines


def test_numbers_listed_steps_and_reports_outcomes(tmp_path: Path):
    steps = [
        Step("First", lambda: "Done first"),
        Step("Extra", lambda: print("extra detail"), listed=False),
        Step("Second", lambda: Skipped("nothing to do")),
    ]
    log, stream = _log(steps)

    run_steps(steps, log, tmp_path)

    assert _lines(stream) == [
        "-- Step  1/2 - First",
        "   [OK] Done first",
        "      extra detail",
        "-- Step  2/2 - Second",
        "   [--] Skipped (nothing to do)",
    ]


def test_runs_steps_when_they_run(tmp_path: Path):
    calls: list[str] = []

    class Project:
        def work(self) -> Outcome:
            calls.append("original")
            return "Done"

    project = Project()
    steps = [Step("Work", lambda: project.work())]
    project.work = lambda: calls.append("replaced") or "Done"  # type: ignore[method-assign]
    log, _ = _log(steps)

    run_steps(steps, log, tmp_path)

    assert calls == ["replaced"]


def test_quiet_step_prints_detail_lines(tmp_path: Path):
    def noisy() -> Outcome:
        print("first line")
        print("  ")
        print("partial", end="")
        return "Done"

    steps = [Step("Noisy", noisy), Step("Loud", lambda: print("raw") or "Done", quiet=False)]
    log, stream = _log(steps)

    run_steps(steps, log, tmp_path)

    lines = _lines(stream)
    assert lines[1:3] == ["      first line", "      partial"]
    assert "      raw" not in lines


def test_user_code_step_runs_in_build_dir(tmp_path: Path):
    seen: list[Path] = []
    steps = [
        Step("User code", lambda: seen.append(Path.cwd()) or "Done", user_code=True),
        Step("Own code", lambda: seen.append(Path.cwd()) or "Done"),
    ]
    log, _ = _log(steps)

    run_steps(steps, log, tmp_path)

    assert seen[0] == tmp_path.resolve()
    assert seen[1] != tmp_path.resolve()


def test_warn_step_survives_listed_failures(tmp_path: Path):
    def fail() -> Outcome:
        raise OSError("disk full")

    steps = [
        Step("Fragile", fail, warn=Warn((OSError,), "Error writing", "Writing had issues")),
        Step("Next", lambda: "Done"),
    ]
    log, stream = _log(steps)

    run_steps(steps, log, tmp_path)

    assert _lines(stream)[1:3] == [
        "   [!!] Error writing: disk full",
        "   [!!] Writing had issues (1 warning)",
    ]
    assert _lines(stream)[-1] == "   [OK] Done"


def test_warn_step_lets_other_failures_through(tmp_path: Path):
    def fail() -> Outcome:
        raise AttributeError("renamed method")

    steps = [Step("Fragile", fail, warn=Warn((OSError,), "Error", "Had issues"))]
    log, _ = _log(steps)

    with pytest.raises(AttributeError):
        run_steps(steps, log, tmp_path)


def test_step_error_reports_failure_and_stops(tmp_path: Path):
    def fail() -> Outcome:
        raise StepError("Render failed", detail="quarto: boom")

    ran: list[str] = []
    steps = [
        Step("Render", fail, warn=Warn((RuntimeError,), "Error", "Had issues")),
        Step("Later", lambda: ran.append("later") or "Done"),
    ]
    log, stream = _log(steps)

    with pytest.raises(StepError, match="Render failed"):
        run_steps(steps, log, tmp_path)

    output = stream.getvalue()
    assert "[FAIL] Render failed" in output
    assert "   quarto: boom" in output
    assert "Build failed at Step 1 - Render" in output
    assert ran == []


def test_deliberate_failure_becomes_build_error(tmp_path: Path):
    error = ValueError("path escapes the build directory")

    def fail() -> Outcome:
        raise error

    steps = [Step("Copy pages", fail, fails_on=(ValueError,))]
    log, stream = _log(steps)

    with pytest.raises(BuildError, match="Copy pages failed: path escapes") as raised:
        run_steps(steps, log, tmp_path)

    assert raised.value.__cause__ is error
    assert "[FAIL] Copy pages failed" in stream.getvalue()
    assert "   path escapes the build directory" in stream.getvalue()


def test_build_error_from_inside_a_step_is_not_a_warning(tmp_path: Path):
    def fail() -> Outcome:
        raise BuildError("Quarto is missing")

    steps = [Step("Fragile", fail, warn=Warn((RuntimeError,), "Error", "Had issues"))]
    log, _ = _log(steps)

    with pytest.raises(BuildError, match="Quarto is missing"):
        run_steps(steps, log, tmp_path)


def test_count_listed_skips_unlisted_steps():
    steps = [Step("A", lambda: "a"), Step("B", lambda: None, listed=False), Step("C", lambda: "c")]

    assert count_listed(steps) == 2
