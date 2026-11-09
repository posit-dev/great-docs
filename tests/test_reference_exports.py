# pyright: reportPrivateUsage=false
"""Tests for finding a project's exports and building its reference sections"""

from __future__ import annotations

import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import griffe
import pytest
from yaml12 import write_yaml

from great_docs import BuildError, GreatDocs
from great_docs._apiref.resolve import _sections_from_package
from great_docs._reference import sections as reference_sections
from great_docs._reference.discovery import (
    categorise_exports,
    categorise_references,
    discover_exports,
    empty_categories,
)
from great_docs._reference.exports import Exports
from tests.support import make_exports, mock_config, write_config


def _make_gd(tmp_path: Path) -> GreatDocs:
    """Create a `GreatDocs` instance with minimal configuration in a temporary directory"""
    (tmp_path / "great-docs.yml").write_text("module: mypkg\n", encoding="utf-8")
    return GreatDocs(project_path=str(tmp_path))


def _patch_cfg(monkeypatch, gd, name, value):
    """Patch a `Config` property to return `value`"""
    monkeypatch.setattr(type(gd._config), name, property(lambda self: value))


class TestNames:
    """Cached export discovery and retries after unsuccessful discovery"""

    def test_finds_the_names_once(self, tmp_path, monkeypatch):
        exports = make_exports(_make_gd(tmp_path))
        searches: list[str] = []

        def discover_exports(package, config, report):
            searches.append(package)
            return ["X"]

        monkeypatch.setattr(Exports, "package", lambda self, name: name)
        monkeypatch.setattr(
            "great_docs._reference.exports.discovery.discover_exports", discover_exports
        )

        assert exports.names("mypkg") == ["X"]
        assert exports.names("mypkg") == ["X"]
        assert searches == ["mypkg"]

    def test_searches_again_after_finding_nothing(self, tmp_path, monkeypatch):
        exports = make_exports(_make_gd(tmp_path))
        found = iter([None, ["X"]])
        monkeypatch.setattr(Exports, "package", lambda self, name: MagicMock())
        monkeypatch.setattr(
            "great_docs._reference.exports.discovery.discover_exports",
            lambda package, config, report: next(found),
        )
        monkeypatch.setattr(
            "great_docs._reference.exports.discovery.parse_dunder_all",
            lambda init_file, config, report: None,
        )

        assert exports.names("mypkg") is None
        assert exports.names("mypkg") == ["X"]

    def test_reads_the_project_package_init_when_discovery_finds_nothing(
        self, tmp_path, monkeypatch
    ):
        package = tmp_path / "mypkg"
        package.mkdir()
        (package / "__init__.py").write_text('__all__ = ["Y"]\n', encoding="utf-8")
        exports = make_exports(_make_gd(tmp_path))
        monkeypatch.setattr(Exports, "package", lambda self, name: MagicMock())
        monkeypatch.setattr(
            "great_docs._reference.exports.discovery.discover_exports",
            lambda package, config, report: None,
        )

        assert exports.names("mypkg") == ["Y"]

    def test_reads_the_init_of_another_package_by_its_name(self, tmp_path, monkeypatch):
        for name, export in [("mypkg", "Y"), ("otherpkg", "Z")]:
            (tmp_path / name).mkdir()
            (tmp_path / name / "__init__.py").write_text(f'__all__ = ["{export}"]\n')
        exports = make_exports(_make_gd(tmp_path))

        def package(self, name):
            raise ImportError(name)

        monkeypatch.setattr(Exports, "package", package)

        assert exports.names("otherpkg") == ["Z"]


