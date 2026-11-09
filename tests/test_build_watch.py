"""
Preview rebuilds after documentation source edits
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import watchfiles

from great_docs import GreatDocs
from great_docs._build import watch
from great_docs._project.layout import Layout

CONFIG = "reference: false\nchangelog:\n  enabled: false\nskill:\n  enabled: false\n"
MARKER = "A line added while watching."
PACKAGE = "watch_demo"

Edits = Callable[[Layout], Iterator[set[Path]]]


class _Preview:
    """A stand-in for `quarto preview` that runs until stopped"""

    def __init__(self) -> None:
        self._stopped = threading.Event()

    def poll(self) -> int | None:
        """
        Report the exit status

        Returns
        -------
        :
            `0` once stopped, otherwise `None`.
        """
        return 0 if self._stopped.is_set() else None

    def wait(self, timeout: float | None = None) -> int:
        """
        Wait until the process is stopped

        Parameters
        ----------
        timeout
            Seconds to wait, or `None` to wait until stopped.

        Returns
        -------
        :
            The exit status, `0`.
        """
        _ = self._stopped.wait(timeout)
        return 0

    def terminate(self) -> None:
        """Stop the process"""
        self._stopped.set()


def _project(root: Path, config: str = CONFIG) -> GreatDocs:
    """
    Create a project with a home page and two user guide pages

    Parameters
    ----------
    root
        The project directory.
    config
        The contents of `great-docs.yml`.

    Returns
    -------
    :
        The project, with its sources in `docs/`.
    """
    (root / "pyproject.toml").write_text('[project]\nname = "watch-demo"\n', encoding="utf-8")
    docs = root / "docs"
    guide = docs / "user_guide"
    guide.mkdir(parents=True)
    (docs / "great-docs.yml").write_text(config, encoding="utf-8")
    (docs / "index.qmd").write_text("# Watch demo\n", encoding="utf-8")
    (guide / "01-intro.qmd").write_text("---\ntitle: Intro\n---\n\nFirst.\n", encoding="utf-8")
    (guide / "02-usage.qmd").write_text("---\ntitle: Usage\n---\n\nSecond.\n", encoding="utf-8")
    return GreatDocs(str(root))


def _watch(
    docs: GreatDocs,
    monkeypatch: pytest.MonkeyPatch,
    edits: Edits,
    watched: list[Path] | None = None,
) -> list[list[str]]:
    """
    Build in watch mode and apply source edits while the preview runs

    Parameters
    ----------
    docs
        The project.
    monkeypatch
        The test's patcher.
    edits
        A generator that edits the project's sources and yields each batch of changed paths,
        in place of watching the file system.
    watched
        A list that receives the directories the watch would observe.

    Returns
    -------
    :
        The `quarto` commands started.
    """
    started: list[list[str]] = []
    popen = subprocess.Popen

    def start(command: list[str], *args: Any, **kwargs: Any) -> object:
        if command[:1] == ["quarto"]:
            started.append(command)
            # Simulate Quarto output to detect its accidental removal during rebuilds.
            site = Path(str(kwargs["cwd"])) / "_site"
            site.mkdir(exist_ok=True)
            (site / "index.html").write_text("<html></html>", encoding="utf-8")
            return _Preview()
        return popen(command, *args, **kwargs)

    monkeypatch.setattr("great_docs._build.quarto.ensure_installed", lambda: None)
    monkeypatch.setattr(subprocess, "Popen", start)

    def changes(layout: Layout, package: Path | None, stop: threading.Event) -> Iterator[set[Path]]:
        if watched is not None:
            watched.extend(watch.watched_dirs(layout, package))
        return edits(layout)

    monkeypatch.setattr(watch, "source_changes", changes)
    docs.build(watch=True, refresh=False)
    return started


def _holding(build_dir: Path, text: str) -> list[str]:
    """
    List project files containing the given text

    Parameters
    ----------
    build_dir
        The project directory.
    text
        The text to look for.

    Returns
    -------
    :
        The paths relative to `build_dir`.
    """
    return sorted(
        path.relative_to(build_dir).as_posix()
        for path in build_dir.rglob("*")
        if path.is_file() and text in path.read_text(encoding="utf-8", errors="ignore")
    )


def test_watch_copies_an_edited_page_into_the_previewed_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    docs = _project(tmp_path)
    page = docs.layout.source_dir / "user_guide" / "01-intro.qmd"
    unchanged: dict[str, int] = {}

    def edit(layout: Layout) -> Iterator[set[Path]]:
        unchanged["mtime"] = (layout.build_dir / "_quarto.yml").stat().st_mtime_ns
        with page.open("a", encoding="utf-8") as file:
            _ = file.write(f"\n{MARKER}\n")
        yield {page}

    started = _watch(docs, monkeypatch, edit)

    assert _holding(docs.layout.build_dir, MARKER) == ["user-guide/intro.qmd"]
    assert (docs.layout.build_dir / "_quarto.yml").stat().st_mtime_ns == unchanged["mtime"]
    assert started == [["quarto", "preview", "--no-browser"]]
    assert not (docs.layout.cache_dir / "watch").exists()


def test_watch_removes_a_deleted_page_and_keeps_quarto_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    docs = _project(tmp_path)
    page = docs.layout.source_dir / "user_guide" / "02-usage.qmd"

    def delete(layout: Layout) -> Iterator[set[Path]]:
        page.unlink()
        yield {page}

    _ = _watch(docs, monkeypatch, delete)

    assert not (docs.layout.build_dir / "user-guide" / "usage.qmd").exists()
    assert (docs.layout.build_dir / "user-guide" / "intro.qmd").exists()
    assert (docs.layout.build_dir / "_site" / "index.html").exists()


def test_watch_applies_configuration_edits_without_restarting_quarto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    docs = _project(tmp_path)

    def configure(layout: Layout) -> Iterator[set[Path]]:
        layout.config_path.write_text(CONFIG + "display_name: Renamed Demo\n", encoding="utf-8")
        yield {layout.config_path}

    started = _watch(docs, monkeypatch, configure)

    assert "Renamed Demo" in (docs.layout.build_dir / "_quarto.yml").read_text(encoding="utf-8")
    assert started == [["quarto", "preview", "--no-browser"]]
    assert "restart" not in capsys.readouterr().out


def test_watch_keeps_the_last_good_build_after_an_invalid_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    docs = _project(tmp_path)
    page = docs.layout.source_dir / "user_guide" / "01-intro.qmd"
    invalid = CONFIG + "pre_render:\n  - a/hook.py\n  - b/hook.py\n"

    def break_then_fix(layout: Layout) -> Iterator[set[Path]]:
        layout.config_path.write_text(invalid, encoding="utf-8")
        with page.open("a", encoding="utf-8") as file:
            _ = file.write(f"\n{MARKER}\n")
        yield {layout.config_path, page}
        layout.config_path.write_text(CONFIG, encoding="utf-8")
        yield {layout.config_path}

    seen: list[list[str]] = []

    def edits(layout: Layout) -> Iterator[set[Path]]:
        for batch in break_then_fix(layout):
            yield batch
            seen.append(_holding(layout.build_dir, MARKER))

    _ = _watch(docs, monkeypatch, edits)

    assert seen == [[], ["user-guide/intro.qmd"]]
    assert "The preview keeps the last successful build." in capsys.readouterr().out


def test_watch_asks_for_a_restart_once_when_project_settings_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    docs = _project(tmp_path)
    page = docs.layout.source_dir / "user_guide" / "01-intro.qmd"
    (docs.layout.source_dir / "hook.py").write_text("", encoding="utf-8")

    def add_hook_then_edit(layout: Layout) -> Iterator[set[Path]]:
        # A `pre_render` script adds `project.pre-render` to the Quarto configuration.
        layout.config_path.write_text(CONFIG + "pre_render: hook.py\n", encoding="utf-8")
        yield {layout.config_path}
        with page.open("a", encoding="utf-8") as file:
            _ = file.write(f"\n{MARKER}\n")
        yield {page}

    _ = _watch(docs, monkeypatch, add_hook_then_edit)

    assert capsys.readouterr().out.count("rerun `great-docs build --watch`") == 1


@pytest.fixture
def package_project(tmp_path: Path) -> Iterator[GreatDocs]:
    """
    Create a project whose package sits beside `docs/` and is documented dynamically

    Yields
    ------
    :
        The project. Its package's modules leave `sys.modules` afterwards.
    """
    package = tmp_path / PACKAGE
    package.mkdir()
    (package / "__init__.py").write_text(
        '__all__ = ["greet"]\n\n\ndef greet() -> str:\n    """Say hello"""\n    return "hello"\n',
        encoding="utf-8",
    )
    config = "dynamic: true\nchangelog:\n  enabled: false\nskill:\n  enabled: false\n"
    yield _project(tmp_path, config)
    for name in [name for name in sys.modules if name.split(".")[0] == PACKAGE]:
        del sys.modules[name]


def test_watch_rebuilds_the_reference_after_a_docstring_edit(
    package_project: GreatDocs, monkeypatch: pytest.MonkeyPatch
):
    init = package_project.layout.package_root / PACKAGE / "__init__.py"
    watched: list[Path] = []

    def edit(layout: Layout) -> Iterator[set[Path]]:
        source = init.read_text(encoding="utf-8")
        init.write_text(source.replace("Say hello", MARKER), encoding="utf-8")
        yield {init}

    _ = _watch(package_project, monkeypatch, edit, watched)

    assert watched == [package_project.layout.source_dir, init.parent]
    assert "reference/greet.qmd" in _holding(package_project.layout.build_dir, MARKER)


@pytest.mark.parametrize(
    ("directory", "package", "expected"),
    [
        ("docs", "pkg", ["docs", "pkg"]),
        ("docs", "src/pkg", ["docs", "src/pkg"]),
        (".", "pkg", ["."]),
        ("pkg/docs", "pkg", ["pkg"]),
        ("docs", None, ["docs"]),
    ],
)
def test_watched_dirs_cover_each_directory_once(
    tmp_path: Path, directory: str, package: str | None, expected: list[str]
):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "watch-demo"\n', encoding="utf-8")
    source = tmp_path / directory
    source.mkdir(parents=True, exist_ok=True)
    (source / "great-docs.yml").write_text(CONFIG, encoding="utf-8")
    layout = Layout.make(tmp_path, source / "great-docs.yml")

    watched = watch.watched_dirs(layout, None if package is None else tmp_path.resolve() / package)

    assert watched == [tmp_path.resolve() / path for path in expected]


@pytest.mark.parametrize(
    ("path", "accepted"),
    [
        ("watch_demo/__init__.py", True),
        ("watch_demo/core/api.py", True),
        ("watch_demo/__pycache__/__init__.cpython-313.pyc", False),
        ("watch_demo/.mypy_cache/core.json", False),
        ("watch_demo/.notes.py", False),
    ],
)
def test_source_filter_accepts_package_sources(tmp_path: Path, path: str, accepted: bool):
    docs = _project(tmp_path)

    accept = watch.source_filter(docs.layout, tmp_path.resolve() / PACKAGE)

    assert accept(watchfiles.Change.modified, str(tmp_path.resolve() / path)) is accepted


@pytest.mark.parametrize(
    ("path", "accepted"),
    [
        ("docs/user_guide/01-intro.qmd", True),
        ("docs/great-docs.yml", True),
        ("docs/assets/logo.png", True),
        ("docs/_quarto/default/index.qmd", False),
        ("docs/_site/index.html", False),
        ("docs/.cache/watch/index.qmd", False),
        ("docs/_freeze/index/execute-results/html.json", False),
        ("docs/.notes/draft.qmd", False),
        ("docs/user_guide/__pycache__/hook.cpython-313.pyc", False),
    ],
)
def test_source_filter_skips_generated_and_hidden_files(tmp_path: Path, path: str, accepted: bool):
    docs = _project(tmp_path)

    accept = watch.source_filter(docs.layout, None)

    assert accept(watchfiles.Change.modified, str(tmp_path.resolve() / path)) is accepted


@pytest.mark.parametrize("directory", [".", "docs"])
def test_staging_skips_the_previewed_project(tmp_path: Path, directory: str):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "watch-demo"\n', encoding="utf-8")
    source = tmp_path / directory
    source.mkdir(exist_ok=True)
    (source / "great-docs.yml").write_text(CONFIG, encoding="utf-8")
    layout = Layout.make(tmp_path)

    staging = watch.stage(layout)

    assert staging.build_dir.is_relative_to(layout.cache_dir)
    top = layout.source_dir / layout.build_dir.relative_to(layout.source_dir).parts[0]
    assert staging.is_reserved_directory(top)
    assert layout.build_dir in staging.generated_dirs()


def test_forget_package_ignores_stale_bytecode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reimports read an edit that keeps the source size and modification time"""
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "stale_bytecode_pkg", raising=False)
    source = tmp_path / "stale_bytecode_pkg.py"
    source.write_text("VALUE = 'old'\n")

    import stale_bytecode_pkg  # type: ignore[import-not-found]

    assert stale_bytecode_pkg.VALUE == "old"

    mtime_ns = source.stat().st_mtime_ns
    source.write_text("VALUE = 'new'\n")
    os.utime(source, ns=(mtime_ns, mtime_ns))
    watch.forget_package("stale_bytecode_pkg")

    import stale_bytecode_pkg  # type: ignore[import-not-found]  # noqa: F811

    assert stale_bytecode_pkg.VALUE == "new"
    sys.modules.pop("stale_bytecode_pkg", None)
