"""
Checkouts and controlled build environments for harness comparisons

A side is a checkout with its own virtual environment. The base side is a detached worktree
of the base commit, kept in the cache directory with a virtual environment synced from the
test checkout's `uv.lock`. Each build command uses the same environment settings: a stub
`quarto` first on `PATH`, the side's `bin` directory next, a failing HTTP proxy, a fixed hash
seed and the census observer on `PYTHONPATH`.
"""

from __future__ import annotations

import fcntl
import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Report the minimum supported Quarto version so builds pass the normal version check.
STUB_QUARTO_VERSION = "1.9.18"

# Fail proxied GitHub and PyPI requests consistently, regardless of network availability.
DEAD_PROXY = "http://127.0.0.1:9"

# Variables passed through from the harness's environment, besides `LC_*`.
INHERITED_VARIABLES = ("HOME", "USER", "LOGNAME", "LANG", "TMPDIR", "TERM")

# Read by the observer and by the stub `quarto`, which import nothing from the harness.
CENSUS_VARIABLE = "GREAT_DOCS_HARNESS_CENSUS"
QUARTO_LOG_VARIABLE = "GREAT_DOCS_HARNESS_QUARTO_LOG"
RENDER_PAGES_VARIABLE = "GREAT_DOCS_HARNESS_RENDER_PAGES"

OBSERVER_SOURCE = Path(__file__).resolve().parent / "observer" / "sitecustomize.py"

_STUB_TEMPLATE = """\
#!/bin/sh
# Quarto stand-in written by the great-docs characterisation harness. `render` and `preview`
# succeed without output; every other subcommand runs the real Quarto. When ${pages} is
# set, `render` writes a placeholder `_site/` page for each page that Quarto would render.
if [ -n "${log}" ]; then
  printf '%s\\n' "$*" >> "${log}"
fi
case "$1" in
  --version) echo "{version}"; exit 0 ;;
  render)
    if [ -n "${pages}" ]; then
      find . -name '*.qmd' ! -path '*/_*' | while IFS= read -r page; do
        target="_site/${{page#./}}"
        target="${{target%.qmd}}.html"
        mkdir -p "${{target%/*}}"
        printf '<html><body>%s</body></html>\\n' "${{page#./}}" > "$target"
      done
    fi
    exit 0 ;;
  preview) exit 0 ;;
esac
exec {real} "$@"
"""


class HarnessError(RuntimeError):
    """An unmet requirement that prevents a harness run or recording"""


@dataclass(frozen=True)
class Side:
    """
    A checkout and the virtual environment that builds it

    Attributes
    ----------
    label :
        `base` or `test`; names the recording directory.
    checkout :
        Root of the checkout.
    venv :
        Its virtual environment.
    facts :
        Recorded commit, interpreter, tool versions and installed distributions.
    """

    label: str
    checkout: Path
    venv: Path
    facts: Mapping[str, Any] = field(default_factory=dict[str, Any])

    @property
    def bin(self) -> Path:
        """Directory of the environment's executables"""
        return self.venv / "bin"

    @property
    def great_docs_dir(self) -> Path:
        """Source directory of the `great_docs` package in the checkout"""
        return self.checkout / "great_docs"


