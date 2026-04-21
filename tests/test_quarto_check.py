from __future__ import annotations

import tempfile

import pytest

from great_docs import GreatDocs
from great_docs.core import QuartoNotFoundError, _ensure_quarto_installed


TROUBLESHOOTING_URL = (
    "https://posit-dev.github.io/great-docs/recipes/fix-common-build-errors.html"
)


def test_ensure_quarto_installed_passes_when_present(monkeypatch):
    monkeypatch.setattr(
        "great_docs.core.shutil.which",
        lambda name: "/usr/local/bin/quarto" if name == "quarto" else None,
    )
    assert _ensure_quarto_installed() is None


def test_ensure_quarto_installed_raises_when_missing(monkeypatch):
    monkeypatch.setattr("great_docs.core.shutil.which", lambda name: None)

    with pytest.raises(QuartoNotFoundError) as excinfo:
        _ensure_quarto_installed()

    msg = str(excinfo.value)
    assert "system-level dependency" in msg
    assert TROUBLESHOOTING_URL in msg
    assert "great-docs install-quarto" in msg


def test_quarto_not_found_error_is_runtime_error():
    assert issubclass(QuartoNotFoundError, RuntimeError)


def test_build_raises_quarto_not_found_when_quarto_missing(monkeypatch):
    monkeypatch.setattr("great_docs.core.shutil.which", lambda name: None)

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.install(force=True)

        with pytest.raises(QuartoNotFoundError, match="great-docs install-quarto"):
            docs.build()