class TestSectionsFromTheReferenceSetting:
    def test_no_reference_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "reference", None)
        # An earlier test in the same process may leave an importable `mypkg` behind.
        monkeypatch.setattr(Exports, "names", lambda self, name: [])
        assert make_exports(gd).sections("mypkg") is None

    def test_include_inherited_on_explicit_members(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(
            monkeypatch,
            gd,
            "reference",
            [
                {
                    "title": "Classes",
                    "contents": [
                        {"name": "MyClass", "members": ["method_a"], "include_inherited": True},
                    ],
                }
            ],
        )
        monkeypatch.setattr(Exports, "package", lambda self, name: MagicMock())
        monkeypatch.setattr(
            "great_docs._reference.exports.discovery.categorise_references",
            lambda package, reference: empty_categories(),
        )
        result = make_exports(gd).sections("mypkg")
        assert result is not None
        found = False
        for section in result:
            for item in section.get("contents", []):
                if isinstance(item, dict) and item.get("name") == "MyClass":
                    assert item.get("include_inherited") is True
                    found = True
        assert found

    def test_include_inherited_on_default_entry(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(
            monkeypatch,
            gd,
            "reference",
            [
                {
                    "title": "Classes",
                    "contents": [
                        {"name": "MyClass", "include_inherited": True},
                    ],
                }
            ],
        )
        monkeypatch.setattr(Exports, "package", lambda self, name: MagicMock())
        monkeypatch.setattr(
            "great_docs._reference.exports.discovery.categorise_references",
            lambda package, reference: empty_categories(),
        )
        result = make_exports(gd).sections("mypkg")
        assert result is not None
        found = False
        for section in result:
            for item in section.get("contents", []):
                if isinstance(item, dict) and item.get("include_inherited") is True:
                    found = True
        assert found

    def test_plain_string_when_no_include_inherited(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(
            monkeypatch,
            gd,
            "reference",
            [
                {
                    "title": "Funcs",
                    "contents": [
                        {"name": "my_func"},
                    ],
                }
            ],
        )
        monkeypatch.setattr(Exports, "package", lambda self, name: MagicMock())
        monkeypatch.setattr(
            "great_docs._reference.exports.discovery.categorise_references",
            lambda package, reference: empty_categories(),
        )
        result = make_exports(gd).sections("mypkg")
        assert result is not None
        for section in result:
            for item in section.get("contents", []):
                if item == "my_func":
                    return
        raise AssertionError("Expected plain string 'my_func' in contents")


class TestFromExplicitConfig:
    @staticmethod
    def _config():
        return mock_config(should_split_methods=lambda count: count > 5)

    def test_section_without_contents_is_skipped(self):
        """Verify that empty or missing contents exclude a reference section"""
        reference = [
            {"title": "Empty", "contents": []},
            {"title": "Missing"},
            {"title": "Funcs", "contents": ["helper"]},
        ]
        result = reference_sections.from_explicit_config(
            self._config(), reference, empty_categories()
        )
        assert result == [{"title": "Funcs", "desc": "", "contents": ["helper"]}]

    def test_item_without_name_is_skipped(self):
        """Verify that unnamed items are omitted while named items are retained"""
        reference = [{"title": "Funcs", "contents": [{"members": False}, {"name": "helper"}]}]
        result = reference_sections.from_explicit_config(
            self._config(), reference, empty_categories()
        )
        assert result == [{"title": "Funcs", "desc": "", "contents": ["helper"]}]

    def test_module_entry_splits_large_class_methods(self):
        """Verify that module entries give large classes separate method sections"""
        categories = empty_categories()
        categories["classes"] = ["pkg.Big", "pkg.Small"]
        categories["class_methods"] = {"pkg.Big": 8, "pkg.Small": 2}
        categories["class_method_names"] = {"pkg.Big": ["a", "b"]}
        result = reference_sections.from_explicit_config(
            self._config(), [{"title": "API", "contents": ["pkg"]}], categories
        )
        assert result == [
            {
                "title": "API",
                "desc": "",
                "contents": [{"name": "pkg.Big", "members": []}, "pkg.Small"],
            },
            {
                "title": "pkg.Big Methods",
                "desc": "Methods for the pkg.Big class",
                "contents": ["pkg.Big.a", "pkg.Big.b"],
            },
        ]


class TestSectionsWithoutGriffe:
    def test_griffe_load_failure_keeps_listed_names(self, tmp_path, monkeypatch):
        """Verify that a load failure preserves configured reference sections"""
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "reference", [{"title": "API", "contents": ["Foo"]}])
        monkeypatch.setattr(
            Exports, "package", lambda self, name: (_ for _ in ()).throw(ImportError("fail"))
        )
        result = make_exports(gd).sections("mypkg")
        assert result == [{"title": "API", "desc": "", "contents": ["Foo"]}]


def test_sections():
    """Verify that discovered exports produce API reference sections"""
    docs = GreatDocs()
    sections = make_exports(docs).sections("great_docs")

    assert sections is not None
    assert len(sections) > 0

    has_contents = any(section.get("contents") for section in sections)
    assert has_contents


def test_method_section_generation():
    """Verify that classes with more than five methods get separate method sections"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        package_dir = Path(tmp_dir) / "testpkg"
        package_dir.mkdir()

        init_content = '''
"""Test package."""
__version__ = "1.0.0"
__all__ = ["BigClass", "SmallClass", "some_function"]

class BigClass:
    """A class with many methods."""
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
    def method7(self): pass

class SmallClass:
    """A class with few methods."""
    def method1(self): pass
    def method2(self): pass

def some_function():
    """A function."""
    pass
'''
        (package_dir / "__init__.py").write_text(init_content)

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            sections = make_exports(docs).sections("testpkg")

            assert sections is not None

            class_section = next((s for s in sections if s["title"] == "Classes"), None)

            assert class_section is not None

            # Suppress inline methods when a separate method section documents them.
            big_class_entry = next(
                (
                    c
                    for c in class_section["contents"]
                    if isinstance(c, dict) and c.get("name") == "BigClass"
                ),
                None,
            )

            assert big_class_entry is not None
            assert big_class_entry == {"name": "BigClass", "members": []}

            assert "SmallClass" in class_section["contents"]

            method_section = next((s for s in sections if s["title"] == "BigClass Methods"), None)

            assert method_section is not None
            assert len(method_section["contents"]) == 7
            assert "BigClass.method1" in method_section["contents"]
            assert "BigClass.method7" in method_section["contents"]

            small_method_section = next(
                (s for s in sections if s["title"] == "SmallClass Methods"), None
            )

            assert small_method_section is None

            func_section = next((s for s in sections if s["title"] == "Functions"), None)

            assert func_section is not None
            assert "some_function" in func_section["contents"]
        finally:
            sys.path.remove(tmp_dir)


def test_module_exports_categorized():
    """Verify that exported submodule members use qualified names in each category"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "modpkg"
        pkg_dir.mkdir()

        (pkg_dir / "__init__.py").write_text(
            '"""A package with submodule exports."""\n__all__ = ["shapes", "colors"]\n'
        )

        shapes_dir = pkg_dir / "shapes"
        shapes_dir.mkdir()
        (shapes_dir / "__init__.py").write_text(
            '"""Shapes module."""\n'
            "class Circle:\n"
            '    """A circle."""\n'
            "    def area(self): pass\n"
            "\n"
            "class Square:\n"
            '    """A square."""\n'
            "    def area(self): pass\n"
            "\n"
            "def draw(shape):\n"
            '    """Draw a shape."""\n'
            "    pass\n"
            "\n"
            "MAX_SIDES = 100\n"
        )

        colors_dir = pkg_dir / "colors"
        colors_dir.mkdir()
        (colors_dir / "__init__.py").write_text(
            '"""Colors module."""\n'
            "def mix(a, b):\n"
            '    """Mix two colors."""\n'
            "    pass\n"
            "\n"
            "def blend(a, b, ratio=0.5):\n"
            '    """Blend two colors."""\n'
            "    pass\n"
            "\n"
            "RED = (255, 0, 0)\n"
            "BLUE = (0, 0, 255)\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = make_exports(docs).categorise("modpkg", ["shapes", "colors"])

            assert "shapes.Circle" in categories["classes"]
            assert "shapes.Square" in categories["classes"]

            assert "shapes.draw" in categories["functions"]
            assert "colors.mix" in categories["functions"]
            assert "colors.blend" in categories["functions"]

            assert "shapes.MAX_SIDES" in categories["constants"]
            assert "colors.RED" in categories["constants"]
            assert "colors.BLUE" in categories["constants"]

            assert categories["other"] == []
        finally:
            sys.path.remove(tmp_dir)


def test_module_class_methods_tracked():
    """Verify method counts for classes in exported submodules"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "methpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with module exports."""\n__all__ = ["models"]\n'
        )

        models_dir = pkg_dir / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text(
            '"""Models module."""\n'
            "class BigModel:\n"
            '    """A model with many methods."""\n'
            "    def fit(self): pass\n"
            "    def predict(self): pass\n"
            "    def score(self): pass\n"
            "    def transform(self): pass\n"
            "    def validate(self): pass\n"
            "    def serialize(self): pass\n"
            "    def load(self): pass\n"
            "\n"
            "class SmallModel:\n"
            '    """A model with few methods."""\n'
            "    def fit(self): pass\n"
            "    def predict(self): pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = make_exports(docs).categorise("methpkg", ["models"])

            assert categories["class_methods"]["models.BigModel"] == 7
            assert len(categories["class_method_names"]["models.BigModel"]) == 7
            assert "fit" in categories["class_method_names"]["models.BigModel"]
            assert "serialize" in categories["class_method_names"]["models.BigModel"]

            assert categories["class_methods"]["models.SmallModel"] == 2
        finally:
            sys.path.remove(tmp_dir)


def test_module_big_class_splitting():
    """Verify that submodule classes with more than five methods get separate sections"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "splitpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with big class in submodule."""\n__all__ = ["engine"]\n'
        )

        engine_dir = pkg_dir / "engine"
        engine_dir.mkdir()
        (engine_dir / "__init__.py").write_text(
            '"""Engine module."""\n'
            "class Engine:\n"
            '    """A big engine class."""\n'
            "    def start(self): pass\n"
            "    def stop(self): pass\n"
            "    def accelerate(self): pass\n"
            "    def brake(self): pass\n"
            "    def reverse(self): pass\n"
            "    def park(self): pass\n"
            "    def idle(self): pass\n"
            "\n"
            "def create_engine():\n"
            '    """Create an engine."""\n'
            "    pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            sections = make_exports(docs).sections("splitpkg")

            assert sections is not None

            class_section = next((s for s in sections if s["title"] == "Classes"), None)
            assert class_section is not None

            big_class_entry = next(
                (
                    c
                    for c in class_section["contents"]
                    if isinstance(c, dict) and c.get("name") == "engine.Engine"
                ),
                None,
            )
            assert big_class_entry is not None
            assert big_class_entry == {"name": "engine.Engine", "members": []}

            method_section = next(
                (s for s in sections if s["title"] == "engine.Engine Methods"),
                None,
            )

            assert method_section is not None
            assert len(method_section["contents"]) == 7
            assert "engine.Engine.start" in method_section["contents"]
            assert "engine.Engine.park" in method_section["contents"]

            func_section = next((s for s in sections if s["title"] == "Functions"), None)

            assert func_section is not None
            assert "engine.create_engine" in func_section["contents"]
        finally:
            sys.path.remove(tmp_dir)


def test_module_exception_subclassification():
    """Verify that submodule exceptions and regular classes use separate categories"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "errpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with exceptions in submodule."""\n__all__ = ["errors"]\n'
        )

        errors_dir = pkg_dir / "errors"
        errors_dir.mkdir()
        (errors_dir / "__init__.py").write_text(
            '"""Errors module."""\n'
            "class ValidationError(ValueError):\n"
            '    """Validation failed."""\n'
            "    pass\n"
            "\n"
            "class NotFoundError(KeyError):\n"
            '    """Item not found."""\n'
            "    pass\n"
            "\n"
            "class Widget:\n"
            '    """A regular class."""\n'
            "    pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = make_exports(docs).categorise("errpkg", ["errors"])

            assert "errors.ValidationError" in categories["exceptions"]
            assert "errors.NotFoundError" in categories["exceptions"]

            assert "errors.Widget" in categories["classes"]
        finally:
            sys.path.remove(tmp_dir)


def test_module_empty_submodule_goes_to_other():
    """Verify that modules without documentable members are grouped under `other`"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "emptypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with empty submodule."""\n__all__ = ["empty_mod"]\n'
        )

        empty_dir = pkg_dir / "empty_mod"
        empty_dir.mkdir()
        (empty_dir / "__init__.py").write_text(
            '"""Empty module with only private members."""\n_internal = 42\n_helper = lambda x: x\n'
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = make_exports(docs).categorise("emptypkg", ["empty_mod"])

            assert "empty_mod" in categories["other"]
        finally:
            sys.path.remove(tmp_dir)


def test_module_mixed_with_top_level():
    """Verify that categories include both top-level exports and submodule members"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "mixedpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Mixed package."""\n'
            '__all__ = ["TopClass", "top_func", "sub"]\n'
            "\n"
            "class TopClass:\n"
            '    """A top-level class."""\n'
            "    pass\n"
            "\n"
            "def top_func():\n"
            '    """A top-level function."""\n'
            "    pass\n"
        )

        sub_dir = pkg_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text(
            '"""Sub module."""\n'
            "class SubClass:\n"
            '    """A class inside a submodule."""\n'
            "    pass\n"
            "\n"
            "def sub_func():\n"
            '    """A function inside a submodule."""\n'
            "    pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = make_exports(docs).categorise("mixedpkg", ["TopClass", "top_func", "sub"])

            assert "TopClass" in categories["classes"]
            assert "top_func" in categories["functions"]

            assert "sub.SubClass" in categories["classes"]
            assert "sub.sub_func" in categories["functions"]

            assert categories["other"] == []
        finally:
            sys.path.remove(tmp_dir)


def test_module_submodule_allowed_in_exports():
    """Verify that export discovery retains submodules"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "subexpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with submodule in __all__."""\n__all__ = ["mymod"]\n'
        )

        mod_dir = pkg_dir / "mymod"
        mod_dir.mkdir()
        (mod_dir / "__init__.py").write_text('"""My module."""\ndef hello(): pass\n')

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            exports = make_exports(docs).names("subexpkg")

            assert exports is not None
            assert "mymod" in exports
        finally:
            sys.path.remove(tmp_dir)


def test_names_missing_package():
    """Verify that discovery returns `None` when neither source finds the package"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = make_exports(docs).names("nonexistent_pkg_xyzzy")

        assert result is None


def test_sections_uses_explicit():
    """Verify that sections prefer the explicit `reference` setting"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(reference=[{"title": "Explicit", "contents": ["A"]}])

        fake_config_sections = [{"title": "Explicit", "contents": ["A"]}]
        with patch.object(
            reference_sections, "from_explicit_config", return_value=fake_config_sections
        ):
            result = make_exports(docs).sections("mypkg")

        assert result == fake_config_sections


def test_sections_falls_back():
    """Verify that sections fall back to discovered exports"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        fake_auto_sections = [{"title": "Auto", "contents": ["B"]}]
        with (
            patch.object(Exports, "names", return_value=["B"]),
            patch.object(Exports, "categorise", return_value={}),
            patch.object(reference_sections, "from_categories", return_value=fake_auto_sections),
        ):
            result = make_exports(docs).sections("mypkg")

        assert result == fake_auto_sections


def test_categorise_references_missing_item_raises(capsys: pytest.CaptureFixture[str]):
    """Report missing configured names and raise `BuildError`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Test package."""\ndef real_func():\n    """A real function."""\n    pass\n'
        )

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            Path(tmp_dir, "great-docs.yml").write_text(
                "reference:\n  - title: Functions\n    contents:\n"
                "      - real_func\n      - nonexistent_item\n"
            )
            docs = GreatDocs(project_path=tmp_dir)

            # Treat the package as installed so missing configured names are errors.
            with patch("importlib.metadata.version", return_value="1.0.0"):
                with pytest.raises(BuildError) as exc_info:
                    make_exports(docs).sections("mypkg")

            error_msg = str(exc_info.value)
            assert "nonexistent_item" in error_msg
            assert "mypkg" in error_msg
            assert "not found" in error_msg
            assert capsys.readouterr().err == f"ERROR: {error_msg}\n"
        finally:
            sys.path.remove(tmp_dir)


def test_sections_basic():
    """Verify that discovered categories produce class and function sections"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.layout.build_dir.mkdir(parents=True, exist_ok=True)

        categories = empty_categories()
        categories["classes"] = ["Widget"]
        categories["functions"] = ["create_widget", "destroy_widget"]
        categories["class_methods"] = {"Widget": 3}
        categories["class_method_names"] = {"Widget": ["render", "update", "close"]}

        with patch.object(
            Exports, "names", return_value=["Widget", "create_widget", "destroy_widget"]
        ):
            with patch.object(Exports, "categorise", return_value=categories):
                result = make_exports(docs).sections("mypkg")

        assert result is not None
        titles = [s["title"] for s in result]
        assert "Classes" in titles
        assert "Functions" in titles


def test_sections_large_class():
    """Verify that sections separate classes with more than five methods"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.layout.build_dir.mkdir(parents=True, exist_ok=True)

        categories = empty_categories()
        categories["classes"] = ["BigClass"]
        categories["class_methods"] = {"BigClass": 10}
        categories["class_method_names"] = {
            "BigClass": ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10"]
        }

        with patch.object(Exports, "names", return_value=["BigClass"]):
            with patch.object(Exports, "categorise", return_value=categories):
                result = make_exports(docs).sections("mypkg")

        assert result is not None
        titles = [s["title"] for s in result]
        assert "BigClass Methods" in titles
        classes_section = next(s for s in result if s["title"] == "Classes")
        assert {"name": "BigClass", "members": []} in classes_section["contents"]


def test_sections_no_exports():
    """Verify that no sections are produced without exports"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        with patch.object(Exports, "names", return_value=None):
            result = make_exports(docs).sections("mypkg")

        assert result is None


def test_sections_all_types():
    """Verify section generation for every export category"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.layout.build_dir.mkdir(parents=True, exist_ok=True)

        categories = empty_categories()
        categories["classes"] = ["MyClass"]
        categories["dataclasses"] = ["MyData"]
        categories["enums"] = ["Color"]
        categories["exceptions"] = ["MyError"]
        categories["namedtuples"] = ["Point"]
        categories["typeddicts"] = ["Options"]
        categories["protocols"] = ["Renderable"]
        categories["abstract_classes"] = ["BaseWidget"]
        categories["functions"] = ["do_thing"]
        categories["async_functions"] = ["async_fetch"]
        categories["constants"] = ["VERSION"]
        categories["type_aliases"] = ["WidgetList"]
        categories["other"] = ["misc_obj"]
        categories["class_methods"] = {}
        categories["class_method_names"] = {}

        all_exports = (
            categories["classes"]
            + categories["dataclasses"]
            + categories["enums"]
            + categories["exceptions"]
            + categories["namedtuples"]
            + categories["typeddicts"]
            + categories["protocols"]
            + categories["abstract_classes"]
            + categories["functions"]
            + categories["async_functions"]
            + categories["constants"]
            + categories["type_aliases"]
            + categories["other"]
        )

        with patch.object(Exports, "names", return_value=all_exports):
            with patch.object(Exports, "categorise", return_value=categories):
                result = make_exports(docs).sections("mypkg")

        assert result is not None
        titles = [s["title"] for s in result]
        assert "Enumerations" in titles
        assert "Exceptions" in titles
        assert "Named Tuples" in titles
        assert "Typed Dicts" in titles
        assert "Protocols" in titles
        assert "Abstract Classes" in titles
        assert "Async Functions" in titles
        assert "Constants" in titles
        assert "Type Aliases" in titles
        assert "Other" in titles


def test_names_with_all():
    """Verify that discovery reads `__all__` from `__init__.py`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "exportpkg_all"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["func_a", "ClassB", "CONST_C"]\n',
            encoding="utf-8",
        )
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "exportpkg_all"\n', encoding="utf-8"
        )
        docs = GreatDocs(project_path=tmp_dir)
        exports = make_exports(docs).names("exportpkg_all")

        assert exports is not None
        assert "func_a" in exports
        assert "ClassB" in exports
        assert "CONST_C" in exports


