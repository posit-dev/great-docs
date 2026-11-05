"""
Preview rebuilds after documentation source edits
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import watchfiles

from great_docs import GreatDocs
from great_docs._build import watch
from great_docs._layout import Layout

CONFIG = "reference: false\nchangelog:\n  enabled: false\nskill:\n  enabled: false\n"
MARKER = "A line added while watching."

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


def _project(root: Path) -> GreatDocs:
    """
    Create a project with a home page and two user guide pages

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
        The project, with its sources in `docs/`.
    """
    (root / "pyproject.toml").write_text('[project]\nname = "watch-demo"\n', encoding="utf-8")
    docs = root / "docs"
    guide = docs / "user_guide"
    guide.mkdir(parents=True)
    (docs / "great-docs.yml").write_text(CONFIG, encoding="utf-8")
    (docs / "index.qmd").write_text("# Watch demo\n", encoding="utf-8")
    (guide / "01-intro.qmd").write_text("---\ntitle: Intro\n---\n\nFirst.\n", encoding="utf-8")
    (guide / "02-usage.qmd").write_text("---\ntitle: Usage\n---\n\nSecond.\n", encoding="utf-8")
    return GreatDocs(str(root))


def _watch(docs: GreatDocs, monkeypatch: pytest.MonkeyPatch, edits: Edits) -> list[list[str]]:
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

    def changes(layout: Layout, stop: threading.Event) -> Iterator[set[Path]]:
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


def test_sync_asks_for_a_restart_when_project_settings_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    staged, served = tmp_path / "staged", tmp_path / "served"
    staged.mkdir()
    served.mkdir()
    (served / "_quarto.yml").write_text("project:\n  type: website\n", encoding="utf-8")
    (staged / "_quarto.yml").write_text(
        "project:\n  type: website\n  render: [index.qmd]\n", encoding="utf-8"
    )

    _ = watch.sync(staged, served, {"_quarto.yml": b"previous digest"})

    assert "rerun `great-docs build --watch`" in capsys.readouterr().out


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

    accept = watch.source_filter(docs.layout)

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
