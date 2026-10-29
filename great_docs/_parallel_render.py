"""
Render a website with several Quarto processes at once

Quarto renders the pages of a website one after another in a single process,
so a site with thousands of pages takes as long as all of them put together.
This module splits the pages into groups and renders the groups in parallel,
each in its own copy of the project. Every copy is the whole project, so each
process sees every page when it builds navigation, resolves links and fills
the search index, and no two processes write to the same files.

A group of pages is rendered with `quarto render <directory>`, which renders
the project's inputs whose path starts with the directory's path. Quarto
compares the paths as strings, so an empty directory named after a common
prefix (such as `reference/fmt_`) selects just the pages starting with it,
rendered by one process in one project context.

A parallel render goes like this:

1. The project's pre-render scripts run once, in the project.
2. `quarto inspect` lists the inputs, which are planned into groups using the
   page timings of the last build.
3. Worker copies of the project (without pre- and post-render scripts) render
   the groups from a shared queue, largest first, through Quarto's freezer.
4. The outputs, freeze caches and search indexes are merged into the
   project's output directory.
5. The project's post-render scripts run once, as after a full render.

Anything unexpected (a page Quarto didn't render, a layout this can't split)
makes `render()` return a result with `fallback` set, and the caller renders
the site the ordinary way.
"""

from __future__ import annotations

import heapq
import json
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from bisect import bisect_left
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from statistics import median
from typing import Any

from yaml12 import parse_yaml, write_yaml

from ._subprocess import TEXT_MODE_KWARGS
from ._utils import QUARTO_YML_HEADER

JOBS_ENV = "GREAT_DOCS_RENDER_JOBS"
"""Environment variable giving the number of render processes (`auto` or a number)"""

MAX_AUTO_JOBS = 8
"""The most processes `auto` starts"""

MIN_PAGES = 40
"""Sites with fewer pages render in one process"""

TARGET_OVERHEAD = 2.0
"""Seconds a Quarto process spends before and after its pages, with others running"""

OVERHEAD_PER_INPUT = 0.0015
"""Seconds more for each input in the project, which Quarto reads as it starts"""

DEFAULT_PAGE_COST = 0.4
"""Seconds a page without code takes when no earlier timing is known"""

EXEC_PAGE_COST = 2.5
"""Seconds added for a page with executable code when no earlier timing is known"""

TRACE_ENV = "GREAT_DOCS_RENDER_TRACE"
"""Environment variable naming a file to write the timeline of a parallel render to"""

WORKER_TAG = "-render-"
"""Infix of the names of worker copies, `.<build dir name>-render-<n>`"""

# Files at the top of the output directory that each worker writes for its own
# pages and that are merged rather than copied
_SEARCH = "search.json"
_SITEMAP = "sitemap.xml"
_LISTINGS = "listings.json"

# The project's files a worker doesn't need
_SKIP_COPY = {"_site", ".quarto", "_gd_sidebars"}

# Pre-render scripts Great Docs adds that don't change the project's inputs
_KNOWN_PRE_RENDER = {"scripts/restore-freeze.py"}

# Keys of `_quarto.yml` that only Great Docs reads, before the render
_NOT_FOR_QUARTO = ("api-reference",)
_SIDEBAR_META = "_gd_render_sidebars.yml"

_TRANSIENT_PATTERNS = ("No such file or directory", "renameSync", "os error 2")
_GLOB_CHARS = frozenset("*?[]{}")
_PROGRESS_RE = re.compile(r"\[\s*(\d+)/(\d+)\]\s+(.+)")
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_URL_RE = re.compile(r"<url>.*?</url>", re.S)
_LOC_RE = re.compile(r"<loc>([^<]*)</loc>")


def resolve_jobs(jobs: int | str | None) -> int:
    """
    Work out how many render processes to use

    Parameters
    ----------
    jobs
        A number, `"auto"`, or `None` to read `GREAT_DOCS_RENDER_JOBS` (and
        render in one process when that isn't set).

    Returns
    -------
    :
        The number of processes, `1` meaning an ordinary render.
    """
    if jobs is None:
        jobs = os.environ.get(JOBS_ENV) or 1
    if isinstance(jobs, str):
        text = jobs.strip().lower()
        if text in ("auto", "0"):
            return _auto_jobs()
        try:
            jobs = int(text)
        except ValueError:
            raise ValueError(f"Render jobs must be a number or 'auto', not {jobs!r}") from None
    if jobs <= 0:
        return _auto_jobs()
    return jobs