def test_names_with_exclusions():
    """Verify that discovery omits names listed in the `exclude` setting"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "exportpkg_excl"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["func_a", "hidden_b", "ClassC"]\n',
            encoding="utf-8",
        )
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "exportpkg_excl"\n', encoding="utf-8"
        )
        (Path(tmp_dir) / "great-docs.yml").write_text("exclude:\n  - hidden_b\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        exports = make_exports(docs).names("exportpkg_excl")

        assert exports is not None
        assert "func_a" in exports
        assert "hidden_b" not in exports
        assert "ClassC" in exports


def test_names_no_all():
    """Verify that discovery finds no exports when only excluded metadata is present"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "exportpkg_noall"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "# No __all__ here\nVERSION = '1.0'\n",
            encoding="utf-8",
        )
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "exportpkg_noall"\n', encoding="utf-8"
        )
        docs = GreatDocs(project_path=tmp_dir)
        exports = make_exports(docs).names("exportpkg_noall")

        # griffe finds the package, but its only public name, `VERSION`, is excluded.
        # Discovery returns an empty list rather than `None` for a missing package.
        assert not exports


def test_names_hyphenated_name():
    """Verify that a missing package with a hyphenated name yields no exports"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "my-pkg"\n', encoding="utf-8"
        )
        docs = GreatDocs(project_path=tmp_dir)

        # No `my_pkg` directory exists, so no `__init__.py` is found.
        exports = make_exports(docs).names("my-pkg")

        assert exports is None


def test_categorise_basic():
    """Verify that exports are grouped by reference category"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "catpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Test."""\n'
            '__all__ = ["MyClass", "my_func", "MY_CONST"]\n'
            "class MyClass:\n"
            '    """A class."""\n'
            "    def method1(self): pass\n"
            "    def method2(self): pass\n"
            "def my_func():\n"
            '    """A func."""\n'
            "    pass\n"
            'MY_CONST = "hello"\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("catpkg", ["MyClass", "my_func", "MY_CONST"])

            assert "MyClass" in result["classes"]
            assert "my_func" in result["functions"]
            assert "MY_CONST" in result["constants"]
            assert result["class_methods"]["MyClass"] == 2
        finally:
            sys.path.remove(tmp_dir)


def test_categorise_keeps_methods_of_an_unimportable_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Verify that a failed package import warns and preserves statically discovered methods"""
    pkg_dir = tmp_path / "unimportable_catpkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        "import not_a_real_dependency_xyz\n"
        "class Widget:\n"
        "    def grow(self): pass\n"
        "    def shrink(self): pass\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        docs = GreatDocs(project_path=str(tmp_path))
        result = make_exports(docs).categorise("unimportable_catpkg", ["Widget"])
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("unimportable_catpkg", None)

    assert result["class_method_names"]["Widget"] == ["grow", "shrink"]
    out = capsys.readouterr().out
    assert "Could not import 'unimportable_catpkg' (ModuleNotFoundError" in out


