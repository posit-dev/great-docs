"""Test source-edit readiness through the watch recorder's real child process"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.quarto_project_diff import record
from tests.quarto_project_diff.catalogue import BuildCase
from tests.quarto_project_diff.sides import Side


@pytest.mark.parametrize("force_polling", [False, True])
@pytest.mark.parametrize("rebuild", [False, True])
def test_watch_edit_waits_for_source_subscription(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, force_polling: bool, rebuild: bool
) -> None:
    """Measure one edit after delayed subscription and require a real rebuild"""
    package = tmp_path / "package"
    package.mkdir()
    source = package / "README.md"
    original = "Original source\n"
    source.write_text(original, encoding="utf-8")
    os.utime(source, (1, 1))
    release = tmp_path / "release-observer"
    script = tmp_path / "preview.py"
    script.write_text(
        textwrap.dedent(
            f"""\
            import os
            import time
            from pathlib import Path
            import watchfiles

            root = Path.cwd()
            source = root / "package" / "README.md"
            served = root / "served"
            served.mkdir()
            Path(os.environ["{record.PREVIEW_DIRECTORY_VARIABLE}"]).write_text(str(served))
            try:
                while not (root / "release-observer").exists():
                    time.sleep(0.01)
                for changes in watchfiles.watch(
                    source.parent, force_polling={force_polling!r}, poll_delay_ms=10,
                    debounce=20, step=5,
                ):
                    (root / "observed").touch()
                    if {rebuild!r}:
                        (served / "index.qmd").write_text(source.read_text())
            except KeyboardInterrupt:
                pass
            """
        ),
        encoding="utf-8",
    )
    wait_until = record._wait_until

    def release_after_preview(
        condition: Callable[[], bool], process: subprocess.Popen[bytes], until: float
    ) -> bool:
        if (tmp_path / "preview-directory.txt").is_file() and not release.exists():
            assert source.read_text(encoding="utf-8") == original
            release.touch()
        return wait_until(condition, process, until)

    monkeypatch.setattr(record, "_wait_until", release_after_preview)
    monkeypatch.setattr(record, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(record, "REBUILD_SECONDS", 2.0)
    env = {**os.environ, "PYTHONPATH": ""}
    job = record.Job(
        BuildCase("package", watch_edit="README.md"),
        Side("test", tmp_path, tmp_path),
        package,
        tmp_path,
        tmp_path,
        env,
        3.0,
        False,
    )
    with (tmp_path / "stdout").open("wb") as out, (tmp_path / "stderr").open("wb") as err:
        status, facts = record.run_watch(job, [sys.executable, str(script)], package, env, out, err)

    assert status == 0
    assert facts == {"previewed": True, "rebuilt": rebuild}
    assert (tmp_path / "observed").is_file()
    assert source.read_text(encoding="utf-8") == f"{original}\n{record.WATCH_MARKER}\n"
    assert (tmp_path / "stderr").read_text(encoding="utf-8") == ""


def test_watch_without_source_subscription_does_not_measure_an_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail a preview without a matching observer without editing its source"""
    package = tmp_path / "package"
    package.mkdir()
    source = package / "README.md"
    source.write_text("Original source\n", encoding="utf-8")
    script = tmp_path / "preview.py"
    script.write_text(
        textwrap.dedent(
            f"""\
            import os
            from pathlib import Path
            import watchfiles

            root = Path.cwd()
            served = root / "served"
            served.mkdir()
            unrelated = root / "unrelated"
            unrelated.mkdir()
            Path(os.environ["{record.PREVIEW_DIRECTORY_VARIABLE}"]).write_text(str(served))
            try:
                for changes in watchfiles.watch(unrelated):
                    pass
            except KeyboardInterrupt:
                pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(record, "POLL_SECONDS", 0.01)
    env = {**os.environ, "PYTHONPATH": ""}
    job = record.Job(
        BuildCase("package", watch_edit="README.md"),
        Side("test", tmp_path, tmp_path),
        package,
        tmp_path,
        tmp_path,
        env,
        3.0,
        False,
    )
    with (tmp_path / "stdout").open("wb") as out, (tmp_path / "stderr").open("wb") as err:
        status, facts = record.run_watch(job, [sys.executable, str(script)], package, env, out, err)

    assert status == 0
    assert facts == {"previewed": True, "rebuilt": False}
    assert source.read_text(encoding="utf-8") == "Original source\n"
    assert not (tmp_path / "watch-ready").exists()
    assert (tmp_path / "stderr").read_text(encoding="utf-8") == ""
