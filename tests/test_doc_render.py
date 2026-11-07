"""Tests for great_docs._apiref._render.doc."""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import griffe as gf

import great_docs._apiref._render.doc as docmod
from great_docs._apiref._render.doc import RenderDoc
from great_docs._apiref._settings import Settings, SourceLinks


def _get_private_cls():
    """Access the name-mangled __RenderDoc class."""
    return vars(docmod)["__RenderDoc"]


class TestRenderAnnotationTildePrefix:
    def test_tilde_prefix_returns_canonical_name(self):
        """When canonical_path starts with '~', returns canonical_name."""
        cls = _get_private_cls()

        mock_expr = MagicMock(spec=gf.Expr)
        mock_expr.canonical_path = "~mod.sub.Widget"
        mock_expr.canonical_name = "Widget"

        fake_attr = MagicMock(spec=gf.Attribute)
        fake_attr.annotation = mock_expr
        fake_attr.kind = gf.Kind("attribute")

        fake_self = types.SimpleNamespace(obj=fake_attr)

        result = cls.__dict__["render_annotation"](fake_self, annotation=mock_expr)
        assert "Widget" in result


class TestRenderModulesSection:
    def test_modules_section_suppressed(self):
        """render_modules_section returns None."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace(_suppress_section=lambda el: None)
        el = MagicMock(spec=gf.DocstringSectionModules)

        result = cls.render_modules_section(fake_self, el)
        assert result is None


class TestRenderExampleFragment:
    def test_unrecognized_fragment_returns_empty(self):
        """When fragment is not ExampleCode or ExampleText, returns ''."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        with patch("great_docs._apiref._render.doc.transform", return_value="unexpected"):
            result = cls._render_example_fragment(fake_self, MagicMock())

        assert result == ""


class TestRenderAdmonitionSection:
    def test_returns_description(self):
        """render_admonition_section returns el.value.description."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock(spec=gf.DocstringSectionAdmonition)
        el.value = MagicMock()
        el.value.description = "Be careful with this function."

        result = cls.render_admonition_section(fake_self, el)
        assert result == "Be careful with this function."


class TestRenderWarningsSection:
    def test_returns_value(self):
        """render_warnings_section returns el.value."""
        from great_docs._apiref._docstring_sections import DocstringSectionWarnings

        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock(spec=DocstringSectionWarnings)
        el.value = "This may cause data loss."

        result = cls.render_warnings_section(fake_self, el)
        assert result == "This may cause data loss."


class TestRenderNotesSection:
    def test_returns_value(self):
        """render_notes_section returns el.value."""
        from great_docs._apiref._docstring_sections import DocstringSectionNotes

        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock(spec=DocstringSectionNotes)
        el.value = "Implementation uses Cython internally."

        result = cls.render_notes_section(fake_self, el)
        assert result == "Implementation uses Cython internally."


class TestRenderSeeAlsoSectionSkipEmpty:
    def test_empty_lines_skipped(self):
        """Empty lines in see_also content are skipped."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock()
        el.value = [("func_a", "Description A")]
        with patch(
            "great_docs._apiref._render.doc.format_see_also",
            return_value="foo:description\n\nbar:other description",
        ):
            result = cls.render_see_also_section(fake_self, el)

        result_str = str(result)

        assert "foo" in result_str
        assert "bar" in result_str


LINKED = SourceLinks(repo_url="https://github.com/user/repo")


class TestSourceLinkCompiledExtension:
    def test_so_extension_returns_none(self):
        """When source path ends with .so, returns None."""

        cls = _get_private_cls()

        fake_self = types.SimpleNamespace(
            _source_relative_path=lambda: "mymod.cpython-313-x86_64-linux-gnu.so",
            settings=Settings(source_links=LINKED),
        )

        result = cls.__dict__["source_link"].func(fake_self)

        assert result is None

    def test_pyd_extension_returns_none(self):
        """When source path ends with .pyd, returns None."""

        cls = _get_private_cls()

        fake_self = types.SimpleNamespace(
            _source_relative_path=lambda: "mymod.pyd", settings=Settings(source_links=LINKED)
        )

        result = cls.__dict__["source_link"].func(fake_self)

        assert result is None


class TestSourceRelativePathValueError:
    def test_relative_to_raises_value_error(self):
        """A file outside the repository root uses its package-relative path"""

        cls = _get_private_cls()

        obj = types.SimpleNamespace(
            filepath="/unrelated/path/to/mod.py",
            relative_package_filepath="mod.py",
        )
        links = SourceLinks(package_root=Path("/completely/different/root"))
        fake_self = types.SimpleNamespace(obj=obj, settings=Settings(source_links=links))

        result = cls.__dict__["_source_relative_path"](fake_self)

        assert result == "mod.py"


class TestSourceRelativePathNamespacePackage:
    def test_list_filepath_falls_back_to_package_relative_path(self):
        """Verify that a namespace package uses its package-relative source path"""

        cls = _get_private_cls()

        obj = types.SimpleNamespace(
            filepath=[Path("/repo/a/ns"), Path("/repo/b/ns")],
            relative_package_filepath="ns",
        )
        links = SourceLinks(package_root=Path("/repo"))
        fake_self = types.SimpleNamespace(obj=obj, settings=Settings(source_links=links))

        result = cls.__dict__["_source_relative_path"](fake_self)

        assert result == "ns"