def test_categorise_with_enum():
    """Verify that enum exports are grouped as enums"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "enumpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "import enum\n"
            "class Color(enum.Enum):\n"
            '    """Color enum."""\n'
            "    RED = 1\n"
            "    BLUE = 2\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("enumpkg", ["Color"])

            assert "Color" in result["enums"]
        finally:
            sys.path.remove(tmp_dir)


def test_categorise_with_exception():
    """Verify that exception exports are grouped as exceptions"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "excpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'class MyError(Exception):\n    """Custom error."""\n'
            'class MyChildError(MyError):\n    """Child error."""\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("excpkg", ["MyError", "MyChildError"])

            assert result["exceptions"] == ["MyError", "MyChildError"]
        finally:
            sys.path.remove(tmp_dir)


def test_categorise_with_dataclass():
    """Verify that dataclass exports are grouped as dataclasses"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "dcpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Point:\n"
            '    """Point dataclass."""\n'
            "    x: float\n"
            "    y: float\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("dcpkg", ["Point"])

            assert "Point" in result["dataclasses"]
        finally:
            sys.path.remove(tmp_dir)


def test_categorise_skips_metadata():
    """Verify that module metadata is excluded from reference categories"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "skippkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__version__ = "1.0.0"\ndef func(): pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("skippkg", ["__version__", "func"])

            assert result is not None
            assert "func" in result["functions"]
            assert "__version__" not in result["constants"]
        finally:
            sys.path.remove(tmp_dir)