def run_checked(argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None) -> str:
    """
    Run a helper command and return its standard output

    Parameters
    ----------
    argv :
        Command and arguments.
    cwd :
        Working directory.
    env :
        Environment; the harness's own when `None`.

    Returns
    -------
    :
        Standard output with surrounding whitespace removed.

    Raises
    ------
    HarnessError
        If the command cannot start or exits non-zero.
    """
    try:
        proc = subprocess.run(
            list(argv),
            cwd=cwd,
            env=None if env is None else dict(env),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise HarnessError(f"Cannot run {shlex.join(argv)}: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip()[-2000:]
        raise HarnessError(f"{shlex.join(argv)} exited {proc.returncode}:\n{tail}")
    return proc.stdout.strip()


def harness_checkout() -> Path:
    """
    Locate the checkout that holds this harness

    Returns
    -------
    :
        Its root directory.
    """
    return Path(__file__).resolve().parents[2]


def checkout_side(checkout: Path) -> Side:
    """
    Describe a checkout that already has a virtual environment

    Parameters
    ----------
    checkout :
        Root of the checkout; its `.venv` must hold `great-docs`.

    Returns
    -------
    :
        The side, labelled `test`, without facts.

    Raises
    ------
    HarnessError
        If the checkout has no `.venv/bin/great-docs`.
    """
    checkout = checkout.resolve()
    venv = checkout / ".venv"
    if not (venv / "bin" / "great-docs").exists():
        raise HarnessError(
            f"{checkout} has no .venv/bin/great-docs; run "
            "`env -u VIRTUAL_ENV uv sync --extra dev --frozen` there first"
        )
    return Side("test", checkout, venv)


def base_side(checkout: Path, ref: str, cache: Path, python_version: str) -> Side:
    """
    Prepare a clean worktree of a base commit with its own virtual environment

    The worktree lives in `cache/worktrees/<sha>` and is reused by later runs against the
    same commit; a lock file serialises its preparation between concurrent runs. The
    environment is synced from the checkout's `uv.lock` with the given interpreter.

    Parameters
    ----------
    checkout :
        The checkout under test; supplies the repository and `uv.lock`.
    ref :
        Base revision, for example `main`.
    cache :
        The harness cache directory.
    python_version :
        Interpreter version for the environment, matching the test side.

    Returns
    -------
    :
        The side, labelled `base`, without facts.

    Raises
    ------
    HarnessError
        If the revision is unknown, `uv.lock` or `uv` is missing, the worktree has local
        changes, or the sync fails.
    """
    sha = run_checked(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], checkout)
    lock_file = checkout / "uv.lock"
    if not lock_file.is_file():
        raise HarnessError(f"{checkout} has no uv.lock to copy into the base worktree")
    uv = shutil.which("uv")
    if uv is None:
        raise HarnessError("`uv` is not on PATH; the base worktree needs it")
    worktrees = cache / "worktrees"
    worktrees.mkdir(parents=True, exist_ok=True)
    tree = worktrees / sha[:12]
    with (worktrees / f"{sha[:12]}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not tree.exists():
            _ = run_checked(
                ["git", "worktree", "add", "--force", "--detach", str(tree), sha], checkout
            )
        if run_checked(["git", "rev-parse", "HEAD"], tree) != sha:
            raise HarnessError(f"{tree} is not at {sha}; remove it with `git worktree remove`")
        if run_checked(["git", "status", "--porcelain"], tree):
            raise HarnessError(f"{tree} has local changes; remove it with `git worktree remove`")
        _ = shutil.copyfile(lock_file, tree / "uv.lock")
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
        _ = run_checked(
            [uv, "sync", "--extra", "dev", "--frozen", "--python", python_version, "--quiet"],
            tree,
            env,
        )
    return Side("base", tree, tree / ".venv")


def write_stub(directory: Path, real_quarto: str) -> Path:
    """
    Write the stub `quarto` executable

    Parameters
    ----------
    directory :
        Directory that will be first on the build's `PATH`.
    real_quarto :
        Path of the real Quarto, which runs every subcommand except `render`, `preview`
        and `--version`.

    Returns
    -------
    :
        The stub's path.
    """
    directory.mkdir(parents=True, exist_ok=True)
    stub = directory / "quarto"
    _ = stub.write_text(
        _STUB_TEMPLATE.format(
            log=QUARTO_LOG_VARIABLE,
            pages=RENDER_PAGES_VARIABLE,
            version=STUB_QUARTO_VERSION,
            real=shlex.quote(real_quarto),
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def install_observer(directory: Path) -> Path:
    """
    Copy the census observer into a directory of its own for `PYTHONPATH`

    The copy keeps every other module of the harness off the build's import path.

    Parameters
    ----------
    directory :
        Destination directory.

    Returns
    -------
    :
        The directory.
    """
    directory.mkdir(parents=True, exist_ok=True)
    _ = shutil.copyfile(OBSERVER_SOURCE, directory / "sitecustomize.py")
    return directory


def search_path(side: Side, stub_dir: Path) -> str:
    """
    Compose the `PATH` of a side's commands

    Parameters
    ----------
    side :
        The side whose environment comes second.
    stub_dir :
        Directory of the stub `quarto`, which comes first.

    Returns
    -------
    :
        The search path, ending with the harness's own `PATH`.
    """
    return os.pathsep.join([str(stub_dir), str(side.bin), os.environ.get("PATH", "")])


def child_environment(side: Side, stub_dir: Path, observer_dir: Path) -> dict[str, str]:
    """
    Compose the environment shared by every command a side runs

    Only an allowlist of the harness's variables passes through, so tokens, coverage and
    virtual-environment settings of the caller do not reach the build.

    Parameters
    ----------
    side :
        The side to build with.
    stub_dir :
        Directory of the stub `quarto`.
    observer_dir :
        Directory of the census observer, which goes last on `PYTHONPATH`.

    Returns
    -------
    :
        The environment without the per-package `PYTHONPATH` entries and per-command
        variables, which the recorder adds.
    """
    env = {k: v for k, v in os.environ.items() if k in INHERITED_VARIABLES or k.startswith("LC_")}
    env.update(
        PATH=search_path(side, stub_dir),
        PYTHONPATH=str(observer_dir),
        PYTHONHASHSEED="0",
        PYTHONIOENCODING="utf-8",
        HTTPS_PROXY=DEAD_PROXY,
        HTTP_PROXY=DEAD_PROXY,
        https_proxy=DEAD_PROXY,
        http_proxy=DEAD_PROXY,
    )
    return env


def real_quarto() -> str:
    """
    Find the real Quarto on the harness's `PATH`

    Returns
    -------
    :
        Its path.

    Raises
    ------
    HarnessError
        If Quarto is missing; `quarto pandoc` converts some packages' README files.
    """
    found = shutil.which("quarto")
    if found is None:
        raise HarnessError("Quarto is not on PATH; the stub passes `quarto pandoc` to it")
    return found


_DISTRIBUTIONS = (
    "import importlib.metadata as m, json, platform, re; "
    "d = {re.sub(r'[-_.]+', '-', (x.metadata['Name'] or '').lower()): x.version "
    "for x in m.distributions()}; "
    "print(json.dumps({'python': platform.python_version(), 'distributions': d}))"
)


def describe(side: Side, stub_dir: Path) -> Side:
    """
    Record the facts a comparison depends on, refusing a side that lacks a required tool

    Parameters
    ----------
    side :
        The side to describe.
    stub_dir :
        Directory of the stub `quarto`, used to compose the side's `PATH`.

    Returns
    -------
    :
        The side with its facts: commit, local changes, interpreter, installed
        distributions, and the versions of `d2`, `ruff`, Git, the real Quarto and the stub.

    Raises
    ------
    HarnessError
        If `d2` or `ruff` is missing from the side's `PATH`, or the interpreter is older
        than 3.12.
    """
    path = search_path(side, stub_dir)
    versions: dict[str, str] = {}
    # Missing tools silently change output: `d2` diagrams remain as code fences and
    # signatures lack `ruff` formatting.
    for tool in ("d2", "ruff"):
        found = shutil.which(tool, path=path)
        if found is None:
            raise HarnessError(f"`{tool}` is not on the {side.label} side's PATH ({path})")
        versions[tool] = run_checked([found, "--version"], side.checkout)
    versions["quarto"] = run_checked([real_quarto(), "--version"], side.checkout)
    versions["git"] = run_checked(["git", "--version"], side.checkout)
    probe = json.loads(run_checked([str(side.bin / "python"), "-c", _DISTRIBUTIONS], side.checkout))
    python = str(probe["python"])
    if tuple(int(p) for p in python.split(".")[:2]) < (3, 12):
        raise HarnessError(f"The census needs Python 3.12 or later; {side.label} has {python}")
    distributions = {
        name: version for name, version in probe["distributions"].items() if name != "great-docs"
    }
    facts = {
        "checkout": str(side.checkout),
        "commit": run_checked(["git", "rev-parse", "HEAD"], side.checkout),
        "local_changes": bool(run_checked(["git", "status", "--porcelain"], side.checkout)),
        "python": python,
        "stub_quarto_version": STUB_QUARTO_VERSION,
        "tools": versions,
        "distributions": dict(sorted(distributions.items())),
    }
    return Side(side.label, side.checkout, side.venv, facts)


def python_version(side: Side) -> str:
    """
    Report the interpreter version of a side's environment

    Parameters
    ----------
    side :
        The side.

    Returns
    -------
    :
        The version, for example `3.13.11`.
    """
    return run_checked(
        [str(side.bin / "python"), "-c", "import platform; print(platform.python_version())"],
        side.checkout,
    )


def environment_differences(base: Mapping[str, Any], test: Mapping[str, Any]) -> list[str]:
    """
    List the facts that differ between two sides and would change build output

    Parameters
    ----------
    base, test :
        Facts of the two sides.

    Returns
    -------
    :
        One line per difference; empty when the environments agree.
    """
    lines: list[str] = []
    for key in ("python", "stub_quarto_version", "tools"):
        if base.get(key) != test.get(key):
            lines.append(f"{key}: {base.get(key)!r} != {test.get(key)!r}")
    base_dists: Mapping[str, str] = base.get("distributions", {})
    test_dists: Mapping[str, str] = test.get("distributions", {})
    for name in sorted(set(base_dists) | set(test_dists)):
        if base_dists.get(name) != test_dists.get(name):
            lines.append(f"distribution {name}: {base_dists.get(name)} != {test_dists.get(name)}")
    return lines


def outside_git(path: Path) -> None:
    """
    Reject a work directory inside a Git repository

    `great-docs` reads the remote and branch of the repository around a package, so a
    package generated inside one would build differently.

    Parameters
    ----------
    path :
        Directory where packages are generated.

    Raises
    ------
    HarnessError
        If the directory or one of its parents holds `.git`.
    """
    resolved = path.resolve()
    for directory in (resolved, *resolved.parents):
        if (directory / ".git").exists():
            raise HarnessError(f"{path} is inside the git repository at {directory}")
