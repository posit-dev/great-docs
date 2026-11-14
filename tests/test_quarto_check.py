from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from great_docs import BuildError, GreatDocs
from great_docs import core
from great_docs._build import quarto
from great_docs._build.quarto import QuartoNotFoundError, QuartoVersionError


TROUBLESHOOTING_URL = "https://posit-dev.github.io/great-docs/recipes/fix-common-build-errors.html"


def test_ensure_installed_passes_when_present(monkeypatch):
    monkeypatch.setattr(
        "great_docs._build.quarto.shutil.which",
        lambda name: "/usr/local/bin/quarto" if name == "quarto" else None,
    )
    monkeypatch.setattr("great_docs._build.quarto.installed_version", lambda: (1, 10, 0))
    assert quarto.ensure_installed() is None


def test_ensure_installed_raises_when_too_old(monkeypatch):
    monkeypatch.setattr(
        "great_docs._build.quarto.shutil.which", lambda name: "/usr/local/bin/quarto"
    )
    monkeypatch.setattr("great_docs._build.quarto.installed_version", lambda: (1, 8, 26))

    with pytest.raises(QuartoVersionError, match=r"1\.9\.18 or later, but found Quarto 1\.8\.26"):
        quarto.ensure_installed()


def test_ensure_installed_passes_when_version_unreadable(monkeypatch):
    monkeypatch.setattr(
        "great_docs._build.quarto.shutil.which", lambda name: "/usr/local/bin/quarto"
    )
    monkeypatch.setattr("great_docs._build.quarto.installed_version", lambda: None)
    assert quarto.ensure_installed() is None


def test_ensure_installed_raises_when_missing(monkeypatch):
    monkeypatch.setattr("great_docs._build.quarto.shutil.which", lambda name: None)

    with pytest.raises(QuartoNotFoundError) as excinfo:
        quarto.ensure_installed()

    msg = str(excinfo.value)
    assert "system-level dependency" in msg
    assert TROUBLESHOOTING_URL in msg


def test_quarto_not_found_error_is_runtime_error():
    assert issubclass(QuartoNotFoundError, RuntimeError)


def test_quarto_errors_are_build_errors():
    assert issubclass(QuartoNotFoundError, BuildError)
    assert issubclass(QuartoVersionError, BuildError)


def test_core_exports_quarto_errors():
    assert core.QuartoNotFoundError is QuartoNotFoundError
    assert core.QuartoVersionError is QuartoVersionError


def test_build_reports_and_raises_quarto_not_found_when_quarto_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr("great_docs._build.quarto.shutil.which", lambda name: None)

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.install(force=True)
        capsys.readouterr()

        with pytest.raises(QuartoNotFoundError, match="great-docs") as excinfo:
            docs.build()

    assert capsys.readouterr().err == f"Error: {excinfo.value}\n"


def test_executable_defaults_to_quarto(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(quarto.EXECUTABLE_ENV, raising=False)
    assert quarto.executable() == "quarto"
    assert not quarto.is_q2()


@pytest.mark.parametrize(
    ("value", "q2"),
    [
        ("q2", True),
        ("/opt/q2/target/release/q2", True),
        ("/opt/bin/q2.exe", True),
        ("quarto", False),
        ("/usr/local/bin/quarto", False),
        ("  ", False),
    ],
)
def test_is_q2_reads_the_executable_name(monkeypatch: pytest.MonkeyPatch, value: str, q2: bool):
    monkeypatch.setenv(quarto.EXECUTABLE_ENV, value)
    assert quarto.is_q2() is q2


@pytest.mark.parametrize(
    ("stdout", "version"),
    [
        ("1.9.37\n", (1, 9, 37)),
        ("q2 (quarto 2) 0.45.0\n", (0, 45, 0)),
        ("Q2 (quarto 2) 0.46.1\n", (0, 46, 1)),
        ("unknown\n", None),
    ],
)
def test_installed_version_reads_quarto_and_quarto_2(
    monkeypatch: pytest.MonkeyPatch, stdout: str, version: tuple[int, ...] | None
):
    monkeypatch.setattr(
        "great_docs._build.quarto.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout, ""),
    )
    assert quarto.installed_version() == version


def test_ensure_installed_applies_the_quarto_2_minimum(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(quarto.EXECUTABLE_ENV, "q2")
    monkeypatch.setattr("great_docs._build.quarto.shutil.which", lambda name: "/bin/q2")
    monkeypatch.setattr("great_docs._build.quarto.installed_version", lambda: (0, 45, 0))
    assert quarto.ensure_installed() is None

    monkeypatch.setattr("great_docs._build.quarto.installed_version", lambda: (0, 44, 2))
    with pytest.raises(QuartoVersionError, match=r"Quarto 2 0\.45\.0 or later"):
        quarto.ensure_installed()


def test_ensure_installed_names_a_missing_quarto_2(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(quarto.EXECUTABLE_ENV, "/nowhere/q2")
    monkeypatch.setattr("great_docs._build.quarto.shutil.which", lambda name: None)

    with pytest.raises(QuartoNotFoundError, match="GREAT_DOCS_QUARTO is '/nowhere/q2'"):
        quarto.ensure_installed()


def test_environment_puts_the_python_scripts_first_for_quarto_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv(quarto.EXECUTABLE_ENV, "q2")
    docs = GreatDocs(project_path=str(tmp_path))
    env = quarto.environment(docs._config)

    scripts = os.path.dirname(env["QUARTO_PYTHON"])
    assert env["PATH"].split(os.pathsep)[0] == scripts


@pytest.mark.skipif(sys.platform == "win32", reason="the fake Quarto 2 is a shell script")
def test_render_reports_quarto_2_pages_and_warnings_when_it_ends(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    fake = tmp_path / "bin" / "q2"
    fake.parent.mkdir()
    out = tmp_path / "_site"
    fake.write_text(
        "#!/bin/sh\n"
        f'echo "Rendering project: {tmp_path} (type: website)" >&2\n'
        'echo "Warning [Q-2-9]: naked HTML in a.qmd" >&2\n'
        'echo "Warning [Q-2-9]: naked HTML in b.qmd" >&2\n'
        'echo "Warning: no code here" >&2\n'
        f'echo "2026-01-01T00:00:00Z  INFO q2::commands::render: Output: {out}/a.html" >&2\n'
        f'echo "2026-01-01T00:00:00Z  INFO q2::commands::render: Output: {out}/b.html" >&2\n'
        f'echo "Rendered 2 of 2 files to {out} — 3 warnings" >&2\n',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv(quarto.EXECUTABLE_ENV, str(fake))
    events: list[object] = []

    result = quarto.render(tmp_path, on_page=events.append, on_warning=events.append)

    assert result.returncode == 0
    assert result.page_timings == []
    assert events == [
        "WARN [Q-2-9] naked HTML in a.qmd (and 1 more like it)",
        "WARN no code here",
        quarto.Progress(1, 2, os.path.join("_site", "a.html")),
        quarto.Progress(2, 2, os.path.join("_site", "b.html")),
    ]