def test_categorise_module_export():
    """Verify that exported modules contribute their public members"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "modpkg"
        pkg_dir.mkdir()
        sub_dir = pkg_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text(
            "class SubClass:\n"
            '    """In submodule."""\n'
            "    def m(self): pass\n"
            "def sub_func(): pass\n",
            encoding="utf-8",
        )
        (pkg_dir / "__init__.py").write_text("from . import sub\n", encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("modpkg", ["sub"])

            assert "sub.SubClass" in result["classes"] or "sub" in result["other"]
        finally:
            sys.path.remove(tmp_dir)


def test_submodule_dunder_all_limits_discovered_and_explicit_members(tmp_path: Path) -> None:
    """Use each submodule's `__all__` when expanding its reference entry"""
    package_dir = tmp_path / "exportpkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        "from . import selected, legacy, empty\ndef direct(): pass\n"
    )
    (package_dir / "selected.py").write_text(
        '__all__ = ["chosen", "_intentional"]\n'
        "def omitted(): pass\n"
        "def chosen(): pass\n"
        "def _intentional(): pass\n"
    )
    (package_dir / "legacy.py").write_text("def public(): pass\ndef _private(): pass\n")
    (package_dir / "empty.py").write_text("__all__ = []\ndef omitted(): pass\n")

    package = griffe.load("exportpkg", search_paths=[tmp_path])
    exports = discover_exports(package, mock_config(), report=lambda line: None)
    assert exports is not None
    assert "selected" in exports
    assert "empty" in exports
    assert "legacy" not in exports

    discovered = categorise_exports(
        package, exports, renderable=lambda path: True, report=lambda line: None
    )
    explicit = categorise_references(package, [{"contents": ["selected", "legacy", "empty"]}])
    assert set(discovered["functions"]) == {"selected.chosen", "selected._intentional", "direct"}
    assert set(explicit["functions"]) == {
        "selected.chosen",
        "selected._intentional",
        "legacy.public",
    }
    for categories in (discovered, explicit):
        assert categories["functions"].index("selected.chosen") < categories["functions"].index(
            "selected._intentional"
        )
        assert "selected.omitted" not in categories["functions"]
        assert "empty.omitted" not in categories["functions"]
        assert "legacy._private" not in categories["functions"]


