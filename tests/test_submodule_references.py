"""
Reference lookup through submodules that the package root does not import
"""

from __future__ import annotations

import importlib
import io
import sys
from collections.abc import Iterator
from pathlib import Path

import griffe
import pytest

from great_docs import GreatDocs
from great_docs._apiref.introspect import get_object
from great_docs._apiref.resolve import _join_path
from great_docs._build import reference
from great_docs._build.log import BuildLog
from great_docs._reference.discovery import categorise_references
from tests.support import StubRemote, make_run, prepare_build_directory, write_config


@pytest.fixture
def package_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Create an importable package whose submodules provide runtime documentation
    """
    package = tmp_path / "lookup_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("declaration: int\nremoved = 1\ndel removed\n")
    function = (
        'def censor(value):\n    """Static censor documentation"""\n    return value\n'
        'censor.__doc__ = "Runtime " + "censor documentation"\n'
    )
    (package / "bounds.py").write_text(function)
    nested = package / "nested"
    nested.mkdir()
    (nested / "__init__.py").write_text("")
    (nested / "tools.py").write_text(function)
    (package / "broken.py").write_text("import lookup_dependency_missing\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "lookup-pkg"\nversion = "1.0.0"\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for name in list(sys.modules):
        if name == "lookup_pkg" or name.startswith("lookup_pkg."):
            sys.modules.pop(name, None)


@pytest.mark.parametrize("name", ["bounds.censor", "nested.tools.censor"])
def test_dynamic_lookup_imports_only_the_requested_submodules(
    package_root: Path, name: str
) -> None:
    """
    Use runtime documentation without requiring root-package imports
    """
    package = importlib.import_module("lookup_pkg")
    assert not hasattr(package, name.split(".", 1)[0])
    obj = get_object(f"lookup_pkg:{name}", dynamic=True)
    assert obj.path == f"lookup_pkg.{name}"
    assert obj.docstring is not None
    assert obj.docstring.value == "Runtime censor documentation"
    assert "lookup_pkg.broken" not in sys.modules


def test_submodule_import_preserves_missing_dependency_errors(package_root: Path) -> None:
    """
    Report an import failure inside the requested submodule
    """
    with pytest.raises(ModuleNotFoundError) as error:
        get_object("lookup_pkg:broken.censor", dynamic=True)
    assert error.value.name == "lookup_dependency_missing"


@pytest.mark.parametrize("name", ["absent.censor", "bounds.absent"])
def test_absent_names_still_fail_lookup(package_root: Path, name: str) -> None:
    """
    Keep missing-module and missing-member failures visible
    """
    with pytest.raises(KeyError, match="absent"):
        get_object(f"lookup_pkg:{name}", dynamic=True)


def test_missing_runtime_values_keep_declaration_rules(package_root: Path) -> None:
    """
    Retain declarations while rejecting deleted runtime values
    """
    declaration = get_object("lookup_pkg:declaration", dynamic=True)
    assert declaration.name == "declaration"
    with pytest.raises(AttributeError, match="No attribute named `removed`"):
        get_object("lookup_pkg:removed", dynamic=True)


@pytest.mark.parametrize(
    ("package", "name", "expected"),
    [
        ("lookup_pkg", "lookup_pkg.bounds.censor", "lookup_pkg:bounds.censor"),
        ("lookup_pkg", "lookup_pkg_extra.censor", "lookup_pkg:lookup_pkg_extra.censor"),
        (None, "lookup_pkg.bounds:censor", "lookup_pkg.bounds:censor"),
        ("lookup_pkg", "lookup_pkg.bounds:censor", "lookup_pkg.bounds:censor"),
        ("lookup_pkg", "bounds:censor", "lookup_pkg.bounds:censor"),
        ("lookup_pkg:Widget", "method", "lookup_pkg:Widget.method"),
    ],
)
def test_reference_paths_preserve_package_boundaries(
    package: str | None, name: str, expected: str
) -> None:
    """
    Remove only a reference's own package prefix
    """
    assert _join_path(package, name) == expected


def test_qualified_references_have_the_same_categories(
    package_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Accept fully qualified entries when validating an installed package
    """
    monkeypatch.setattr("great_docs._reference.discovery._installed_version", lambda name: "1.0.0")
    package = griffe.load("lookup_pkg", search_paths=[package_root])
    relative = [{"title": "API", "contents": ["bounds.censor"]}]
    qualified = [{"title": "API", "contents": ["lookup_pkg.bounds.censor"]}]
    assert categorise_references(package, qualified) == categorise_references(package, relative)


@pytest.mark.parametrize("qualified", [False, True])
def test_dynamic_reference_build_uses_runtime_submodule_docs(
    package_root: Path, monkeypatch: pytest.MonkeyPatch, qualified: bool
) -> None:
    """
    Generate dynamic reference pages without a static-analysis retry
    """
    name = "lookup_pkg.bounds.censor" if qualified else "bounds.censor"
    write_config(
        package_root,
        {
            "module": "lookup_pkg",
            "dynamic": True,
            "reference": [{"title": "API", "contents": [name]}],
        },
    )
    docs = GreatDocs(project_path=str(package_root))
    docs._remote = StubRemote()
    monkeypatch.chdir(package_root)
    run = make_run(docs)
    prepare_build_directory(docs, run)
    monkeypatch.chdir(docs.layout.build_dir)
    stream = io.StringIO()
    outcome, ref = reference.api(run, docs._config, docs.layout, BuildLog(stream=stream))
    assert outcome == "API reference generated"
    assert ref is not None
    assert "retrying with static analysis" not in stream.getvalue()
    page = docs.layout.build_dir / "reference" / f"{name}.qmd"
    assert "Runtime censor documentation" in page.read_text(encoding="utf-8")