def _auto_jobs() -> int:
    """One process per core, counting only the fast cores on Apple silicon"""
    cores = os.cpu_count() or 1
    if sys.platform == "darwin":
        try:
            fast = subprocess.run(
                ["sysctl", "-n", "hw.perflevel0.physicalcpu"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            cores = int(fast.stdout.strip()) if fast.returncode == 0 else cores
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return max(1, min(cores, MAX_AUTO_JOBS))


# ── Planning ─────────────────────────────────────────────────────────────────


@dataclass
class Target:
    """A group of pages one Quarto process renders"""

    path: str
    """What to pass to `quarto render`, relative to the project"""

    inputs: list[str]
    """The inputs it renders, relative to the project"""

    cost: float
    """Estimated seconds the pages take, not counting Quarto's own overhead"""

    @property
    def single(self) -> bool:
        """Whether the target is one file (Quarto shows no progress for these)"""
        return len(self.inputs) == 1 and self.path == self.inputs[0]


def plan_targets(
    inputs: Sequence[str],
    costs: Mapping[str, float],
    workers: int,
    atomic: Iterable[str] = (),
    can_name: Callable[[str], bool] = lambda path: True,
    overhead: float = TARGET_OVERHEAD,
) -> list[Target] | None:
    """
    Split a project's inputs into groups that Quarto can render separately

    The inputs are split on their paths, one character at a time, and only
    where a directory of that name selects the group's inputs and nothing
    else, the way Quarto matches them. Splitting the most expensive group
    again and again gives a series of plans; the one that the workers should
    finish soonest, counting the time each Quarto process takes to start, is
    returned.

    Parameters
    ----------
    inputs
        The project's inputs, relative to the project, as POSIX paths.
    costs
        Estimated seconds each input takes to render.
    workers
        The number of processes that will render the groups.
    atomic
        Directories whose inputs must be rendered together, such as those of
        listing pages (`""` for the project itself).
    can_name
        Whether a path can be used as a group's directory, which is created
        (empty) when it doesn't exist.
    overhead
        Seconds each group costs on top of its pages.

    Returns
    -------
    :
        The groups, most expensive first, or `None` when the inputs can't be
        split.
    """
    atomic = {d.strip("/") for d in atomic}
    if "" in atomic or not inputs:
        return None
    ordered = sorted(inputs)
    workers = max(workers, 1)

    def covered(path: str) -> int:
        """Count the inputs `quarto render <path>` would select"""
        return bisect_left(ordered, path + "\U0010ffff") - bisect_left(ordered, path)

    def locked(prefix: str) -> bool:
        return any(prefix.startswith(d + "/") for d in atomic)

    def settle(prefix: str, members: list[str]) -> list[_Group] | None:
        """Split a group until each part can be rendered on its own"""
        groups: list[_Group] = []
        stack = [(prefix, members)]
        while stack:
            prefix, members = stack.pop()
            cost = sum(costs.get(m, DEFAULT_PAGE_COST) for m in members)
            if len(members) == 1:
                groups.append(_Group(members[0], members[0], members, cost, False))
                continue
            # Quarto drops a trailing separator, so `reference/` selects `reference*`
            path = prefix.rstrip("/")
            selectable = bool(path) and covered(path) == len(members) and can_name(path)
            if locked(prefix):
                if not selectable:
                    return None
                groups.append(_Group(prefix, path, members, cost, False))
            elif selectable:
                groups.append(_Group(prefix, path, members, cost, True))
            else:
                stack.extend(_children(prefix, members))
        return groups

    groups = settle("", list(inputs))
    if groups is None:
        return None
    best, best_time = list(groups), _makespan([g.cost for g in groups], workers, overhead)
    while len(groups) < 16 * workers:
        candidates = [g for g in groups if g.splittable]
        if not candidates:
            break
        group = max(candidates, key=lambda g: g.cost)
        # Splitting a group cheaper than a process start can't help
        if group.cost < overhead:
            break
        parts: list[_Group] = []
        for child in _children(group.prefix, group.members):
            settled = settle(*child)
            if settled is None:
                break
            parts.extend(settled)
        else:
            groups.remove(group)
            groups.extend(parts)
            finish = _makespan([g.cost for g in groups], workers, overhead)
            if finish < best_time - 1e-9:
                best, best_time = list(groups), finish
            continue
        group.splittable = False

    targets = [Target(g.path, g.members, g.cost) for g in best]
    targets.sort(key=lambda t: t.cost, reverse=True)
    return targets


@dataclass
class _Group:
    """A group of inputs while planning"""

    prefix: str
    path: str
    members: list[str]
    cost: float
    splittable: bool


def _children(prefix: str, members: Sequence[str]) -> list[tuple[str, list[str]]]:
    """Split inputs sharing a prefix on the character after it"""
    children: dict[str, list[str]] = {}
    for member in members:
        # An input that is the prefix itself goes on its own
        key = member if len(member) == len(prefix) else prefix + member[len(prefix)]
        children.setdefault(key, []).append(member)
    return list(children.items())


def _makespan(costs: Iterable[float], workers: int, overhead: float) -> float:
    """Return when workers taking the largest group first would finish"""
    loads = [0.0] * workers
    for cost in sorted(costs, reverse=True):
        heapq.heapreplace(loads, loads[0] + cost + overhead)
    return max(loads)


def target_overhead(n_inputs: int) -> float:
    """Estimate the seconds each Quarto process adds, for a project of this size"""
    return TARGET_OVERHEAD + OVERHEAD_PER_INPUT * max(n_inputs - 400, 0)


def estimate_costs(
    inputs: Sequence[str],
    timings: Mapping[str, float],
    executable: Mapping[str, int],
) -> dict[str, float]:
    """
    Estimate how long each input takes to render

    Parameters
    ----------
    inputs
        The project's inputs.
    timings
        Seconds each page took in the last build, where known.
    executable
        The number of executable code cells in each input.

    Returns
    -------
    :
        Estimated seconds for each input.
    """
    plain = [timings[i] for i in inputs if i in timings and not executable.get(i)]
    base = median(plain) if plain else DEFAULT_PAGE_COST
    costs: dict[str, float] = {}
    for item in inputs:
        if item in timings:
            costs[item] = max(timings[item], 0.01)
        elif executable.get(item):
            costs[item] = base + EXEC_PAGE_COST + 0.2 * executable[item]
        else:
            costs[item] = base
    return costs


def read_timings(*paths: Path) -> dict[str, float]:
    """Read the page timings of the last build from the first `build-timings.json` found"""
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pages = data.get("pages") if isinstance(data, dict) else None
        if not isinstance(pages, list):
            continue
        return {
            str(p["page"]): float(p["seconds"])
            for p in pages
            if isinstance(p, dict) and "page" in p and isinstance(p.get("seconds"), (int, float))
        }
    return {}


# ── The project ──────────────────────────────────────────────────────────────


@dataclass
class _Project:
    """What `quarto inspect` says about a project"""

    inputs: list[str]
    executable: dict[str, int]
    listing_dirs: set[str]
    page_freeze: set[str]
    problems: list[str] = field(default_factory=list[str])


def _inspect(build_dir: Path, env: Mapping[str, str]) -> _Project:
    result = subprocess.run(
        ["quarto", "inspect"],
        cwd=build_dir,
        env=dict(env),
        capture_output=True,
        **TEXT_MODE_KWARGS,
    )
    if result.returncode != 0:
        raise RuntimeError("quarto inspect failed: " + result.stderr.strip()[-2000:])
    data = json.loads(result.stdout)
    root = Path(os.path.realpath(build_dir))
    inputs: list[str] = []
    for item in data["files"]["input"]:
        path = Path(os.path.realpath(item))
        inputs.append(path.relative_to(root).as_posix())

    project = _Project(inputs=inputs, executable={}, listing_dirs=set(), page_freeze=set())
    info: dict[str, Any] = data.get("fileInformation") or {}
    dir_freezes = _dir_freeze_checker(build_dir)
    for rel in inputs:
        entry = info.get(rel) or {}
        cells = entry.get("codeCells") or []
        n_exec = sum(1 for c in cells if not str(c.get("language", "")).startswith("="))
        if n_exec:
            project.executable[rel] = n_exec
        meta = entry.get("metadata") or {}
        # `quarto inspect` gives only the page's own front matter, so the
        # `_metadata.yml` files of the directories above it are read here
        if _sets_freeze(meta) or dir_freezes(PurePosixPath(rel).parent):
            project.page_freeze.add(rel)
        if meta.get("listing") is not None:
            directory = str(PurePosixPath(rel).parent)
            project.listing_dirs.add("" if directory == "." else directory)
            for contents in _listing_contents(meta["listing"]):
                if contents.startswith(("/", "../")) or "/../" in contents:
                    project.problems.append(f"{rel} lists pages outside its directory")
        if any(ch in _GLOB_CHARS for ch in rel):
            project.problems.append(f"{rel} has a glob character in its path")
    return project


def _sets_freeze(meta: Any) -> bool:
    """Whether page or directory metadata says anything about freezing"""
    if not isinstance(meta, dict):
        return False
    execute = meta.get("execute")
    return "freeze" in meta or (isinstance(execute, dict) and "freeze" in execute)


def _dir_freeze_checker(build_dir: Path) -> Callable[[PurePosixPath], bool]:
    """
    Return a check that a directory's metadata files, or its parents', set `freeze`

    Any mention of `freeze` counts, even `freeze: false`: keeping a page's
    frozen results when they won't be used costs nothing, while dropping
    them when they would be makes the page run its code again.
    """
    cache: dict[PurePosixPath, bool] = {}

    def freezes(directory: PurePosixPath) -> bool:
        if directory in cache:
            return cache[directory]
        found = False
        for name in ("_metadata.yml", "_metadata.yaml"):
            path = build_dir / directory / name
            if not path.is_file():
                continue
            try:
                found = _sets_freeze(parse_yaml(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                # Quarto will report the file; keep its pages' results meanwhile
                found = True
            if found:
                break
        if not found and directory != directory.parent:
            found = freezes(directory.parent)
        cache[directory] = found
        return found

    return freezes


def _listing_contents(listing: Any) -> Iterable[str]:
    listings = listing if isinstance(listing, list) else [listing]
    for item in listings:
        if not isinstance(item, dict):
            continue
        contents = item.get("contents")
        for entry in contents if isinstance(contents, list) else [contents]:
            if isinstance(entry, str):
                yield entry.strip()


def _name_checker(build_dir: Path) -> Callable[[str], bool]:
    """Return a check that a path can name a group's directory"""

    def can_name(path: str) -> bool:
        if not path or any(ch in _GLOB_CHARS for ch in path):
            return False
        target = build_dir / path
        parent, name = target.parent, target.name
        if name.startswith((".", "_")):
            return False
        try:
            siblings = os.listdir(parent)
        except OSError:
            return False
        if name in siblings:
            return target.is_dir() and not target.is_symlink()
        # A file or directory with the same name in another case, on a
        # case-insensitive file system
        folded = name.casefold()
        return not any(s.casefold() == folded for s in siblings)

    return can_name


def _project_config(build_dir: Path) -> tuple[str, dict[str, Any]]:
    text = (build_dir / "_quarto.yml").read_text(encoding="utf-8")
    return text, dict(parse_yaml(text) or {})


def _scripts(config: Mapping[str, Any], key: str) -> list[str]:
    value = (config.get("project") or {}).get(key)
    if value is None:
        return []
    return [str(v) for v in (value if isinstance(value, list) else [value])]


def _project_freezes(config: Mapping[str, Any]) -> bool:
    execute = config.get("execute")
    freeze = execute.get("freeze") if isinstance(execute, dict) else None
    return freeze not in (None, False)


def _run_scripts(
    build_dir: Path, scripts: Sequence[str], env: Mapping[str, str]
) -> tuple[bool, str]:
    """Run project scripts the way Quarto does, returning success and their output"""
    output: list[str] = []
    for entry in scripts:
        args = shlex.split(entry)
        if not args:
            continue
        script = args[0]
        suffix = PurePosixPath(script).suffix.lower()
        if suffix == ".py":
            cmd = [env.get("QUARTO_PYTHON") or sys.executable, *args]
        elif suffix in (".ts", ".lua", ".r"):
            cmd = ["quarto", "run", *args]
        else:
            cmd = args
        result = subprocess.run(
            cmd, cwd=build_dir, env=dict(env), capture_output=True, **TEXT_MODE_KWARGS
        )
        output.append(result.stdout + result.stderr)
        if result.returncode != 0:
            return False, f"Script '{script}' failed:\n" + "".join(output)
    return True, "".join(output)


# ── Workers ──────────────────────────────────────────────────────────────────


def worker_dir(build_dir: Path, slot: int | str) -> Path:
    """
    Return where a worker's copy of a project goes

    The copies sit beside the project, so files can be cloned, and aren't
    hidden: Quarto expands no globs (in sidebars or listings, say) in a
    project inside a hidden directory.
    """
    return build_dir.parent / f"_{build_dir.name}{WORKER_TAG}{slot}"


def worker_dirs(build_dir: Path) -> list[Path]:
    """Return the worker copies of a project left in place, such as by a crash"""
    prefix = worker_dir(build_dir, "").name
    try:
        return sorted(
            p for p in build_dir.parent.iterdir() if p.name.startswith(prefix) and p.is_dir()
        )
    except OSError:
        return []


def _clone(entries: Sequence[Path], dest: Path) -> None:
    """
    Copy files and directories into a directory, keeping their times

    Quarto trusts its cache of a page's metadata while the page is older than
    the cache, so the copies keep the originals' modification times. Files
    are cloned where the file system can.
    """
    if not entries:
        return
    dest.mkdir(parents=True, exist_ok=True)
    sources = [str(entry) for entry in entries]
    if sys.platform == "darwin":
        cmd = ["cp", "-cRp", *sources, str(dest)]
    elif sys.platform.startswith("linux"):
        cmd = ["cp", "-R", "--reflink=auto", "--preserve=timestamps", *sources, str(dest)]
    else:
        cmd = None
    if cmd is not None and subprocess.run(cmd, capture_output=True).returncode == 0:
        return
    for entry in entries:
        target = dest / entry.name
        if entry.is_dir() and not entry.is_symlink():
            shutil.copytree(entry, target, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target, follow_symlinks=False)


def _copy_project(build_dir: Path, dest: Path) -> None:
    """Copy a project for a worker"""
    dest.mkdir()
    _clone([p for p in build_dir.iterdir() if p.name not in _SKIP_COPY], dest)

    # Workers leave the project's scripts to the parallel render
    text, config = _project_config(dest)
    project = config.get("project") or {}
    project.pop("pre-render", None)
    project.pop("post-render", None)
    _slim_config(config, dest)
    with open(dest / "_quarto.yml", "w", encoding="utf-8") as f:
        if text.startswith(QUARTO_YML_HEADER):
            f.write(QUARTO_YML_HEADER)
        write_yaml(config, f)


def _slim_config(config: dict[str, Any], dest: Path) -> None:
    """
    Make a worker's `_quarto.yml` quicker for Quarto to read

    For each input, Quarto checks every string in the project config outside
    `project` and `website` as a possible path, and parses `_quarto.yml`
    again to compare formats, so both get slow as a site grows. Great Docs'
    own keys go, since Quarto doesn't use them, and the sidebars move to a
    metadata file, which Quarto merges into the config once.
    """
    for key in _NOT_FOR_QUARTO:
        config.pop(key, None)
    website = config.get("website")
    if (
        isinstance(website, dict)
        and website.get("sidebar")
        and "metadata-files" not in config
        and "metadata-file" not in config
        and not (dest / _SIDEBAR_META).exists()
    ):
        with open(dest / _SIDEBAR_META, "w", encoding="utf-8") as f:
            write_yaml({"website": {"sidebar": website.pop("sidebar")}}, f)
        config["metadata-files"] = [_SIDEBAR_META]


@dataclass
class _Outcome:
    """What a worker's render of one target produced"""

    returncode: int
    stderr: str
    pages: list[tuple[str, float]]
    warnings: list[str]
    started: float
    seconds: float
    startup: float
    """Seconds before Quarto started on the first page"""


class _Runner:
    """Render targets from a queue in worker copies of a project"""

    def __init__(
        self,
        build_dir: Path,
        targets: list[Target],
        workers: int,
        env: Mapping[str, str],
        freezes: bool,
        page_freeze: set[str],
        on_page: Callable[[str], None] | None,
        overhead: float = TARGET_OVERHEAD,
    ):
        self.build_dir = build_dir
        self.overhead = overhead
        self.targets = targets
        self.env = dict(env)
        self.freezes = freezes
        self.page_freeze = page_freeze
        self.on_page = on_page
        self.queue: queue.Queue[Target] = queue.Queue()
        for target in targets:
            self.queue.put(target)
        self.dirs = [worker_dir(build_dir, slot) for slot in range(workers)]
        self.done: dict[int, list[tuple[Target, _Outcome]]] = {s: [] for s in range(workers)}
        self.failure: tuple[Target, _Outcome] | None = None
        self.error: BaseException | None = None
        self.stop = threading.Event()
        self.warm = threading.Event()
        self._lock = threading.Lock()
        self._procs: dict[int, subprocess.Popen[str]] = {}

    def run(self) -> None:
        threads = [
            threading.Thread(target=self._work, args=(slot,), daemon=True)
            for slot in range(len(self.dirs))
        ]
        for thread in threads:
            thread.start()
        try:
            for thread in threads:
                while thread.is_alive():
                    thread.join(0.2)
        except BaseException:
            self.stop.set()
            self.kill()
            raise

    def kill(self) -> None:
        with self._lock:
            procs = list(self._procs.values())
        for proc in procs:
            _kill(proc)

    def _work(self, slot: int) -> None:
        directory = self.dirs[slot]
        try:
            if self.stop.is_set():
                return
            _copy_project(self.build_dir, directory)
            if not self.freezes:
                self._thaw_nothing(directory)
            # Quarto reads every page's metadata before rendering any, caching
            # it in `.quarto/idx`, so the first worker does that for the rest
            if slot > 0:
                while not self.warm.wait(0.1):
                    if self.stop.is_set():
                        return
                index = self.dirs[0] / ".quarto" / "idx"
                if index.is_dir():
                    _clone([index], directory / ".quarto")
            while not self.stop.is_set():
                try:
                    target = self.queue.get_nowait()
                except queue.Empty:
                    return
                outcome = self._render(slot, directory, target)
                if slot == 0:
                    self.warm.set()
                if outcome.returncode != 0 and any(
                    p in outcome.stderr for p in _TRANSIENT_PATTERNS
                ):
                    outcome = self._render(slot, directory, target)
                if self.stop.is_set():
                    return
                if outcome.returncode != 0:
                    with self._lock:
                        if self.failure is None:
                            self.failure = (target, outcome)
                    self.stop.set()
                    self.kill()
                    return
                self.done[slot].append((target, outcome))
        except BaseException as e:
            with self._lock:
                if self.error is None:
                    self.error = e
            self.stop.set()
            self.kill()
        finally:
            if slot == 0:
                self.warm.set()

    def _thaw_nothing(self, directory: Path) -> None:
        """
        Remove frozen results the full render wouldn't use

        A render of some pages only reads the freezer when asked to, and then
        thaws any page it finds there, so without project-wide freezing the
        entries of pages that don't ask for freezing go.
        """
        freeze = directory / "_freeze"
        if not freeze.is_dir():
            return
        for target in self.targets:
            for item in target.inputs:
                if item in self.page_freeze:
                    continue
                entry = freeze / PurePosixPath(item).with_suffix("")
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)

    def _render(self, slot: int, directory: Path, target: Target) -> _Outcome:
        if not target.single:
            (directory / target.path).mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        proc = subprocess.Popen(
            ["quarto", "render", target.path, "--use-freezer"],
            cwd=directory,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            start_new_session=os.name == "posix",
            **TEXT_MODE_KWARGS,
        )
        with self._lock:
            self._procs[slot] = proc
        pages: list[tuple[str, float]] = []
        warnings: list[str] = []
        stderr: list[str] = []

        def handle(line: str) -> None:
            plain = _ANSI_RE.sub("", line).strip()
            if not plain:
                return
            match = _PROGRESS_RE.search(plain)
            if match:
                page = match.group(3).strip()
                pages.append((page, time.monotonic()))
                if slot == 0:
                    self.warm.set()
                if self.on_page:
                    self.on_page(page)
            elif plain.startswith("WARN"):
                warnings.append(plain)

        def read_stderr() -> None:
            assert proc.stderr is not None
            for line in proc.stderr:
                stderr.append(line)
                handle(line)

        reader = threading.Thread(target=read_stderr, daemon=True)
        reader.start()
        assert proc.stdout is not None
        for line in proc.stdout:
            handle(line)
        proc.wait()
        reader.join(timeout=5)
        with self._lock:
            self._procs.pop(slot, None)
        ended = time.monotonic()

        timings: list[tuple[str, float]] = []
        if target.single and proc.returncode == 0:
            timings.append((target.path, max(ended - started - self.overhead, 0.05)))
            if self.on_page:
                self.on_page(target.path)
        else:
            for i, (page, stamp) in enumerate(pages):
                end = pages[i + 1][1] if i + 1 < len(pages) else ended
                timings.append((page, end - stamp))
        startup = (pages[0][1] if pages else ended) - started
        return _Outcome(
            proc.returncode, "".join(stderr), timings, warnings, started, ended - started, startup
        )

    def write_trace(self, path: Path, origin: float) -> None:
        """Write when and how long each worker rendered each target, for tuning"""
        rows = [
            {
                "worker": slot,
                "target": target.path,
                "pages": len(target.inputs),
                "estimate": round(target.cost, 2),
                "start": round(outcome.started - origin, 2),
                "seconds": round(outcome.seconds, 2),
                "startup": round(outcome.startup, 2),
            }
            for slot, results in self.done.items()
            for target, outcome in results
        ]
        path.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")

    def cleanup(self) -> None:
        for directory in self.dirs:
            if directory.exists():
                shutil.rmtree(directory, ignore_errors=True)


def _kill(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
    except (OSError, ProcessLookupError):
        pass


# ── Merging ──────────────────────────────────────────────────────────────────


def _owner_of(rel: str, owners: Mapping[str, int]) -> int | None:
    """
    Return the worker that rendered the page an output belongs to

    A page `a/b.qmd` writes `a/b.html` and files such as `a/b.md` next to it,
    and its figures and libraries go to `a/b_files/`.
    """
    path = PurePosixPath(rel)
    parent = path.parent
    name = path.name
    while "." in name:
        name = name.rsplit(".", 1)[0]
        stem = str(parent / name) if str(parent) != "." else name
        if stem in owners:
            return owners[stem]
    return None


def merge_sites(
    sources: Sequence[Path],
    dest: Path,
    owners: Mapping[str, int],
) -> None:
    """
    Move the outputs of the workers into one output directory

    A page's outputs come from the worker that rendered it. Anything else,
    such as resources and site libraries, comes from the first worker that
    has it, apart from the search index, sitemap and listing index, which are
    merged.

    Parameters
    ----------
    sources
        The output directories of the workers, by worker number.
    dest
        The output directory to fill, which must not exist yet.
    owners
        The worker number of each rendered input, by the input's path without
        its suffix.
    """
    dest.mkdir(parents=True)
    for slot, source in enumerate(sources):
        if source.is_dir():
            _move_tree(source, dest, "", slot, owners)


def _move_tree(source: Path, dest: Path, rel: str, slot: int, owners: Mapping[str, int]) -> None:
    for entry in os.scandir(source):
        entry_rel = rel + entry.name
        target = dest / entry.name
        if not rel and entry.name in (_SEARCH, _SITEMAP, _LISTINGS):
            continue
        if entry.is_dir(follow_symlinks=False):
            if entry.name.endswith("_files") and entry_rel[: -len("_files")] in owners:
                owner = owners[entry_rel[: -len("_files")]]
                if owner == slot:
                    if target.exists():
                        shutil.rmtree(target)
                    os.replace(entry.path, target)
                elif not target.exists():
                    os.replace(entry.path, target)
            elif not target.exists():
                os.replace(entry.path, target)
            elif target.is_dir():
                _move_tree(Path(entry.path), target, entry_rel + "/", slot, owners)
        else:
            if not target.exists() or _owner_of(entry_rel, owners) == slot:
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                os.replace(entry.path, target)


def merge_search(
    indexes: Sequence[list[dict[str, Any]]],
    page_order: Mapping[str, int],
    owners_by_page: Mapping[str, int],
) -> list[dict[str, Any]]:
    """
    Merge the workers' search indexes, in the order a full render writes them

    Parameters
    ----------
    indexes
        Each worker's search entries.
    page_order
        The position of each output page in the project's inputs.
    owners_by_page
        The worker number that rendered each output page.

    Returns
    -------
    :
        The entries, each page's from the worker that rendered it.
    """
    chosen: dict[str, tuple[int, int, dict[str, Any]]] = {}
    position = 0
    for slot, entries in enumerate(indexes):
        for entry in entries:
            href = str(entry.get("href", ""))
            page = href.split("#", 1)[0]
            owner = owners_by_page.get(page)
            previous = chosen.get(href)
            if previous is None or (owner == slot and previous[0] != slot):
                chosen[href] = (slot, position, entry)
            position += 1
    big = len(page_order)

    def key(item: tuple[str, tuple[int, int, dict[str, Any]]]) -> tuple[int, int]:
        href, (_, pos, _) = item
        return page_order.get(href.split("#", 1)[0], big), pos

    return [entry for _, (_, _, entry) in sorted(chosen.items(), key=key)]


def merge_sitemaps(texts: Sequence[str]) -> str | None:
    """Merge the workers' sitemaps, keeping the first `<url>` for each location"""
    texts = [t for t in texts if t]
    if not texts:
        return None
    seen: dict[str, str] = {}
    for text in texts:
        for block in _URL_RE.findall(text):
            loc = _LOC_RE.search(block)
            seen.setdefault(loc.group(1) if loc else block, block)
    first = texts[0]
    if not seen or "</url>" not in first:
        return first
    head = first[: first.find("<url>")]
    tail = first[first.rfind("</url>") + len("</url>") :]
    body = "\n".join(f"  {block}" for block in seen.values())
    return head.rstrip() + "\n" + body + "\n" + tail.lstrip("\n")


def _merge_listings(paths: Sequence[Path]) -> list[Any] | None:
    merged: list[Any] = []
    keys: set[str] = set()
    found = False
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        found = True
        for item in data if isinstance(data, list) else []:
            key = json.dumps(item.get("listing") if isinstance(item, dict) else item)
            if key not in keys:
                keys.add(key)
                merged.append(item)
    return merged if found else None


def _merge_freeze(
    sources: Sequence[Path],
    dest: Path,
    owned: Mapping[int, Iterable[str]],
    keep: Callable[[str], bool],
) -> None:
    """Copy the frozen results of each worker's pages back to the project"""
    for slot, source in enumerate(sources):
        if not source.is_dir():
            continue
        for item in owned.get(slot, ()):
            if not keep(item):
                continue
            stem = PurePosixPath(item).with_suffix("")
            entry = source / stem
            if entry.is_dir():
                target = dest / stem
                if target.exists():
                    shutil.rmtree(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(entry, target)
        libs = source / "site_libs"
        if libs.is_dir():
            _copy_missing(libs, dest / "site_libs")


def _copy_missing(source: Path, dest: Path) -> None:
    for root, _, files in os.walk(source):
        rel = Path(root).relative_to(source)
        for name in files:
            target = dest / rel / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(root) / name, target)


# ── Rendering ────────────────────────────────────────────────────────────────


@dataclass
class RenderResult:
    """The outcome of a parallel render, shaped like the ordinary render's"""

    returncode: int = 0
    stderr: str = ""
    stdout: str = ""
    page_timings: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    warnings: list[str] = field(default_factory=list[str])
    fallback: str | None = None
    """Why the site should be rendered the ordinary way instead, if it should"""
    targets: int = 0
    workers: int = 0
    pages: int = 0


def render(
    build_dir: Path,
    env: Mapping[str, str],
    jobs: int,
    timings: Mapping[str, float] | None = None,
    on_start: Callable[[int, int, int], None] | None = None,
    on_page: Callable[[str], None] | None = None,
    min_pages: int = MIN_PAGES,
) -> RenderResult:
    """
    Render a Quarto website with several processes

    Parameters
    ----------
    build_dir
        The Quarto project directory.
    env
        The environment for Quarto.
    jobs
        The most processes to run at once.
    timings
        Seconds each page took in the last build, which guide the split.
    on_start
        Called with the number of pages, groups and processes once the render
        is planned.
    on_page
        Called with each input as Quarto starts rendering it (or, for a group
        of one page, once it is done). Called from several threads.
    min_pages
        Sites with fewer pages aren't split.

    Returns
    -------
    :
        The result. When `fallback` is set, nothing was rendered (or what was
        has been discarded) and the site should be rendered the ordinary way.
    """
    for leftover in worker_dirs(build_dir):
        shutil.rmtree(leftover, ignore_errors=True)
    if jobs < 2:
        return RenderResult(fallback="one render process requested")

    text, config = _project_config(build_dir)
    project_type = (config.get("project") or {}).get("type")
    if project_type != "website":
        return RenderResult(fallback=f"project type is {project_type!r}, not a website")
    output_dir = str((config.get("project") or {}).get("output-dir") or "_site")
    if PurePosixPath(output_dir).is_absolute() or ".." in PurePosixPath(output_dir).parts:
        return RenderResult(fallback=f"output directory {output_dir!r} is outside the project")
    pre_render = _scripts(config, "pre-render")
    post_render = _scripts(config, "post-render")

    try:
        project = _inspect(build_dir, env)
    except (RuntimeError, ValueError, KeyError, OSError) as e:
        return RenderResult(fallback=f"couldn't inspect the project ({e})")
    if len(project.inputs) < min_pages:
        return RenderResult(fallback=f"only {len(project.inputs)} pages")
    if project.problems:
        return RenderResult(fallback=project.problems[0])
    if "" in project.listing_dirs:
        return RenderResult(fallback="a listing page at the top of the site")

    script_env = {
        **env,
        "QUARTO_PROJECT_OUTPUT_DIR": output_dir,
        "QUARTO_PROJECT_RENDER_ALL": "1",
        "QUARTO_PROJECT_SCRIPT_PROGRESS": "0",
        "QUARTO_PROJECT_SCRIPT_QUIET": "1",
    }
    if pre_render:
        ok, output = _run_scripts(
            build_dir,
            pre_render,
            {**script_env, "QUARTO_PROJECT_INPUT_FILES": "\n".join(project.inputs)},
        )
        if not ok:
            return RenderResult(returncode=1, stderr=output)
        if any(script not in _KNOWN_PRE_RENDER for script in pre_render):
            try:
                project = _inspect(build_dir, env)
            except (RuntimeError, ValueError, KeyError, OSError) as e:
                return RenderResult(fallback=f"couldn't inspect the project ({e})")
            if project.problems or "" in project.listing_dirs:
                return RenderResult(fallback="the pre-render scripts changed the project")

    costs = estimate_costs(project.inputs, timings or {}, project.executable)
    overhead = target_overhead(len(project.inputs))
    targets = plan_targets(
        project.inputs, costs, jobs, project.listing_dirs, _name_checker(build_dir), overhead
    )
    if not targets or len(targets) < 2:
        return RenderResult(fallback="the pages can't be split")
    workers = min(jobs, len(targets))
    if on_start:
        on_start(len(project.inputs), len(targets), workers)

    freezes = _project_freezes(config)
    runner = _Runner(
        build_dir, targets, workers, env, freezes, project.page_freeze, on_page, overhead
    )
    origin = time.monotonic()
    try:
        runner.run()
        if os.environ.get(TRACE_ENV):
            runner.write_trace(Path(os.environ[TRACE_ENV]), origin)
        if runner.error is not None:
            return RenderResult(fallback=f"a worker failed ({runner.error!r})")
        if runner.failure is not None:
            target, outcome = runner.failure
            return RenderResult(
                returncode=outcome.returncode or 1,
                stderr=f"Rendering {target.path} failed:\n{outcome.stderr}",
                warnings=outcome.warnings,
            )

        try:
            return _finish(build_dir, output_dir, project, runner, freezes, post_render, script_env)
        except (OSError, ValueError) as e:
            return RenderResult(fallback=f"couldn't merge the outputs ({e})")
    finally:
        runner.kill()
        runner.cleanup()


def _finish(
    build_dir: Path,
    output_dir: str,
    project: _Project,
    runner: _Runner,
    freezes: bool,
    post_render: Sequence[str],
    script_env: Mapping[str, str],
) -> RenderResult:
    """Check and merge what the workers rendered, then run the post-render scripts"""
    owners: dict[str, int] = {}
    owned: dict[int, list[str]] = {}
    page_timings: list[dict[str, Any]] = []
    warnings: list[str] = []
    for slot, results in runner.done.items():
        for target, outcome in results:
            # Quarto must have rendered just what the target's prefix selected
            rendered = {page for page, _ in outcome.pages}
            missing = [item for item in target.inputs if item not in rendered]
            if missing:
                return RenderResult(fallback=f"Quarto didn't render {missing[0]} for {target.path}")
            for item in target.inputs:
                owners[str(PurePosixPath(item).with_suffix(""))] = slot
                owned.setdefault(slot, []).append(item)
            page_timings.extend(
                {"page": page, "seconds": round(seconds, 3)}
                for page, seconds in outcome.pages
                if page in target.inputs
            )
            warnings.extend(outcome.warnings)
    if {item for items in owned.values() for item in items} != set(project.inputs):
        return RenderResult(fallback="some pages weren't rendered")

    sources = [d / output_dir for d in runner.dirs]
    site = build_dir / output_dir
    if site.exists():
        shutil.rmtree(site)
    merge_sites(sources, site, owners)

    order = {_output(item): n for n, item in enumerate(project.inputs)}
    by_page = {_output(item): slot for slot, items in owned.items() for item in items}
    indexes: list[list[dict[str, Any]]] = []
    for source in sources:
        try:
            data = json.loads((source / _SEARCH).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = []
        indexes.append(data if isinstance(data, list) else [])
    if any(indexes):
        entries = merge_search(indexes, order, by_page)
        (site / _SEARCH).write_text(
            json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    sitemap = merge_sitemaps([_read(source / _SITEMAP) for source in sources])
    if sitemap is not None:
        (site / _SITEMAP).write_text(sitemap, encoding="utf-8")
    listings = _merge_listings([source / _LISTINGS for source in sources])
    if listings is not None:
        (site / _LISTINGS).write_text(json.dumps(listings, indent=2), encoding="utf-8")

    # Without project-wide freezing, only pages that ask for it keep results
    _merge_freeze(
        [d / "_freeze" for d in runner.dirs],
        build_dir / "_freeze",
        owned,
        keep=(lambda item: True) if freezes else project.page_freeze.__contains__,
    )

    output = ""
    if post_render:
        outputs = "\n".join(str(PurePosixPath(output_dir, _output(i))) for i in project.inputs)
        ok, output = _run_scripts(
            build_dir, post_render, {**script_env, "QUARTO_PROJECT_OUTPUT_FILES": outputs}
        )
        if not ok:
            return RenderResult(returncode=1, stderr=output)

    return RenderResult(
        stdout=output,
        page_timings=page_timings,
        warnings=warnings,
        targets=len(runner.targets),
        workers=len(runner.dirs),
        pages=len(project.inputs),
    )


def _output(item: str) -> str:
    return str(PurePosixPath(item).with_suffix(".html"))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