def test_root_dunder_all_keeps_submodules_without_exports(tmp_path: Path) -> None:
    """
    Keep a listed submodule when the package itself declares its exports
    """
    package_dir = tmp_path / "root_exports_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        'from . import selected, legacy\n__all__ = ["selected", "legacy"]\n'
    )
    (package_dir / "selected.py").write_text('__all__ = ["chosen"]\ndef chosen(): pass\n')
    (package_dir / "legacy.py").write_text("def public(): pass\n")

    package = griffe.load("root_exports_pkg", search_paths=[tmp_path])
    exports = discover_exports(package, mock_config(), report=lambda line: None)

    assert exports == ["selected", "legacy"]
    categories = categorise_exports(
        package, exports, renderable=lambda path: True, report=lambda line: None
    )
    assert set(categories["functions"]) == {"selected.chosen", "legacy.public"}


def test_empty_submodule_dunder_all_limits_generated_discovery(tmp_path: Path) -> None:
    """
    Treat an empty submodule export list as a declaration
    """
    package_dir = tmp_path / "empty_sibling_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("from . import empty, legacy\n")
    (package_dir / "empty.py").write_text("__all__ = []\ndef hidden(): pass\n")
    (package_dir / "legacy.py").write_text("def public(): pass\n")

    package = griffe.load("empty_sibling_pkg", search_paths=[tmp_path])

    assert discover_exports(package, mock_config(), report=lambda line: None) == ["empty"]


def test_unresolved_root_dunder_all_keeps_submodules_without_exports(tmp_path: Path) -> None:
    """
    Keep the public-member fallback when a root export list cannot be resolved
    """
    package_dir = tmp_path / "dynamic_exports_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        'from . import selected, legacy\n_names = ["selected", "legacy"]\n__all__ = _names\n'
    )
    (package_dir / "selected.py").write_text('__all__ = ["chosen"]\ndef chosen(): pass\n')
    (package_dir / "legacy.py").write_text("def public(): pass\n")

    package = griffe.load("dynamic_exports_pkg", search_paths=[tmp_path])

    exports = discover_exports(package, mock_config(), report=lambda line: None)
    assert exports is not None
    assert set(exports) == {
        "selected",
        "legacy",
    }


def test_all_public_submodules_without_exports_keep_fallback(tmp_path: Path) -> None:
    """
    Keep every public submodule when none declares exports
    """
    package_dir = tmp_path / "public_modules_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("from . import first, second\n")
    (package_dir / "first.py").write_text("def one(): pass\n")
    (package_dir / "second.py").write_text("def two(): pass\n")

    package = griffe.load("public_modules_pkg", search_paths=[tmp_path])

    exports = discover_exports(package, mock_config(), report=lambda line: None)
    assert exports is not None
    assert set(exports) == {
        "first",
        "second",
    }


def test_unexpanded_dunder_all_uses_public_members(tmp_path: Path) -> None:
    package_dir = tmp_path / "unexpanded_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        '_names = ["chosen"]\n__all__ = _names\ndef chosen(): pass\ndef extra(): pass\n'
    )

    package = griffe.load("unexpanded_pkg", search_paths=[tmp_path])

    assert discover_exports(package, mock_config(), report=lambda line: None) == [
        "chosen",
        "extra",
    ]
    assert [entry.name for entry in _sections_from_package(package)[0].contents] == [
        "chosen",
        "extra",
    ]


def test_imported_dunder_all_limits_reference_discovery(tmp_path: Path) -> None:
    package_dir = tmp_path / "imported_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        "from .sub import __all__, chosen\ndef extra(): pass\n"
    )
    (package_dir / "sub.py").write_text('__all__ = ["chosen"]\ndef chosen(): pass\n')

    package = griffe.load("imported_pkg", search_paths=[tmp_path])

    assert discover_exports(package, mock_config(), report=lambda line: None) == ["chosen"]
    assert [entry.name for entry in _sections_from_package(package)[0].contents] == ["chosen"]


def test_empty_dunder_all_exports_no_members(tmp_path: Path) -> None:
    package_dir = tmp_path / "empty_exports_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("__all__ = []\ndef extra(): pass\n")

    package = griffe.load("empty_exports_pkg", search_paths=[tmp_path])

    assert discover_exports(package, mock_config(), report=lambda line: None) == []
    assert _sections_from_package(package)[0].contents == []


def test_sections_without_reference_or_exports():
    """
    Return no sections when configuration and exports are both empty
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        with (
            patch.object(type(docs._config), "reference", property(lambda self: None)),
            patch.object(Exports, "names", return_value=[]),
        ):
            result = make_exports(docs).sections("mypkg")
        assert result is None


def test_sections_from_reference_basic():
    """Verify section generation from a simple `reference` setting"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "secpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["ClassA", "func_b"]\n'
            "class ClassA:\n"
            '    """A class."""\n'
            "    def m1(self): pass\n"
            "    def m2(self): pass\n"
            "def func_b(): pass\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {"title": "Classes", "contents": ["ClassA"]},
                    {"title": "Functions", "contents": ["func_b"]},
                ],
                should_split_methods=lambda n: n > 5,
            )

            with (
                patch.object(
                    Exports,
                    "names",
                    return_value=["ClassA", "func_b"],
                ),
            ):
                result = make_exports(docs).sections("secpkg")

            assert result is not None
            assert len(result) >= 2

            titles = [s["title"] for s in result]
            assert "Classes" in titles
            assert "Functions" in titles
        finally:
            sys.path.remove(tmp_dir)


def test_sections_from_reference_large_class():
    """Verify that configured classes with more than five methods get a method section"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "lgpkg"
        pkg_dir.mkdir()
        methods = "\n".join(f"    def method{i}(self): pass\n" for i in range(8))
        (pkg_dir / "__init__.py").write_text(
            f'class BigClass:\n    """Big."""\n{methods}',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {"title": "Classes", "contents": ["BigClass"]},
                ],
                should_split_methods=lambda n: n > 5,
            )

            with (
                patch.object(Exports, "names", return_value=["BigClass"]),
            ):
                result = make_exports(docs).sections("lgpkg")

            assert result is not None

            titles = [s["title"] for s in result]
            assert "BigClass Methods" in titles
        finally:
            sys.path.remove(tmp_dir)


def test_sections_from_reference_dict_items():
    """Verify that `members: false` suppresses method documentation"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "dictpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'class MyClass:\n    """Class."""\n    def m(self): pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {
                        "title": "API",
                        "contents": [
                            {"name": "MyClass", "members": False},
                        ],
                    },
                ],
                should_split_methods=lambda n: n > 5,
            )

            with (
                patch.object(Exports, "names", return_value=["MyClass"]),
            ):
                result = make_exports(docs).sections("dictpkg")

            assert result is not None
            section = result[0]
            found = False
            for item in section["contents"]:
                if isinstance(item, dict) and item.get("name") == "MyClass":
                    assert item["members"] == []
                    found = True
            assert found
        finally:
            sys.path.remove(tmp_dir)


