from __future__ import annotations

import textwrap
from pathlib import Path

from great_docs.core import GreatDocs


def _write_pkg(root: Path) -> None:
    """A minimal package whose public API lives under a submodule, with a matching reference: config"""
    (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "0.1.0"\n')
    pkg = root / "mypkg"
    sub = pkg / "sub"
    sub.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        textwrap.dedent(
            """
            from mypkg import sub
            from mypkg.core import TopClass
            __all__ = ["TopClass", "sub"]
            """
        )
    )
    (pkg / "core.py").write_text("class TopClass:\n    def go(self): ...\n")
    (sub / "__init__.py").write_text(
        "from mypkg.sub.things import Widget\n__all__ = ['Widget']\n"
    )
    (sub / "things.py").write_text("class Widget:\n    def fit(self): ...\n")
    (root / "great-docs.yml").write_text(
        textwrap.dedent(
            """
            reference:
              - title: API
                contents:
                  - TopClass
                  - name: sub.Widget
                    members:
                      - fit
            """
        )
    )


def test_flattens_config_into_dotted_stems(tmp_path: Path):
    _write_pkg(tmp_path)
    gd = GreatDocs(project_path=str(tmp_path))
    names = gd.documented_symbol_names("mypkg")
    assert names == ["TopClass", "sub.Widget", "sub.Widget.fit"]


def test_returns_empty_without_reference_config(tmp_path: Path):
    _write_pkg(tmp_path)
    (tmp_path / "great-docs.yml").write_text("logo: assets/logo.png\n")
    gd = GreatDocs(project_path=str(tmp_path))
    assert gd.documented_symbol_names("mypkg") == []
