from __future__ import annotations

import tempfile

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
