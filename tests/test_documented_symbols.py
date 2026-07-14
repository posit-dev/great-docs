from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

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
    (sub / "__init__.py").write_text("from mypkg.sub.things import Widget\n__all__ = ['Widget']\n")
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


def test_does_not_write_build_artifacts(tmp_path: Path):
    """`documented_symbol_names` is a read-only query: it must leave no files behind.

    The resolution pipeline (via `_create_api_sections_from_config`) normally
    writes `_object_types.json` (and a `_constant_values.json` sidecar). Calling
    it as a programmatic query (e.g., from `api-snapshot` / `api-diff`) must not
    drop those artifacts into the project tree.
    """
    _write_pkg(tmp_path)
    gd = GreatDocs(project_path=str(tmp_path))

    names = gd.documented_symbol_names("mypkg")
    assert names  # sanity: the config path (which performs the write) ran

    artifacts = list(tmp_path.rglob("_object_types.json")) + list(
        tmp_path.rglob("_constant_values.json")
    )
    assert artifacts == [], f"query left build artifacts behind: {artifacts}"

    # The flag is reset so a subsequent real build can still write artifacts.
    assert gd._suppress_artifact_writes is False


def test_returns_empty_without_reference_config(tmp_path: Path):
    """Without a reference config, the resolver delegates to auto-discovery (same as the renderer).

    A completely empty package (no exports) must still yield an empty list.
    """
    # Bare package with no exports so auto-discovery produces nothing.
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "emptypkg"\nversion = "0.1.0"\n')
    (tmp_path / "emptypkg").mkdir()
    (tmp_path / "emptypkg" / "__init__.py").write_text("__all__ = []\n")
    (tmp_path / "great-docs.yml").write_text("logo: assets/logo.png\n")
    gd = GreatDocs(project_path=str(tmp_path))
    assert gd.documented_symbol_names("emptypkg") == []


def test_resolver_matches_renderer_sections(tmp_path: Path):
    """Resolver and renderer each match an independent ground-truth stem list.

    Both sides are verified against a hard-coded expectation derived from the
    `_write_pkg` fixture config, so divergence bugs cannot hide behind a
    circular comparison.
    """
    _write_pkg(tmp_path)
    gd = GreatDocs(project_path=str(tmp_path))

    # Ground truth: stems that the _write_pkg fixture config declares.
    expected = ["TopClass", "sub.Widget", "sub.Widget.fit"]

    # Resolver must match ground truth.
    assert gd.documented_symbol_names("mypkg") == expected

    # Renderer sections, flattened independently, must also match ground truth.
    sections = gd._create_api_sections_with_config("mypkg")
    renderer_stems: list[str] = []
    for section in sections or []:
        for item in section.get("contents", []):
            if isinstance(item, str):
                renderer_stems.append(item)
            elif isinstance(item, dict):
                name = item["name"]
                renderer_stems.append(name)
                renderer_stems.extend(f"{name}.{m}" for m in item.get("members", []) or [])
    assert list(dict.fromkeys(renderer_stems)) == expected


def _write_pkg_with_nodoc(root: Path) -> None:
    """A package with two documented classes, one of them marked %nodoc"""
    (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "0.1.0"\n')
    pkg = root / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        textwrap.dedent(
            """
            from mypkg.core import VisibleClass, HiddenClass
            __all__ = ["VisibleClass", "HiddenClass"]
            """
        )
    )
    (pkg / "core.py").write_text(
        textwrap.dedent(
            '''
            class VisibleClass:
                """A documented class."""
                ...

            class HiddenClass:
                """An internal class.

                %nodoc
                """
                ...
            '''
        )
    )
    (root / "great-docs.yml").write_text(
        textwrap.dedent(
            """
            reference:
              - title: API
                contents:
                  - VisibleClass
                  - HiddenClass
            """
        )
    )


def test_nodoc_symbol_excluded_from_documented_symbol_names(tmp_path: Path):
    """A symbol whose docstring contains %nodoc must be absent from the resolver output.

    This verifies that `documented_symbol_names` honours the same nodoc filter that
    the dev-build renderer applies, so a tagged versioned build cannot generate a
    page the dev renderer hides.
    """
    _write_pkg_with_nodoc(tmp_path)
    gd = GreatDocs(project_path=str(tmp_path))
    names = gd.documented_symbol_names("mypkg")
    assert "VisibleClass" in names
    assert "HiddenClass" not in names


def test_deduplication_preserves_first_occurrence_order(tmp_path: Path):
    """Symbols that appear more than once are deduplicated, keeping first-occurrence order."""
    _write_pkg(tmp_path)
    # Overwrite config with a reference block that repeats TopClass and sub.Widget.fit.
    (tmp_path / "great-docs.yml").write_text(
        textwrap.dedent(
            """
            reference:
              - title: Section A
                contents:
                  - TopClass
                  - name: sub.Widget
                    members:
                      - fit
              - title: Section B
                contents:
                  - TopClass
                  - sub.Widget.fit
            """
        )
    )
    gd = GreatDocs(project_path=str(tmp_path))
    names = gd.documented_symbol_names("mypkg")
    # Duplicates removed; first-occurrence order is: TopClass, sub.Widget, sub.Widget.fit.
    assert names == ["TopClass", "sub.Widget", "sub.Widget.fit"]
    # No duplicates.
    assert len(names) == len(set(names))


def test_search_path_failure_preserves_original_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pkg(tmp_path)
    gd = GreatDocs(project_path=str(tmp_path))

    def fail_search_paths() -> list[str]:
        raise RuntimeError("search path failure")

    monkeypatch.setattr(gd, "_griffe_search_paths", fail_search_paths)

    with pytest.raises(RuntimeError, match="search path failure"):
        gd.documented_symbol_names("mypkg")

    assert gd._suppress_artifact_writes is False


def test_restores_cached_package_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_pkg(tmp_path)
    gd = GreatDocs(project_path=str(tmp_path))
    cached_package = ModuleType("mypkg")
    cached_submodule = ModuleType("mypkg.cached")
    for key in [key for key in sys.modules if key == "mypkg" or key.startswith("mypkg.")]:
        monkeypatch.delitem(sys.modules, key)
    monkeypatch.setitem(sys.modules, "mypkg", cached_package)
    monkeypatch.setitem(sys.modules, "mypkg.cached", cached_submodule)

    assert gd.documented_symbol_names("mypkg") == [
        "TopClass",
        "sub.Widget",
        "sub.Widget.fit",
    ]
    assert sys.modules["mypkg"] is cached_package
    assert sys.modules["mypkg.cached"] is cached_submodule
    assert "mypkg.core" not in sys.modules
    assert "mypkg.sub" not in sys.modules


def test_missing_configured_symbol_returns_empty(tmp_path: Path) -> None:
    _write_pkg(tmp_path)
    (tmp_path / "great-docs.yml").write_text(
        "reference:\n  - title: API\n    contents:\n      - MissingObject\n"
    )

    gd = GreatDocs(project_path=str(tmp_path))

    assert gd.documented_symbol_names("mypkg") == []


def test_dynamic_import_failure_returns_empty(tmp_path: Path) -> None:
    _write_pkg(tmp_path)
    (tmp_path / "mypkg" / "__init__.py").write_text("raise ImportError('broken package')\n")
    (tmp_path / "great-docs.yml").write_text(
        "dynamic: true\nreference:\n  - title: API\n    contents:\n      - TopClass\n"
    )

    gd = GreatDocs(project_path=str(tmp_path))

    assert gd.documented_symbol_names("mypkg") == []