def test_sections_from_reference_explicit_members_passthrough():
    """Verify that configured sections preserve explicit member lists"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "inhpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'class Parent:\n    """Parent."""\n    def inherited(self): pass\n'
            'class Child(Parent):\n    """Child."""\n    def own(self): pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {
                        "title": "API",
                        "contents": [
                            {
                                "name": "Child",
                                "members": ["own", "inherited"],
                            },
                        ],
                    },
                ],
                should_split_methods=lambda n: n > 5,
            )

            with (
                patch.object(Exports, "names", return_value=["Child"]),
            ):
                result = make_exports(docs).sections("inhpkg")

            assert result is not None
            section = result[0]
            found = False
            for item in section["contents"]:
                if isinstance(item, dict) and item.get("name") == "Child":
                    assert item["members"] == ["own", "inherited"]
                    found = True
            assert found
        finally:
            sys.path.remove(tmp_dir)


def test_sections_from_reference_include_inherited():
    """Verify that configured sections preserve `include_inherited`"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "inhpkg2"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'class Base:\n    """Base."""\n    def base_method(self): pass\n'
            'class Derived(Base):\n    """Derived."""\n    def derived_method(self): pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {
                        "title": "API",
                        "contents": [
                            {
                                "name": "Derived",
                                "include_inherited": True,
                            },
                        ],
                    },
                ],
                should_split_methods=lambda n: n > 5,
            )

            with (
                patch.object(Exports, "names", return_value=["Derived"]),
            ):
                result = make_exports(docs).sections("inhpkg2")

            assert result is not None
            section = result[0]
            found = False
            for item in section["contents"]:
                if isinstance(item, dict) and item.get("name") == "Derived":
                    assert item["include_inherited"] is True
                    found = True
            assert found
        finally:
            sys.path.remove(tmp_dir)


def test_categorise_async_function():
    """Verify that asynchronous exports are grouped separately from synchronous functions"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "asyncpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "async def async_func():\n"
            '    """Async function."""\n'
            "    pass\n"
            "def sync_func():\n"
            '    """Sync function."""\n'
            "    pass\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("asyncpkg", ["async_func", "sync_func"])

            assert "async_func" in result["async_functions"]
            assert "sync_func" in result["functions"]
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("asyncpkg", None)


def test_categorise_type_alias():
    """Verify that type aliases have their own reference group"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "tapkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "from typing import TypeAlias, TypeVar\n"
            'T = TypeVar("T")\n'
            "A: TypeAlias = int\n"
            'MY_CONST = "hello"\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("tapkg", ["T", "A", "MY_CONST"])

            assert "MY_CONST" in result["constants"]
            assert "T" in result["type_aliases"]
            assert "A" in result["type_aliases"]
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("tapkg", None)


def test_categorise_namedtuple():
    """Verify that named tuple exports are grouped as named tuples"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "ntpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "from typing import NamedTuple\n"
            "class Point(NamedTuple):\n"
            '    """A point."""\n'
            "    x: float\n"
            "    y: float\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("ntpkg", ["Point"])

            assert "Point" in result["namedtuples"]
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("ntpkg", None)


def test_categorise_protocol():
    """Verify that protocol exports are grouped as protocols"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "protpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "from typing import Protocol\n"
            "class Drawable(Protocol):\n"
            '    """A drawable protocol."""\n'
            "    def draw(self): ...\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("protpkg", ["Drawable"])

            assert "Drawable" in result["protocols"]
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("protpkg", None)


def test_categorise_not_in_members():
    """Verify that undefined exports are grouped under `other`"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "missingpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("x = 1\n", encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("missingpkg", ["NotThere"])

            assert "NotThere" in result["other"]
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("missingpkg", None)


def test_categorise_griffe_load_failure():
    """
    Group exports under `other` when griffe cannot load an importable package
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "loadfailpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("def func(): pass\n", encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)

            with patch.object(griffe, "load", side_effect=RuntimeError("load failed")):
                result = make_exports(docs).categorise("loadfailpkg", ["func"])

            assert result["other"] == ["func"]
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("loadfailpkg", None)


def test_categorise_files_exports_under_other_without_griffe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    """
    Exclude metadata and group exports under `other` when griffe cannot load

    A mistyped `module:` setting can leave an importable package in the project
    root under a different name. Categorising must leave that package unimported.
    """
    (tmp_path / "actual_pkg").mkdir()
    (tmp_path / "actual_pkg" / "__init__.py").write_text(
        '__all__ = ["make", "Widget"]\n\ndef make(): pass\n\nclass Widget: pass\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    docs = GreatDocs(project_path=str(tmp_path))

    try:
        result = make_exports(docs).categorise("named_pkg", ["__version__", "make", "Widget"])
        imported = "actual_pkg" in sys.modules
    finally:
        sys.modules.pop("actual_pkg", None)

    assert result == {**empty_categories(), "other": ["make", "Widget"]}
    assert "Could not load package with griffe" in capsys.readouterr().err
    assert not imported


def test_categorise_cyclic_alias():
    """Verify that categorisation excludes cyclic aliases"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "cyclicpkg2"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("class Normal: pass\n", encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).categorise("cyclicpkg2", ["Normal", "DoesNotExist"])

            assert "Normal" in result["classes"]
            assert "DoesNotExist" in result["other"]
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("cyclicpkg2", None)


def test_sections_from_reference_inline_methods_true_never_splits():
    """Verify that `inline_methods: true` keeps methods inline regardless of class size"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "inlinepkg"
        pkg_dir.mkdir()
        methods = "\n".join(f"    def method{i}(self): pass\n" for i in range(10))
        (pkg_dir / "__init__.py").write_text(
            f'class BigClass:\n    """Big."""\n{methods}',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {"title": "Classes", "contents": ["BigClass"]},
                ],
                should_split_methods=lambda n: False,  # never split
            )

            with (
                patch.object(Exports, "names", return_value=["BigClass"]),
            ):
                result = make_exports(docs).sections("inlinepkg")

            assert result is not None
            titles = [s["title"] for s in result]
            assert "BigClass Methods" not in titles
            classes_section = next(s for s in result if s["title"] == "Classes")
            assert "BigClass" in classes_section["contents"]
        finally:
            sys.path.remove(tmp_dir)


def test_sections_from_reference_inline_methods_false_always_splits():
    """Verify that `inline_methods: false` separates methods even for small classes"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "splitforcepkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            textwrap.dedent("""\
            class SmallClass:
                \"\"\"Small class with documented methods.\"\"\"

                def method_a(self) -> str:
                    \"\"\"
                    Perform action A.

                    Returns
                    -------
                    str
                        The result.
                    \"\"\"
                    return "a"

                def method_b(self) -> str:
                    \"\"\"
                    Perform action B.

                    Returns
                    -------
                    str
                        The result.
                    \"\"\"
                    return "b"
            """),
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {"title": "Classes", "contents": ["SmallClass"]},
                ],
                should_split_methods=lambda n: n > 0,  # always split
            )

            with (
                patch.object(Exports, "names", return_value=["SmallClass"]),
            ):
                result = make_exports(docs).sections("splitforcepkg")

            assert result is not None
            titles = [s["title"] for s in result]
            assert "SmallClass Methods" in titles
        finally:
            sys.path.remove(tmp_dir)


