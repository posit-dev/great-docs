"""
Record command results and project changes for each build case and checkout

Each side's recording directory contains `side.json` with environment facts,
`builds/<case>.json` with one manifest per case, `logs/` with normalised command output for
diagnosis, and `blobs/` with normalised file contents indexed by SHA-256 and shared by cases.

A manifest records, for each command of the case: the exit status, every file the command
added, changed or removed in the project, the step skeleton and `[!!]` warnings of its
output, the census of exceptions that `great_docs` handled, and the calls that reached the
stub `quarto`.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import multiprocessing
import os
import shutil
import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.harness.catalogue import COMMANDS, BuildCase, generate, has_config, pin_mtimes
from tests.harness.normalise import (
    FILE_RULES,
    Rule,
    log_skeleton,
    log_warnings,
    normalise_bytes,
    normalise_message,
    normalise_text,
    path_rules,
)
from tests.harness.sides import (
    CENSUS_VARIABLE,
    QUARTO_LOG_VARIABLE,
    RENDER_PAGES_VARIABLE,
    HarnessError,
    Side,
)

# Bumped whenever the manifest format changes; comparisons refuse mixed schemas.
SCHEMA = 2

# Not build output: Python writes `__pycache__` when it imports the package, and Git rewrites
# the stat data in `.git` of a copied repository.
SKIPPED_DIRECTORIES = frozenset({"__pycache__", ".git"})


@dataclass(frozen=True)
class Job:
    """
    A build case and its execution context on one checkout

    Attributes
    ----------
    case :
        The build case.
    side :
        The side that builds it.
    pristine :
        The generated package, copied before the first command.
    work :
        Root of the job directories.
    recording :
        The side's recording directory.
    environment :
        Environment shared by the side's commands.
    timeout :
        Seconds each command may run.
    keep :
        Whether to keep the job directory after recording.
    """

    case: BuildCase
    side: Side
    pristine: Path
    work: Path
    recording: Path
    environment: Mapping[str, str]
    timeout: float
    keep: bool


def scan(root: Path) -> dict[str, str]:
    """
    Fingerprint every file under a directory

    Parameters
    ----------
    root :
        Directory to scan.

    Returns
    -------
    :
        Mapping from each POSIX path relative to `root` to its raw content's SHA-256,
        or to `symlink:<target>` for a symbolic link.
    """
    found: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        directory = Path(dirpath)
        links = [d for d in dirnames if (directory / d).is_symlink()]
        dirnames[:] = sorted(d for d in dirnames if d not in SKIPPED_DIRECTORIES and d not in links)
        for name in [*filenames, *links]:
            path = directory / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                found[rel] = f"symlink:{os.readlink(path)}"
            else:
                found[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def store_blob(blobs: Path, data: bytes) -> str:
    """
    Add content to a side's blob store

    Parameters
    ----------
    blobs :
        The store directory.
    data :
        Normalised file content.

    Returns
    -------
    :
        The content's SHA-256, which names the blob.
    """
    digest = hashlib.sha256(data).hexdigest()
    target = blobs / digest[:2] / digest
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{digest}.{os.getpid()}.partial")
        _ = partial.write_bytes(data)
        os.replace(partial, target)
    return digest


def file_changes(
    package: Path,
    before: Mapping[str, str],
    after: Mapping[str, str],
    rules: Sequence[Rule],
    blobs: Path,
    counts: dict[str, int],
) -> list[dict[str, Any]]:
    """
    Describe the files one command added, changed or removed

    Parameters
    ----------
    package :
        The package directory.
    before, after :
        Fingerprints from `scan` before and after the command.
    rules :
        Normalisation rules for file content.
    blobs :
        Blob store that receives the normalised content.
    counts :
        Replacements per rule, updated in place.

    Returns
    -------
    :
        One record per path, sorted by path.
    """
    records: list[dict[str, Any]] = []
    for rel in sorted(set(before) | set(after)):
        old, new = before.get(rel), after.get(rel)
        if old == new:
            continue
        if new is None:
            records.append({"path": rel, "change": "removed"})
            continue
        path = package / rel
        if new.startswith("symlink:"):
            kind, data = "symlink", os.readlink(path).encode()
        else:
            data = path.read_bytes()
            kind = "binary" if b"\x00" in data else "text"
        data, applied = normalise_bytes(data, rel, rules)
        for name, n in applied.items():
            counts[name] = counts.get(name, 0) + n
        records.append(
            {
                "path": rel,
                "change": "added" if old is None else "changed",
                "kind": kind,
                "size": len(data),
                "sha256": store_blob(blobs, data),
            }
        )
    return records


def read_census(directory: Path, rules: Sequence[Rule]) -> tuple[list[dict[str, Any]], int]:
    """
    Merge the census files that a command's processes wrote

    Entries are keyed by exception type, normalised message and raising function. Line
    numbers and handlers are kept for the report only, so moving code does not by itself
    create a new entry.

    Parameters
    ----------
    directory :
        Directory named by `GREAT_DOCS_HARNESS_CENSUS` for the command.
    rules :
        Path rules for messages.

    Returns
    -------
    :
        The entries sorted by key, and the number of processes that reported.
    """
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        for kind, message, raised_in, raised_at, handler, handled_at, count in payload["records"]:
            key = (kind, normalise_message(message, rules), raised_in)
            entry = merged.setdefault(key, {"count": 0, "raised_at": set(), "handlers": set()})
            entry["count"] += count
            entry["raised_at"].add(raised_at)
            entry["handlers"].add(f"{handler} ({handled_at})")
    entries = [
        {
            "type": kind,
            "message": message,
            "raised_in": raised_in,
            "count": entry["count"],
            "raised_at": sorted(entry["raised_at"]),
            "handlers": sorted(entry["handlers"]),
        }
        for (kind, message, raised_in), entry in sorted(merged.items())
    ]
    return entries, len(files)


def package_paths(package: Path) -> list[str]:
    """
    List the `PYTHONPATH` entries that `test-packages/render_all.py` gives a package

    Parameters
    ----------
    package :
        The package directory.

    Returns
    -------
    :
        The package directory, then its `src`, `python` and `lib` directories when present.
    """
    subdirs = [package / sub for sub in ("src", "python", "lib")]
    return [str(package), *(str(d) for d in subdirs if d.is_dir())]


def _read_text(path: Path) -> str:
    """
    Read command output, replacing invalid UTF-8 bytes

    Parameters
    ----------
    path :
        Output file.

    Returns
    -------
    :
        The text, with undecodable bytes replaced.
    """
    return path.read_bytes().decode("utf-8", errors="replace")


def run_command(
    job: Job,
    name: str,
    package: Path,
    rules: Sequence[Rule],
    before: Mapping[str, str],
    counts: dict[str, int],
) -> tuple[dict[str, Any], dict[str, str]]:
    """
    Run one `great-docs` command on a package and describe its effect

    Parameters
    ----------
    job :
        The job the command belongs to.
    name :
        Key of `COMMANDS`.
    package :
        The package directory.
    rules :
        Path rules followed by file rules.
    before :
        Fingerprints of the package before the command.
    counts :
        Replacements per rule, updated in place.

    Returns
    -------
    :
        The command's record and the package fingerprints after it.

    Raises
    ------
    HarnessError
        If the command finished but no process reported a census, which means the observer
        did not load.
    """
    job_dir = package.parent
    census_dir = job_dir / f"census-{name}"
    quarto_log = job_dir / f"quarto-{name}.log"
    env = {
        **job.environment,
        "PYTHONPATH": os.pathsep.join([*package_paths(package), job.environment["PYTHONPATH"]]),
        CENSUS_VARIABLE: str(census_dir),
        QUARTO_LOG_VARIABLE: str(quarto_log),
    }
    if job.case.render_pages:
        env[RENDER_PAGES_VARIABLE] = "1"
    argv = [
        str(job.side.bin / "great-docs"),
        *COMMANDS[name],
        *job.case.arguments.get(name, ()),
        "--project-path",
        str(package),
    ]
    out_file, err_file = job_dir / f"{name}.out", job_dir / f"{name}.err"
    start = time.perf_counter()
    with out_file.open("wb") as out, err_file.open("wb") as err:
        try:
            status: int | str = subprocess.run(
                argv,
                cwd=job_dir,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=job.timeout,
                check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            status = "timeout"
    seconds = round(time.perf_counter() - start, 2)

    after = scan(package)
    files = file_changes(package, before, after, rules, job.recording / "blobs", counts)
    stdout, _ = normalise_text(_read_text(out_file), "", rules)
    stderr, _ = normalise_text(_read_text(err_file), "", rules)
    log = job.recording / "logs" / f"{job.case.id}.{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    _ = log.write_text(f"{stdout}\n--- stderr ---\n{stderr}", encoding="utf-8")

    census, reporters = read_census(census_dir, rules)
    if status != "timeout" and reporters == 0:
        raise HarnessError(f"{job.case.id} {name}: no census reported; the observer did not load")
    calls = quarto_log.read_text(encoding="utf-8").splitlines() if quarto_log.exists() else []
    record = {
        "status": status,
        "seconds": seconds,
        "files": files,
        "skeleton": log_skeleton(stdout, stderr),
        "warnings": log_warnings(stdout, stderr),
        "census": census,
        "python_processes": reporters,
        "quarto_calls": sorted(normalise_text(c, "", rules)[0] for c in calls),
    }
    return record, after


def record_case(job: Job) -> dict[str, Any]:
    """
    Build one case on one side in a fresh job directory and write its manifest

    Parameters
    ----------
    job :
        The job to run.

    Returns
    -------
    :
        A summary for progress output: case, side, status and seconds of each command.
    """
    job_dir = job.work / job.side.label / job.case.id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)
    package = job_dir / job.case.package
    _ = shutil.copytree(job.pristine, package, symlinks=True)
    pin_mtimes(package)
    tokens = {
        "<PKG>": package,
        "<JOB>": job_dir,
        "<WORK>": job.work,
        "<GREAT_DOCS>": job.side.great_docs_dir,
        "<VENV>": job.side.venv,
        "<CHECKOUT>": job.side.checkout,
    }
    rules = (*path_rules(tokens), *FILE_RULES)
    counts: dict[str, int] = {}
    commands: dict[str, Any] = {}
    fingerprints = scan(package)
    for name in job.case.commands:
        if name == "init" and has_config(package):
            commands[name] = {"status": "skipped"}
            continue
        commands[name], fingerprints = run_command(job, name, package, rules, fingerprints, counts)
    manifest = {
        "schema": SCHEMA,
        "case": job.case.id,
        "package": job.case.package,
        "variant": job.case.variant,
        "overlay": dict(job.case.overlay) if job.case.overlay else None,
        "expects_reference": job.case.expects_reference,
        "order": list(commands),
        "commands": commands,
        "normalised": dict(sorted(counts.items())),
    }
    target = job.recording / "builds" / f"{job.case.id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    if not job.keep:
        shutil.rmtree(job_dir)
    return {
        "case": job.case.id,
        "side": job.side.label,
        "commands": {k: (v["status"], v.get("seconds", 0.0)) for k, v in commands.items()},
    }


def generate_all(cases: Iterable[BuildCase], test_packages: Path, work: Path) -> dict[str, Path]:
    """
    Generate each case's package once, for every side to copy

    Parameters
    ----------
    cases :
        The build cases.
    test_packages :
        The `test-packages` directory of the harness's checkout.
    work :
        Work directory; packages go to `work/pristine/<case>`.

    Returns
    -------
    :
        Case identifier to package directory.
    """
    pristine: dict[str, Path] = {}
    for case in cases:
        parent = work / "pristine" / case.id
        if parent.exists():
            shutil.rmtree(parent)
        parent.mkdir(parents=True)
        pristine[case.id] = generate(case, test_packages, parent)
    return pristine


def record(
    sides: Sequence[tuple[Side, Path, Mapping[str, str]]],
    cases: Sequence[BuildCase],
    pristine: Mapping[str, Path],
    work: Path,
    workers: int,
    timeout: float = 300.0,
    keep: bool = False,
) -> float:
    """
    Record every case on every side in a pool of worker processes

    Interleave submissions by case in a shared worker pool to give both sides comparable
    scheduling conditions.

    Parameters
    ----------
    sides :
        Each side with its recording directory and command environment.
    cases :
        The build cases.
    pristine :
        Generated package per case identifier.
    work :
        Root of the job directories.
    workers :
        Number of worker processes.
    timeout :
        Seconds each command may run.
    keep :
        Whether to keep job directories.

    Returns
    -------
    :
        Wall time in seconds.
    """
    jobs = [
        Job(case, side, pristine[case.id], work, recording, environment, timeout, keep)
        for case in cases
        for side, recording, environment in sides
    ]
    for side, recording, _ in sides:
        if recording.exists():
            shutil.rmtree(recording)
        recording.mkdir(parents=True)
    seconds: dict[str, float] = {side.label: 0.0 for side, _, _ in sides}
    start = time.perf_counter()
    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(workers, mp_context=context) as pool:
        futures = [pool.submit(record_case, job) for job in jobs]
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            if future.exception() is not None:
                # Cancel queued jobs; the pool waits for running jobs before propagating the error.
                for queued in futures:
                    _ = queued.cancel()
            summary = future.result()
            parts = ", ".join(f"{k} {status}" for k, (status, _) in summary["commands"].items())
            spent = sum(s for _, s in summary["commands"].values())
            seconds[summary["side"]] += spent
            print(
                f"[{done:>3}/{len(jobs)}] {summary['side']:<4} {summary['case']}: {parts} ({spent:.1f} s)"
            )
    wall = round(time.perf_counter() - start, 1)
    for side, recording, _ in sides:
        meta = {
            "schema": SCHEMA,
            "label": side.label,
            "facts": dict(side.facts),
            "cases": [case.id for case in cases],
            "wall_seconds": wall,
            "command_seconds": round(seconds[side.label], 1),
        }
        _ = (recording / "side.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return wall
