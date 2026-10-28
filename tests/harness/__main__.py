"""
Command line of the characterisation harness

`run` records a base commit and the checkout under test and compares them; `record` and
`compare` do the two halves separately. Exit status: 0 when no case regressed, 1 on a
regression (or, with `--strict`, on any difference), 2 when the harness refuses to run.
Differences that aren't regressions are reported, and in GitHub Actions also raised as a
warning annotation, without failing the run.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from tests.harness.catalogue import BuildCase, full_cases, select, tier_cases
from tests.harness.compare import Comparison, compare, write_reports
from tests.harness.record import generate_all, record
from tests.harness.sides import (
    HarnessError,
    Side,
    base_side,
    checkout_side,
    child_environment,
    describe,
    environment_differences,
    harness_checkout,
    install_observer,
    outside_git,
    python_version,
    real_quarto,
    write_stub,
)


STRICT_HELP = "fail on any difference, not only on regressions"


def cache_directory(given: Path | None) -> Path:
    """
    Choose the directory for worktrees, recordings and job directories

    Parameters
    ----------
    given :
        Directory from `--cache-dir`, if any.

    Returns
    -------
    :
        `given`, else `$GREAT_DOCS_HARNESS_CACHE`, else `$XDG_CACHE_HOME/great-docs-harness`,
        else `~/.cache/great-docs-harness`.
    """
    if given is not None:
        return given.resolve()
    if os.environ.get("GREAT_DOCS_HARNESS_CACHE"):
        return Path(os.environ["GREAT_DOCS_HARNESS_CACHE"]).resolve()
    xdg = os.environ.get("XDG_CACHE_HOME")
    root = Path(xdg) if xdg else Path.home() / ".cache"
    return (root / "great-docs-harness").resolve()


def choose_cases(
    catalogue: str, only: Sequence[str], checkout: Path, side: Side
) -> list[BuildCase]:
    """
    Select catalogue cases by case identifier or package name

    Parameters
    ----------
    catalogue :
        `tier` or `full`.
    only :
        Case identifiers or package names; empty for all.
    checkout :
        Checkout whose `test-packages` holds the catalogue.
    side :
        Side with recorded interpreter facts, used to exclude unsupported full-catalogue specs.

    Returns
    -------
    :
        Matching cases in catalogue order.
    """
    if catalogue == "full":
        python = tuple(int(p) for p in str(side.facts["python"]).split("."))
        cases = full_cases(checkout / "test-packages", python)
    else:
        cases = tier_cases(checkout / "test-packages")
    return select(cases, only)


def prepare_work(cache: Path) -> tuple[Path, Path, Path]:
    """
    Create a fresh work directory with the stub `quarto` and the observer

    Parameters
    ----------
    cache :
        The cache directory.

    Returns
    -------
    :
        The work directory, the stub's directory and the observer's directory.
    """
    outside_git(cache)
    work = cache / "work" / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    work.mkdir(parents=True)
    stub_dir = work / "stub"
    _ = write_stub(stub_dir, real_quarto())
    return work, stub_dir, install_observer(work / "observer")


def exit_status(comparison: Comparison, strict: bool) -> int:
    """
    Choose the exit status of a comparison, warning GitHub Actions about passing differences

    Parameters
    ----------
    comparison :
        The comparison.
    strict :
        Fail on any difference, not only on regressions.

    Returns
    -------
    :
        0 when the comparison passes, else 1.
    """
    passes = comparison.passes(strict)
    if passes and not comparison.matches and os.environ.get("GITHUB_ACTIONS") == "true":
        differ = sum(c.status != "match" for c in comparison.cases)
        print(
            f"::warning title=Harness differences::{differ} of {len(comparison.cases)} cases "
            "differ from the base commit, with no regressions. Review the report."
        )
    return 0 if passes else 1


def command_run(args: argparse.Namespace) -> int:
    """
    Record the base commit and the checkout under test, then compare them

    Parameters
    ----------
    args :
        Parsed arguments of `run`.

    Returns
    -------
    :
        The exit status.
    """
    checkout = (args.checkout or harness_checkout()).resolve()
    cache = cache_directory(args.cache_dir)
    work, stub_dir, observer = prepare_work(cache)
    try:
        test = checkout_side(checkout)
        print(f"preparing base worktree for {args.base} in {cache / 'worktrees'}", flush=True)
        base = base_side(checkout, args.base, cache, python_version(test))
        base, test = describe(base, stub_dir), describe(test, stub_dir)
        drift = environment_differences(base.facts, test.facts)
        if drift:
            raise HarnessError("The two environments differ:\n  " + "\n  ".join(drift))
        cases = choose_cases(args.catalogue, args.only, harness_checkout(), test)
        out = (args.out or cache / "runs" / work.name).resolve()
        pristine = generate_all(cases, harness_checkout() / "test-packages", work)
        sides = [
            (side, out / side.label, child_environment(side, stub_dir, observer))
            for side in (base, test)
        ]
        wall = record(sides, cases, pristine, work, args.workers, args.timeout, args.keep)
    finally:
        if not args.keep:
            shutil.rmtree(work)
    comparison = compare(out / "base", out / "test")
    print(write_reports(comparison, out, args.strict))
    print(f"{len(cases)} cases on two sides in {wall} s; recordings and reports in {out}")
    return exit_status(comparison, args.strict)


def command_record(args: argparse.Namespace) -> int:
    """
    Record one checkout

    Parameters
    ----------
    args :
        Parsed arguments of `record`.

    Returns
    -------
    :
        The exit status, 0 once the recording is written.
    """
    cache = cache_directory(args.cache_dir)
    work, stub_dir, observer = prepare_work(cache)
    out = args.out.resolve()
    try:
        side = describe(checkout_side(args.checkout), stub_dir)
        cases = choose_cases(args.catalogue, args.only, harness_checkout(), side)
        pristine = generate_all(cases, harness_checkout() / "test-packages", work)
        environment = child_environment(side, stub_dir, observer)
        sides = [(side, out, environment)]
        wall = record(sides, cases, pristine, work, args.workers, args.timeout, args.keep)
    finally:
        if not args.keep:
            shutil.rmtree(work)
    print(f"{len(cases)} cases in {wall} s; recording in {out}")
    return 0


def command_compare(args: argparse.Namespace) -> int:
    """
    Compare two recordings

    Parameters
    ----------
    args :
        Parsed arguments of `compare`.

    Returns
    -------
    :
        0 when the comparison passes, 1 otherwise.
    """
    comparison = compare(args.base.resolve(), args.test.resolve())
    print(write_reports(comparison, (args.out or args.test.parent).resolve(), args.strict))
    return exit_status(comparison, args.strict)


def parser() -> argparse.ArgumentParser:
    """
    Create the parser for the harness commands

    Returns
    -------
    :
        The parser with the `run`, `record` and `compare` commands.
    """
    top = argparse.ArgumentParser(prog="python -m tests.harness", description=__doc__)
    commands = top.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser) -> None:
        _ = sub.add_argument("--catalogue", choices=["tier", "full"], default="tier")
        _ = sub.add_argument("--only", nargs="+", default=[], metavar="CASE")
        _ = sub.add_argument("--workers", type=int, default=4)
        _ = sub.add_argument("--timeout", type=float, default=300.0, help="seconds per command")
        _ = sub.add_argument("--cache-dir", type=Path, default=None)
        _ = sub.add_argument("--keep", action="store_true", help="keep job directories")

    run = commands.add_parser("run", help="record a base commit and this checkout, then compare")
    _ = run.add_argument("--base", default="main", help="base revision (default: main)")
    _ = run.add_argument("--checkout", type=Path, default=None, help="checkout under test")
    _ = run.add_argument("--out", type=Path, default=None, help="directory for recordings")
    _ = run.add_argument("--strict", action="store_true", help=STRICT_HELP)
    common(run)
    run.set_defaults(handler=command_run)

    rec = commands.add_parser("record", help="record one checkout")
    _ = rec.add_argument("checkout", type=Path)
    _ = rec.add_argument("--out", type=Path, required=True)
    common(rec)
    rec.set_defaults(handler=command_record)

    cmp = commands.add_parser("compare", help="compare two recordings")
    _ = cmp.add_argument("base", type=Path)
    _ = cmp.add_argument("test", type=Path)
    _ = cmp.add_argument("--out", type=Path, default=None, help="directory for the reports")
    _ = cmp.add_argument("--strict", action="store_true", help=STRICT_HELP)
    cmp.set_defaults(handler=command_compare)
    return top


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the harness command line

    Parameters
    ----------
    argv :
        Command-line arguments, or the process arguments when `None`.

    Returns
    -------
    :
        The exit status.
    """
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (HarnessError, ValueError) as exc:
        print(f"harness refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