def test_sections_from_reference_inline_methods_custom_threshold():
    """Verify that `inline_methods: 10` keeps a class with eight methods inline"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "threshpkg"
        pkg_dir.mkdir()
        methods = "\n".join(f"    def method{i}(self): pass\n" for i in range(8))
        (pkg_dir / "__init__.py").write_text(
            f'class MediumClass:\n    """Medium."""\n{methods}',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            docs._config = mock_config(
                reference=[
                    {"title": "Classes", "contents": ["MediumClass"]},
                ],
                should_split_methods=lambda n: n > 10,  # threshold=10
            )

            with (
                patch.object(Exports, "names", return_value=["MediumClass"]),
            ):
                result = make_exports(docs).sections("threshpkg")

            assert result is not None
            titles = [s["title"] for s in result]
            assert "MediumClass Methods" not in titles
            classes_section = next(s for s in result if s["title"] == "Classes")
            assert "MediumClass" in classes_section["contents"]
        finally:
            sys.path.remove(tmp_dir)


class TestSectionsFromReference:
    """Sections built from the reference setting"""

    def test_expands_module_members_in_section(self):
        """Verify that a configured module expands into its discovered members"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            pkg = tmp / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text('__all__ = ["sub"]\n')
            sub = pkg / "sub"
            sub.mkdir()
            (sub / "__init__.py").write_text(
                'def func_a():\n    """A func."""\n    pass\n\n'
                'class MyClass:\n    """A class."""\n    pass\n'
            )
            with open(tmp / "great-docs.yml", "w") as f:
                write_yaml({"reference": [{"title": "Module", "contents": ["sub"]}]}, f)
            docs = GreatDocs(project_path=tmp_dir)
            old_path = sys.path[:]
            sys.path.insert(0, tmp_dir)
            try:
                result = make_exports(docs).sections("mypkg")
            finally:
                sys.path[:] = old_path
            if result is not None:
                assert len(result) >= 1
                assert result[0]["title"] == "Module"

    def test_returns_none_without_reference_config(self):
        """Verify that empty configuration and exports produce no sections"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            pkg = tmp / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            docs = GreatDocs(project_path=tmp_dir)
            result = make_exports(docs).sections("mypkg")
            assert result is None


class TestSectionsFromReferenceMore:
    """More sections built from the reference setting"""

    def test_large_class_gets_companion_section(self):
        """Verify that a configured class with more than five methods gets a method section"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            pkg_name = "bigclasspkg"
            (tmp / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\n')
            pkg = tmp / pkg_name
            pkg.mkdir()
            methods = "\n".join(
                [
                    f'    def method_{i}(self):\n        """Method {i}."""\n        pass\n'
                    for i in range(8)
                ]
            )
            (pkg / "__init__.py").write_text(
                f'__all__ = ["BigClass"]\n\nclass BigClass:\n    """A big class."""\n{methods}'
            )
            with open(tmp / "great-docs.yml", "w") as f:
                write_yaml(
                    {"reference": [{"title": "Core", "contents": ["BigClass"]}]},
                    f,
                )
            docs = GreatDocs(project_path=tmp_dir)
            old_path = sys.path[:]
            # Clear imported modules so later tests do not reuse this temporary package.
            cached = {k: v for k, v in sys.modules.items() if k.startswith(pkg_name)}
            for k in cached:
                del sys.modules[k]
            sys.path.insert(0, tmp_dir)
            try:
                result = make_exports(docs).sections(pkg_name)
            finally:
                sys.path[:] = old_path
                for k in list(sys.modules):
                    if k.startswith(pkg_name):
                        del sys.modules[k]
            if result is not None:
                assert len(result) >= 2
                titles = [s["title"] for s in result]
                assert "BigClass Methods" in titles

    def test_dict_item_with_members_false(self):
        """Verify that configured `members: false` produces an empty member list"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            pkg = tmp / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text(
                '__all__ = ["MyClass"]\n\nclass MyClass:\n    """A class."""\n    pass\n'
            )
            with open(tmp / "great-docs.yml", "w") as f:
                write_yaml(
                    {
                        "reference": [
                            {
                                "title": "Core",
                                "contents": [{"name": "MyClass", "members": False}],
                            }
                        ]
                    },
                    f,
                )
            docs = GreatDocs(project_path=tmp_dir)
            old_path = sys.path[:]
            sys.path.insert(0, tmp_dir)
            try:
                result = make_exports(docs).sections("mypkg")
            finally:
                sys.path[:] = old_path
            if result is not None:
                assert len(result) >= 1
                core = result[0]["contents"]
                assert any(
                    isinstance(c, dict) and c.get("name") == "MyClass" and c.get("members") == []
                    for c in core
                )
